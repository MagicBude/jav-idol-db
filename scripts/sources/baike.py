# -*- coding: utf-8 -*-
"""
baike.baidu.com Fetcher —— 中文侧女优档案补充源
============================================================================
价值：补 minnano 没有的字段——出生地 / 中文名 / 曾用名 / 代表作品 / 血型，
以及中文别名（供中文搜索与 zh 显示层）。

抓取方式（2026-09-08 实测）：
----------------------------------------------------------------
- 纯 urllib 直连 403（非浏览器指纹拦截）
- 桌面版词条是 JS 水合，headless 等不出正文
- **移动版（iPhone UA）服务端直出**，正文内嵌结构化 JSON：
    {"key":"dateOfBirth","title":"出生日期",...,"text":[{"text":"1997年11月23日"}...]}
  用正则按 key/title 提取，同一 JSON 在页面重复出现，每 key 取首现。
- 反爬绕过：Playwright mobile 语境 + AutomationControlled 关闭 +
  webdriver 置 undefined（沙箱实测稳定通过；本机宽网更稳）。

词条名策略：
----------------------------------------------------------------
百科词条以中文名命名（楓カレン→枫花恋），日文名直连会被弹回首页。
候选名依次直连试错：目录名 → alias.json 簇内中文变体 → minnano 別名，
页面含 dateOfBirth JSON 即认定命中。
"""
import re
import urllib.parse

# 字段 title → 归一化 key（按 title 匹配，跨词条稳健）
_TITLE_MAP = {
    "本名": "real_name",
    "曾用名": "former_name",
    "别名": "alias_baike",
    "外文名": "foreign_name",
    "国籍": "nationality",
    "出生地": "birthplace",
    "籍贯": "native_place",
    "出生日期": "birthdate_raw",
    "身高": "height_raw",
    "经纪公司": "agency_zh",
    "职业": "occupation",
    "代表作品": "notable_work",
    "血型": "blood_type",
    "三围": "measurements_raw",
    "size": "measurements_raw",
    "出道时间": "debut_raw",
    "星座": "constellation",
}

_KEY_RE = re.compile(r'\{"key":"([^"]*)","title":"([^"]*)"')
_TEXT_RE = re.compile(r'"text":" ?([^"]{1,120})"')
_TITLE_SUFFIX = re.compile(r"_百度百科.*$")


def parse_baike_html(html):
    """解析移动版词条页内嵌 JSON → 字段 dict；非词条页返回 None。"""
    if not html or "dateOfBirth" not in html and "birthPlace" not in html:
        # 两把钥匙都没有，基本是首页/验证页
        if not _KEY_RE.search(html or ""):
            return None
    fields = {}
    seen = set()
    for m in _KEY_RE.finditer(html):
        key, title = m.group(1), m.group(2)
        norm = _TITLE_MAP.get(title.strip().lower()) or _TITLE_MAP.get(title.strip())
        if not norm or norm in seen:
            continue
        seg = html[m.end():m.end() + 900]
        # 取第一个干净 text 值（跳过引用/链接 fragments）
        tm = _TEXT_RE.search(seg)
        if not tm:
            continue
        val = tm.group(1).strip()
        if not val or val.startswith("http"):
            continue
        fields[norm] = val
        seen.add(norm)

    # 词条标题 = 中文名（<title>枫花恋_百度百科</title>；title 标签可能带属性/换行，用 lxml）
    try:
        import lxml.html as LH
        titles = LH.fromstring(html).xpath("//title/text()")
        if titles:
            name_zh = _TITLE_SUFFIX.sub("", titles[0]).strip()
            if name_zh and name_zh != "百度百科":
                fields["name_zh"] = name_zh
    except Exception:
        pass

    # 出生日 1997年11月23日 → 1997-11-23
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", fields.get("birthdate_raw", ""))
    if m:
        fields["birthdate"] = "{:04d}-{:02d}-{:02d}".format(*map(int, m.groups()))
    # 身高 150 cm → 150
    m = re.search(r"(\d{3})", fields.get("height_raw", ""))
    if m:
        fields["height"] = int(m.group(1))
    # 三围/SIZE：T:150 B:78cm W:54 H:75cm（C cup） / B82/W59/H81
    size = fields.get("measurements_raw", "")
    if size:
        for key, rx in (("bust", r"B\s*[:：]?\s*(\d{2,3})"),
                        ("waist", r"W\s*[:：]?\s*(\d{2,3})"),
                        ("hips", r"H\s*[:：]?\s*(\d{2,3})")):
            m = re.search(rx, size, re.I)
            if m:
                fields[key] = int(m.group(1))
        m = re.search(r"([A-Z])\s*(?:cup|杯|罩杯)", size, re.I)
        if m:
            fields["cup"] = m.group(1).upper()

    # 中文别名集合：曾用名 / 别名 / 本名≠词条名时也并列
    zh_aliases = []
    for src in (fields.get("former_name"), fields.get("alias_baike")):
        if not src:
            continue
        for part in re.split(r"[、/，,;；]", src):
            part = part.strip()
            # 去括号罗马字注释：樋口彩（Higuchi Aya）→ 樋口彩
            part = re.split(r"[(（]", part)[0].strip()
            if part and part not in zh_aliases:
                zh_aliases.append(part)
    if zh_aliases:
        fields["aliases_zh"] = zh_aliases

    if not fields.get("name_zh"):
        return None
    return fields


# ---------------------------------------------------------------- 抓取
def _module_playwright():
    from playwright.sync_api import sync_playwright  # noqa: F401
    return None


class BaikeFetcher:
    """Playwright 移动版抓取（语境复用，串行使用）。"""

    name = "baike"

    def __init__(self):
        self._pw = None
        self._browser = None
        self._page = None

    def _ensure_page(self):
        if self._page is None:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(
                headless=True, args=["--disable-blink-features=AutomationControlled"])
            ctx = self._browser.new_context(
                user_agent=("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                            "Version/17.0 Mobile/15E148 Safari/604.1"),
                locale="zh-CN", viewport={"width": 390, "height": 844}, is_mobile=True)
            page = ctx.new_page()
            page.add_init_script(
                'Object.defineProperty(navigator,"webdriver",{get:()=>undefined})')
            self._page = page
        return self._page

    def fetch(self, name, timeout=40000):
        """直连词条页，返回 (final_url, html)；未命中返回 (None, None)。"""
        page = self._ensure_page()
        url = "https://baike.baidu.com/item/" + urllib.parse.quote(name)
        html = None
        try:
            page.goto(url, timeout=timeout)
            try:
                page.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(4000)
            # 重定向进行中 content() 会抛错，重试几次
            for _ in range(3):
                try:
                    html = page.content()
                    break
                except Exception:
                    page.wait_for_timeout(1500)
        except Exception as e:
            print(f"    [baike] ERR {name}: {type(e).__name__} {str(e)[:80]}")
            return None, None
        if html is None:
            return None, None
        final = page.url
        if "/item/" not in final:
            return None, None  # 被弹回首页=无此词条
        if "dateOfBirth" not in html and "birthPlace" not in html:
            return None, None
        return final, html

    def close(self):
        for attr in ("_browser", "_pw"):
            try:
                getattr(self, attr).close() if attr == "_browser" else getattr(self, attr).stop()
            except Exception:
                pass


def parse_entry_title(final_url):
    """从最终 URL 取词条名（URL-decoded）。"""
    m = re.search(r"/item/([^/?#]+)", final_url or "")
    if not m:
        return None
    return urllib.parse.unquote(m.group(1))
