# -*- coding: utf-8 -*-
"""
javdatabase.com Fetcher —— 英文元数据站，作为 codeav 的第二源
============================================================================
详情页（番号小写）：https://www.javdatabase.com/movies/{code}/

抓取方式：静态优先
----------------------------------------------------------------
该站虽挂 Cloudflare，但详情页是**公开缓存内容**（响应头 cf-cache-status: HIT），
实测 urllib 直连即可拿到完整 HTML（2026-09-02 验证 40 样本可达 34，85%），
**无需 Playwright 过 CF**。静态抓取比浏览器快两个数量级（~0.4s vs ~15s/部），
因此默认走 HTTP；只有静态失败且显式允许时才回退浏览器（供本机 CF 变严时使用）。

页面结构（与旧版假设不同，旧正则已失效）：
----------------------------------------------------------------
详情页字段是 `<p class="mb-1"><b>标签: </b>值</p>` 序列，标签名带空格与冒号：

    <p class="mb-1"><b>Title: </b>英文标题</p>
    <p class="mb-1"><b>JAV Series: </b>系列（常为空或误填英文标题片段）</p>
    <p class="mb-1"><b>DVD ID: </b>SSIS-001</p>
    <p class="mb-1"><b>Content ID: </b>ssis00001</p>
    <p class="mb-1"><b>Release Date: </b>2021-02-18</p>
    <p class="mb-1"><b>Runtime: </b>147  (HD: 147) min.</p>
    <p class="mb-1"><b>Studio: </b>S1 NO.1 STYLE</p>
    <p class="mb-1"><b>Director: </b>Ichigohara</p>
    <p class="mb-1"><b>Genre(s): </b>Beautiful Girl ...</p>
    <p class="mb-1"><b>Idol(s)/Actress(es): </b>Sayaka Otoshiro Tsukasa Aoi</p>

关键取舍：英文文本不能直填
----------------------------------------------------------------
本站全库以**日文**为准（maker=アイデアポケット、director=ドラゴン西川），
而 javdatabase 全给英文/罗马音（Idea Pocket / Dragon Nishikawa）。直接写入
会造出「一部日文一部英文」的破碎字段，污染筛选与分组。因此：

- **可直接填**（与语言无关的规范化值）：date、duration、cover
- **只做原值保留，不直接填**：maker_en / director_en / series_en /
  tags_en / content_id —— 这些键不在 base._FILL_FIELDS 里，merge_work 会
  忽略它们，安全。由 scripts/enrich_from_javdatabase.py 经「罗马音→日文映射表」
  转换后再落地（映射表由本站已有日文值反向标注得到）。
- **不返回 title**：英文标题会污染日文标题库。
- **不返回 actress / actresses**：罗马音（Kana Momonogi）与日文目录名
  （桃乃木かな）体系不同，强填会污染归属判定。
"""
import re
import urllib.request
import urllib.error

from .base import Fetcher, UA, canon_code, clean

BASE = "https://www.javdatabase.com"

# 详情页字段块：<p class="mb-1"><b>标签: </b>值</p>
_RE_FIELD = re.compile(r'<p class="mb-1"><b>([^<:]+):\s*</b>(.*?)</p>', re.S)
_RE_TAG = re.compile(r"<[^>]+>")
_RE_DATE = re.compile(r"(\d{4}[-/]\d{2}[-/]\d{2})")
_RE_MIN = re.compile(r"(\d{2,3})\s*(?:\(HD:|min)")
_RE_OGIMAGE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I
)
_RE_OGIMAGE_ALT = re.compile(
    r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']', re.I
)

# 详情页字段标签 → 内部键
_FIELD_MAP = {
    "title": "title_en",
    "jav series": "series_en",
    "dvd id": "dvd_id",
    "content id": "content_id",
    "release date": "date_raw",
    "runtime": "runtime_raw",
    "studio": "maker_en",
    "director": "director_en",
    "genre(s)": "genres_raw",
    "idol(s)/actress(es)": "idols_raw",
}


def _http_get(url, timeout=20, referer=None):
    """静态取 HTML。返回 (html, err)；err 为 None 表示成功。"""
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
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


def parse_detail(html):
    """解析详情页为字段 dict（值均为清洗后的纯文本）。"""
    out = {}
    if not html:
        return out
    for m in _RE_FIELD.finditer(html):
        key = _RE_TAG.sub("", m.group(1)).strip()
        # 页面里 <b> 后可能还有 <a> 链接（如 Idol(s) 指向女优页）
        val = clean(_RE_TAG.sub(" ", m.group(2)))
        internal = _FIELD_MAP.get(key.lower())
        if internal:
            out[internal] = val
        else:
            out.setdefault("_extra", {})[key] = val

    img = _RE_OGIMAGE.search(html) or _RE_OGIMAGE_ALT.search(html)
    if img:
        out["cover"] = img.group(1).strip()
    return out


class JavdatabaseFetcher(Fetcher):
    name = "javdatabase"

    def __init__(self, allow_browser=False, timeout=20):
        """allow_browser：静态失败时是否回退 Playwright（默认 False，沙箱内
        无浏览器且静态已够用；本机若被 CF 拦可置 True 并配 JAV_HUMAN=1）。"""
        self.allow_browser = allow_browser
        self.timeout = timeout

    def url_for(self, std):
        return f"{BASE}/movies/{std.lower()}/"

    def fetch_html(self, std):
        """取详情页 HTML：静态优先，可选回退浏览器。"""
        url = self.url_for(std)
        html, err = _http_get(url, timeout=self.timeout)
        if html:
            return html
        if self.allow_browser and err not in ("HTTP404",):
            html = self._browser_get(url)
            if html:
                return html
        return None

    def _browser_get(self, url):
        from .base import run_with_browser, wait_past_cf
        try:
            def _go(page):
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if not wait_past_cf(page, page.locator("#poster, .entry-content p"),
                                    timeout=45000):
                    return None
                return page.content()
            return run_with_browser(_go, locale="en-US")
        except Exception:
            return None

    def fetch(self, code, hint=None):
        std = canon_code(code)
        html = self.fetch_html(std)
        if not html:
            return None
        d = parse_detail(html)
        if not d:
            return None

        duration = None
        if d.get("runtime_raw"):
            m = _RE_MIN.search(d["runtime_raw"])
            if m:
                v = int(m.group(1))
                # 合理性闸门：正片时长 5~600 分钟
                if 5 <= v <= 600:
                    duration = v

        date = None
        if d.get("date_raw"):
            m = _RE_DATE.search(d["date_raw"])
            if m:
                date = m.group(1).replace("/", "-")

        tags = []
        if d.get("genres_raw"):
            for t in re.split(r"\s{2,}|,(?![a-z])", d["genres_raw"]):
                t = clean(t)
                if t and t not in tags:
                    tags.append(t)

        return {
            "code": std,
            "source": self.name,
            "source_url": self.url_for(std),
            # ---- 可直接落库（与语言无关）----
            "date": date,
            "duration": duration,
            "cover": d.get("cover"),
            # ---- 英文原值：不进 _FILL_FIELDS，仅供映射脚本消费 ----
            "title_en": d.get("title_en"),
            "maker_en": d.get("maker_en"),
            "director_en": d.get("director_en"),
            "series_en": d.get("series_en"),
            "content_id": d.get("content_id"),
            "tags_en": tags,
            "idols_en": d.get("idols_raw"),
            # 刻意不返回 title / actress / actresses
        }
