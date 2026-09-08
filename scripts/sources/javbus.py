# -*- coding: utf-8 -*-
"""
javbus.com Fetcher —— 中文圈常用，CF 拦截较重。

详情页按番号：https://www.javbus.com/{std}
字段提取改为「静态 HTML 解析」（与 javdatabase 一致，用 lxml XPath，无额外依赖），
Playwright 只负责过 CF 拿到 page.content()。标签匹配借鉴社区刮削器的做法：每个
info 行用 <span> 标签定位字段名，再取对应值；同时兼容中文/英文标签。

2026-09-08 更新：先前以为本源「被 CF 挡必须走浏览器」，实为脚本没走系统代理 →
 直连被墙。改由 base.ensure_proxy() 自动挂代理后，静态 urllib 直连即 200 且无 CF
 挑战，故 fetch_html 改为「静态优先 + 浏览器兜底」，速度提升一个量级。
javbus 年龄墙用 cookie `age=verified; existmag=mag`，静态请求带上即可。
"""
import re
import lxml.html as LH
from .base import (Fetcher, canon_code, clean, run_with_browser,
                   wait_past_cf, http_get, looks_blocked)


# 番号前缀改写：javbus 把 gana/mium/luxu 重定向到带数字前缀的页面
_JAVBUS_REWRITES = [("GANA", "200GANA"), ("MIUM", "300MIUM"), ("LUXU", "259LUXU")]


def _javbus_req_code(code):
    """请求用番号：gana-001 -> 200gana-001（结果仍用原番号）。"""
    u = code.upper()
    for pre, rep in _JAVBUS_REWRITES:
        if u.startswith(pre):
            return rep + u[len(pre):]
    return code


# 字段标签映射（归一化后比对，兼容中英文）
_LABELS = {
    "series": ["系列", "series"],
    "date": ["發行日期", "发行日期", "release"],
    "duration": ["長度", "時長", "片長", "收錄時間", "duration", "length"],
    "director": ["導演", "导演", "director"],
    "maker": ["製作商", "制作商", "maker", "studio"],
    "actress": ["演員", "演员", "actor"],
    "tags": ["類別", "类别", "genre", "tags"],
}


def _norm_label(s):
    return clean(s).rstrip(":：").strip().lower()


def _classify(label):
    nl = _norm_label(label)
    if not nl:
        return None
    for field, cands in _LABELS.items():
        for c in cands:
            if nl == c.lower() or c.lower() in nl or nl in c.lower():
                return field
    return None


