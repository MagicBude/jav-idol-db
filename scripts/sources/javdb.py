# -*- coding: utf-8 -*-
"""
javdb.com Fetcher —— 搜索后取精确番号匹配进详情。CF 重，主域常被墙，带 .tv 镜像兜底。

字段提取改为「静态 HTML 解析」（与 javdatabase 一致，用 lxml XPath，无额外依赖），
Playwright 只负责过 CF 拿到 page.content()。详情面板结构：
nav.panel.movie-panel-info > div.panel-block，每块 <strong>标签</strong> + <span
class="value">值</span>。男优用 ♂ 符号标记，需过滤。

标签匹配借鉴社区刮削器：strong 文本归一化后比对（番號/日期/時長/導演/片商/系列/
評分/類別/演員），兼容繁简。
"""
import re
import lxml.html as LH
from urllib.parse import quote, urljoin
from .base import (Fetcher, canon_code, clean, run_with_browser, wait_past_cf,
                   click_age_gate, http_get, looks_blocked)


_LABELS = {
    "code": ["番號", "番号"],
    "date": ["日期"],
    "duration": ["時長", "时长"],
    "director": ["導演", "导演"],
    "maker": ["片商"],
    "publisher": ["發行", "发行"],
    "series": ["系列"],
    "rating": ["評分", "评分"],
    "tags": ["類別", "类别"],
    "actress": ["演員", "演员"],
}


def _norm_label(s):
    return "".join(clean(s).rstrip(":：").split())


_DURATION_RE = re.compile(r"(\d{1,4})\s*(分鍾|分钟|分|分間|min)?", re.I)
_RATING_RE = re.compile(r"([\d.]+)\s*分")
_RATING_COUNT_RE = re.compile(r"(\d+)\s*人")


def _block_value(block):
    """取 panel-block 的值文本：优先 span.value，否则去掉 strong 后的剩余。"""
    v = block.xpath(".//span[contains(concat(' ', normalize-space(@class), ' '), ' value ')]")
    if v:
        return clean(v[0].text_content())
    strongs = block.xpath(".//strong")
    if strongs:
        return clean(block.text_content().replace(
            clean(strongs[0].text_content()), "", 1))
    return clean(block.text_content())


def _is_male(link):
    """javdb 男优：紧跟的兄弟 strong 带 .male 或含 ♂。

    注意：class 用分词判断，不能用子串——否则「female」会被误判（'male' in
    'female' 为 True）。"""
    nxt = link.getnext()
    if nxt is None:
        return False
    cls = (nxt.get("class") or "").split()
    if "male" in cls:
        return True
    if "♂" in (nxt.text_content() or ""):
        return True
    return False


def parse_javdb_html(html, std):
    """从 javdb 详情页 HTML 提取字段。返回标准化 dict 或 None。"""
    if not html:
        return None
    doc = LH.fromstring(html)
    if isinstance(doc, str):
        return None

    # 标题：优先 origin-title（无 HTML 实体），次选 current-title
    title = None
    for xp in (".//span[contains(@class, 'origin-title')]",
               ".//strong[contains(@class, 'current-title')]"):  # noqa
        el = doc.xpath(xp)
        if el:
            title = clean(el[0].text_content())
            break
    if not title:
        raw = doc.findtext(".//title") or ""
        if raw:
            for suf in ("| JavDB 成人影片數據庫", "| JavDB"):
                raw = raw.replace(suf, "")
            title = clean(raw.split("|")[0]) if raw else None

    panel = doc.xpath(".//nav[contains(@class, 'movie-panel-info')]")
    root = panel[0] if panel else doc

    out = {"series": None, "date": None, "duration": None, "director": None,
           "maker": None, "publisher": None, "rating": None,
           "rating_count": None, "actress": None, "actresses": [], "tags": []}

    for block in root.xpath(".//div[contains(concat(' ', normalize-space(@class), ' '), ' panel-block ')]"):
        strongs = block.xpath(".//strong")
        if not strongs:
            continue
        field = None
        nl = _norm_label(strongs[0].text_content())
        for k, cands in _LABELS.items():
            if nl in cands or nl in [c.lower() for c in cands]:
                field = k
                break
        if not field:
            continue

        if field == "code":
            m = re.search(r"([A-Z0-9]+-?\d+)", _block_value(block))
            if m:
                out["code"] = canon_code(m.group(1))
        elif field == "date":
            m = re.search(r"(\d{4}-\d{2}-\d{2})", _block_value(block))
            if m:
                out["date"] = m.group(1)
        elif field == "duration":
            m = _DURATION_RE.search(_block_value(block))
            if m:
                out["duration"] = int(m.group(1))
        elif field in ("series", "director", "maker", "publisher"):
            links = block.xpath(".//a")
            if links:
                out[field] = clean(links[0].text_content())
        elif field == "rating":
            val = _block_value(block)
            m = _RATING_RE.search(val or "")
            if m:
                out["rating"] = float(m.group(1))
            mc = _RATING_COUNT_RE.search(val or "")
            if mc:
                out["rating_count"] = int(mc.group(1))
        elif field == "tags":
            for a in block.xpath(".//a"):
                t = clean(a.text_content())
                if t and t not in out["tags"]:
                    out["tags"].append(t)
        elif field == "actress":
            for a in block.xpath(".//a"):
                if _is_male(a):
                    continue
                t = clean(a.text_content())
                if t and t not in out["actresses"]:
                    out["actresses"].append(t)
            if out["actresses"] and not out["actress"]:
                out["actress"] = out["actresses"][0]

    # 封面
    cover = None
    for xp in (".//meta[@property='og:image']",
               ".//img[contains(@class, 'video-cover')]"):  # noqa
        el = doc.xpath(xp)
        if el:
            cover = el[0].get("content") or el[0].get("src")
            if cover:
                break

    if not title and not out["series"] and not out["maker"]:
        if not out["date"] and not out["duration"] and not out["actresses"]:
            return None
    return {
        "code": std, "source": "javdb", "source_url": "",
        "title": title, "date": out["date"], "actress": out["actress"],
        "actresses": out["actresses"], "maker": out["maker"], "label": None,
        "series": out["series"], "duration": out["duration"],
        "tags": out["tags"], "synopsis": None,
        "rating": out["rating"], "rating_count": out["rating_count"],
        "cover": cover, "director": out["director"],
    }


