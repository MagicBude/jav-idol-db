# -*- coding: utf-8 -*-
"""
javmenu.com Fetcher —— 聚合站，静态可达，series/director 缺口的重要补源
============================================================================
详情页（番号大写）：https://javmenu.com/{CODE}

抓取方式：静态优先
----------------------------------------------------------------
该站无 Cloudflare 拦截（2026-09-07 沙箱实测 urllib 直连 200，150KB 完整
HTML，无挑战页），静态请求 ~1s/部，无需 Playwright。仅在静态失败时可选
回退浏览器（allow_browser=True，供本机网络变化时使用）。

字段值语言：繁中标签 + 日文值
----------------------------------------------------------------
信息卡片为 `div.card-body`（内含「影片資料」字样）下的行序列，每行
`<div><span>标签:</span> 值</div>`；标签兼容繁中/简中/日文/英文（与社区
刮削器一致），值本身是日文原文（系列=初体験○本番スペシャル、導演=嵐山
みちる），可直接落库——符合本站「日文为唯一真相」原则，与 javdatabase
（英文值需映射）的处理方式不同。

关键取舍：
- date / duration / cover / title(日文) / maker / director / series / tags
  / actresses 可直接落库（值均为日文）。
- label 无独立行（该站不提供），保持 None。
- synopsis 不取（该站简介为繁中翻译，会污染日文简介）。
"""
import re
import urllib.request
import urllib.error

import lxml.html as LH

from .base import Fetcher, UA, canon_code, clean

BASE = "https://javmenu.com"

# 字段标签映射（归一化后比对，兼容繁中/简中/日文/英文）
# 注：刻意不含 女優/類別（actress/tags）——该站演员男女优不分（全是 /actor/ 链接，
# 男优会混入），标签是繁中翻译（單體作品/多P），与全库日文体系冲突，填了必污染。
_LABELS = {
    "date": ["發佈於", "发布于", "發行日期", "发行日期", "発売日", "release date"],
    "duration": ["時長", "时长", "長度", "长度", "duration", "runtime"],
    "maker": ["出版", "發行", "发行", "片商", "製作商", "制作商", "studio", "maker", "publisher"],
    "series": ["系列", "series"],
    "director": ["導演", "导演", "director"],
}


def _norm_label(s):
    """标签归一化：去空白去冒号转小写（JavBoss 同款 normalizeJavMenuLabel）。"""
    s = clean(s).rstrip(":：").strip().lower()
    return "".join(s.split())


def _classify(label):
    nl = _norm_label(label)
    if not nl:
        return None
    for field, cands in _LABELS.items():
        for c in cands:
            if nl == c or c in nl or nl in c:
                return field
    return None


_TITLE_SUFFIXES = ("免費AV在線看", "免费AV在线看")
_RE_CODE_PREFIX = re.compile(r"^[A-Z]{2,8}[-_]?\d{2,6}[A-Z]{0,3}\s+", re.I)
_DURATION_RE = re.compile(r"(\d{1,4})\s*(分鐘|分钟|分|min)?", re.I)
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _clean_title(raw, code):
    """清理标题：去「免費AV在線看」后缀、去番号前缀、去「 | 」之后内容。"""
    t = clean(raw)
    if not t:
        return None
    for suf in _TITLE_SUFFIXES:
        if t.endswith(suf):
            t = clean(t[: -len(suf)])
    if code:
        # 前缀可能是「SONE-001 」或「SONE001 」
        t = re.sub(re.escape(code) + r"\s*", "", t, count=1, flags=re.I).strip()
    t = _RE_CODE_PREFIX.sub("", t).strip()
    if " | " in t:
        t = clean(t.split(" | ")[0])
    return t or None


def _find_info_card(doc):
    """定位含「影片資料」的信息卡片 div.card-body。"""
    for c in doc.xpath("//div[contains(concat(' ', normalize-space(@class), ' '), ' card-body ')]"):
        try:
            if "影片資料" in (c.text_content() or ""):
                return c
        except Exception:
            continue
    return None