_DURATION_RE = re.compile(r"(\d{1,4})\s*(分鐘|分钟|分|分間|min)?", re.I)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def parse_javbus_html(html, std):
    """从 javbus 详情页 HTML 提取字段。返回标准化 dict 或 None。"""
    if not html:
        return None
    doc = LH.fromstring(html)
    if isinstance(doc, str):
        return None

    # 标题
    title = None
    h3 = doc.xpath(".//h3")
    if h3:
        title = clean(h3[0].text_content())
    if not title:
        raw = doc.findtext(".//title") or ""
        title = clean(raw.split("|")[0]) if raw else None
    if title:
        title = re.sub(r"^[\u4e00-\u9fff]{2,6}[-_ ]?\d{2,5}\s*", "", title).strip()

    # info 区
    info = doc.xpath(".//div[contains(concat(' ', normalize-space(@class), ' '), ' info ')]")
    root = info[0] if info else doc

    series = date = duration = director = maker = None
    actress = None
    actresses = []
    tags = []

    for p in root.xpath(".//p"):
        spans = p.xpath(".//span")
        if len(spans) >= 2:
            label = clean(spans[0].text_content())
            value = clean(" ".join(s.text_content() for s in spans[1:]))
        else:
            txt = clean(p.text_content())
            parts = re.split(r"[:：]", txt, 1) if (":" in txt or "：" in txt) else None
            # 注意：maxsplit=1 时 re.split 只返回 2 段，按 3 段解包会 ValueError
            if not parts or len(parts) < 2:
                continue
            label, value = clean(parts[0]), clean(parts[1])
        field = _classify(label)
        if not field:
            continue
        if field == "series":
            series = value or series
        elif field == "date":
            m = _DATE_RE.search(value or "")
            date = m.group(1) if m else date
        elif field == "duration":
            m = _DURATION_RE.search(value or "")
            if m:
                duration = int(m.group(1))
        elif field == "director":
            director = value or director
        elif field == "maker":
            maker = value or maker
        elif field == "actress":
            for a in p.xpath(".//a"):
                t = clean(a.text_content())
                if t and t not in actresses:
                    actresses.append(t)
            if actresses and not actress:
                actress = actresses[0]
        elif field == "tags":
            for a in p.xpath(".//a"):
                href = a.get("href") or ""
                if "/star/" in href:
                    continue
                t = clean(a.text_content())
                if t and t not in tags:
                    tags.append(t)

    # 封面
    cover = None
    for xp in (".//meta[@property='og:image']",
               ".//a[contains(concat(' ', normalize-space(@class), ' '), ' bigImage ')]",
               ".//img[contains(@class, 'cover')]",
               ".//img[contains(@class, 'bigImage')]",
               ".//img[@id='cover']"):
        el = doc.xpath(xp)
        if el:
            cover = el[0].get("content") or el[0].get("href") or el[0].get("src")
            if cover:
                break

    # 预览图（缩略图集）：JavBoss 同款选择器，取 data-src/data-original/src（去重）
    sample_images = []
    seen_s = set()
    for xp in (".//*[@id='sample-waterfall']//a",
               ".//*[@class and contains(concat(' ', normalize-space(@class), ' '), ' sample-waterfall ')]//a",
               ".//*[@class and contains(concat(' ', normalize-space(@class), ' '), ' image-gallery-section ')]//a",
               ".//a[contains(concat(' ', normalize-space(@class), ' '), ' tile-item ')]"):
        for a in doc.xpath(xp):
            for attr in ("data-src", "data-original", "data-lazy-src", "src"):
                u = a.get(attr)
                if u and u not in seen_s:
                    seen_s.add(u)
                    sample_images.append(u)
                    break

    if not title:
        return None
    return {
        "code": std, "source": "javbus", "source_url": "",
        "title": title, "date": date, "actress": actress,
        "actresses": actresses, "maker": maker, "label": None,
        "series": series, "duration": duration, "tags": tags,
        "synopsis": None, "rating": None, "rating_count": None,
        "cover": cover, "director": director, "sample_images": sample_images,
    }


class JavbusFetcher(Fetcher):
    name = "javbus"
    BASES = ["https://www.javbus.com", "https://www.javbus.one"]
    # 年龄墙 cookie（静态请求带上即可，与网页版的 age=verified 等价）
    COOKIE = "dv=1"

    def __init__(self, allow_browser=True, timeout=20):
        self.allow_browser = allow_browser
        self.timeout = timeout

    def url_for(self, std):
        return f"{self.BASES[0]}/{_javbus_req_code(std)}"

    def fetch_html(self, std):
        """静态优先：走代理的 urllib 直连即可拿到完整详情页（2026-09-08 验证）。
        被拦时才降级到 Playwright 过 CF。"""
        url = self.url_for(std)
        html, err = http_get(url, timeout=self.timeout, headers={"Cookie": self.COOKIE})
        if html and not looks_blocked(html):
            return html, url
        if self.allow_browser and err != "HTTP404":
            h2 = self._browser_get(url)
            return (h2, url) if h2 else (None, url)
        return None, url

    def _browser_get(self, url):
        try:
            def _go(page):
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if not wait_past_cf(page, page.locator("h3, #cover, .bigImage"),
                                    timeout=70000):
                    return None
                return page.content()
            return run_with_browser(_go, locale="zh-TW")
        except Exception:
            return None

    def fetch(self, code, hint=None):
        std = canon_code(code)
        html, url = self.fetch_html(std)
        if not html:
            return None
        res = parse_javbus_html(html, std)
        if res:
            res["source_url"] = url
        return res