class JavdbFetcher(Fetcher):
    name = "javdb"
    DOMAINS = ["https://javdb.com", "https://javdb39.com", "https://javdb.tv"]

    def __init__(self, allow_browser=True, timeout=20):
        self.allow_browser = allow_browser
        self.timeout = timeout

    # --- 搜索结果里挑出「番号完全相等」的那一条 -----------------------
    @staticmethod
    def _pick_href(html, std):
        """搜不到的绝不将就：javdb 的 f=all 是模糊搜索，搜 SSIS-001 也会返回
        PSIS-001 / SHIS-001。照抄第一条等于给作品灌上别人的 series —— 宁可漏，
        不可错。因此这里只认 div.video-title/strong 里的番号与 std 完全相等者。"""
        try:
            doc = LH.fromstring(html)
        except Exception:
            return None
        for a in doc.xpath("//a[contains(@href,'/v/')]"):
            strongs = a.xpath(".//div[contains(@class,'video-title')]//strong")
            if not strongs:
                continue
            uid = clean(strongs[0].text_content())
            if uid and canon_code(uid) == std:
                return a.get("href")
        return None

    def _static(self, domain, std):
        search_url = f"{domain}/search?q={quote(std)}&f=all"
        html, err = http_get(search_url, referer=f"{domain}/")
        if not html or looks_blocked(html):
            return None, (err or "BLOCKED")
        href = self._pick_href(html, std)
        if not href:
            return None, "NOHIT"
        detail = urljoin(domain + "/", href.lstrip("/"))
        dhtml, derr = http_get(detail, referer=search_url, timeout=self.timeout)
        if not dhtml or looks_blocked(dhtml):
            return None, (derr or "BLOCKED")
        res = parse_javdb_html(dhtml, std)
        if res:
            res["source_url"] = detail
        return res, None

    def _browser(self, domain, std):
        try:
            def _go(page):
                page.goto(f"{domain}/search?q={std}&f=all",
                          wait_until="domcontentloaded", timeout=30000)
                click_age_gate(page)
                if not wait_past_cf(page,
                                    page.locator("a[href^='/v/'], .item-title a"),
                                    timeout=60000):
                    return None
                href = self._pick_href(page.content(), std)
                if not href:
                    return None
                detail = urljoin(domain + "/", href.lstrip("/"))
                page.goto(detail, wait_until="domcontentloaded", timeout=30000)
                click_age_gate(page)
                page.wait_for_timeout(1200)
                res = parse_javdb_html(page.content(), std)
                if res:
                    res["source_url"] = detail
                return res
            return run_with_browser(_go, locale="ja-JP")
        except Exception:
            return None

    def fetch(self, code, hint=None):
        std = canon_code(code)
        for domain in self.DOMAINS:
            res, err = self._static(domain, std)
            if res:
                return res
            if err == "NOHIT":
                continue                      # 主域没这部，换镜像也白搭
            if self.allow_browser:
                res = self._browser(domain, std)
                if res:
                    return res
        return None