def parse_javmenu_html(html, std):
    """从 javmenu 详情页 HTML 提取字段。返回标准化 dict 或 None。"""
    if not html:
        return None
    try:
        doc = LH.fromstring(html)
    except Exception:
        return None
    if isinstance(doc, str):
        return None

    card = _find_info_card(doc)
    fields = {}
    if card is not None:
        for row in card.xpath("./div"):
            spans = row.xpath("./span")
            if not spans:
                continue
            label = clean(spans[0].text_content())
            field = _classify(label)
            if not field:
                continue
            # 值：字段行的链接多指向站内搜索/系列页，文本不可靠（番號行甚至把
            # 番号拆成 SONE + -001 两个 a），故一律取「整行文本去掉标签文本」
            full = clean(row.text_content())
            lbl_txt = clean(spans[0].text_content())
            value = clean(full.replace(lbl_txt, "", 1))
            if value and value not in ("---", "無", "无"):
                fields[field] = fields.get(field) or value

    # 标题：h1 优先，title 兜底（code 前缀用 std 去，页面内番号行不可靠）
    title = None
    h1 = doc.xpath("//h1")
    if h1:
        title = _clean_title(h1[0].text_content(), std)
    if not title:
        raw = doc.findtext(".//title") or ""
        title = _clean_title(raw, std)

    # 封面：og:image
    cover = None
    og = doc.xpath("//meta[@property='og:image']/@content")
    if og:
        cover = clean(og[0])

    date = None
    if fields.get("date"):
        m = _DATE_RE.search(fields["date"])
        if m:
            date = m.group(1)
    duration = None
    if fields.get("duration"):
        m = _DURATION_RE.search(fields["duration"])
        if m:
            v = int(m.group(1))
            if 5 <= v <= 600:  # 合理性闸门
                duration = v

    # 软 404 闸门：番号不存在时该站返回「猜你喜歡」推荐页——有 h1 标题但
    # 没有任何「影片資料」字段行。信息卡片字段是命中作品的硬性证据，
    # 一个字段都没解析到就视为未命中（防止拿推荐页标题污染库）。
    if not fields:
        return None
    if not title and not fields.get("series") and not fields.get("maker"):
        return None
    return {
        "code": std, "source": "javmenu", "source_url": "",
        "title": title, "date": date,
        # 刻意不返回 actress / actresses / tags（见 _LABELS 处注释）
        "actress": None, "actresses": [], "maker": fields.get("maker"),
        "label": None, "series": fields.get("series"), "duration": duration,
        "tags": [], "synopsis": None, "rating": None, "rating_count": None,
        "cover": cover, "director": fields.get("director"),
    }


def _http_get(url, timeout=20, referer=None):
    """静态取 HTML。返回 (html, err)；err 为 None 表示成功。"""
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,ja;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace"), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP{e.code}"
    except Exception as e:
        return None, type(e).__name__


class JavmenuFetcher(Fetcher):
    name = "javmenu"

    def __init__(self, allow_browser=False, timeout=20):
        self.allow_browser = allow_browser
        self.timeout = timeout

    def url_for(self, std):
        return f"{BASE}/{std.upper()}"

    def fetch_html(self, std):
        url = self.url_for(std)
        html, err = _http_get(url, timeout=self.timeout)
        if html:
            return html
        if self.allow_browser and err not in ("HTTP404",):
            return self._browser_get(url)
        return None

    def _browser_get(self, url):
        from .base import run_with_browser, wait_past_cf
        try:
            def _go(page):
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if not wait_past_cf(page, page.locator("h1, div.card-body"),
                                    timeout=45000):
                    return None
                return page.content()
            return run_with_browser(_go, locale="zh-TW")
        except Exception:
            return None

    def fetch(self, code, hint=None):
        std = canon_code(code)
        html = self.fetch_html(std)
        if not html:
            return None
        res = parse_javmenu_html(html, std)
        if res:
            res["source_url"] = self.url_for(std)
        return res
