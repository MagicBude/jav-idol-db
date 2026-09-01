# -*- coding: utf-8 -*-
"""
codeav.net Fetcher —— 主源（FANZA/DMM 元数据镜像，静态页，urllib 直连最稳）
"""
import re
import json
import urllib.request
from .base import Fetcher, canon_code, clean, UA, upgrade_cover_url


def _meta_dd(html, *keys):
    """从元数据表 <dt>键</dt><dd>值</dd> 取值，兼容日文/英文两套渲染。

    codeav 同一页面会随机返回日文（レーベル / 上映時間 / シリーズ）
    或英文（Label / Runtime / Series）表头，只认一套会漏抓近半作品。
    """
    for k in keys:
        m = re.search(re.escape(k) + r"</dt>\s*<dd>(.*?)</dd>", html, re.S | re.I)
        if m:
            val = clean(re.sub(r"<[^>]+>", "", m.group(1)))
            if val:
                return val
    return None


class CodeavFetcher(Fetcher):
    name = "codeav"

    def fetch(self, code, hint=None):
        std = canon_code(code)
        url = f"https://www.codeav.net/movie/{std.lower()}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
        except Exception:
            return None
        if len(html) < 4000:
            return None

        result = {"code": std, "source": self.name, "source_url": url}

        # 片名
        m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
        result["title"] = clean(m.group(1)) if m else ""
        if not result["title"] or "CodeAV" in result["title"]:
            # 连片名都没有，基本是 404
            return None

        # 发行日
        m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html)
        result["date"] = m.group(1) if m else None

        # 女优：只用 JSON-LD 的 actor 主演字段（codeav 对本片唯一可靠的女优信号）。
        # 注意：页面上的 /actress/ <li> 列表与 avatar 头像卡片都是全站统一的
        # 「相关/人气女优」挂件（几乎每个影片都一致），绝不能当作本片卡司。
        m = re.search(r'"actor"\s*:\s*\[\s*\{\s*"@type"\s*:\s*"Person"\s*,\s*"name"\s*:\s*"([^"]+)', html)
        if not m:
            m = re.search(r'"actor"\s*:\s*\{\s*"@type"\s*:\s*"Person"\s*,\s*"name"\s*:\s*"([^"]+)', html)
        if not m:
            m = re.search(r'"actor"\s*:\s*\[?\s*\{?\s*"name"\s*:\s*"([^"]+)', html)
        actress = clean(m.group(1)) if m else ""
        actress_url = ""
        # 从 JSON-LD actor[].url 精确拿到女优详情页 slug（最可靠）
        m2 = re.search(r'"actor"\s*:\s*\[?\s*\{[^}]*"name"\s*:\s*"([^"]+)"[^}]*"url"\s*:\s*"([^"]+)"', html)
        if m2:
            if clean(m2.group(1)) == actress or not actress:
                actress = clean(m2.group(1))
                actress_url = m2.group(2)
        # 兜底：指向具体女优详情页 /actress/（单数）的链接文字；
        # 排除导航占位「女優 / もっと見る / フィルモグラフィー」等。
        if not actress or actress == "女優":
            m = re.search(r'href="[^"]*/actress/[^"]*"[^>]*>([^<]+)</a>', html, re.I)
            if m:
                t = clean(m.group(1))
                if t and t not in ("女優", "もっと見る", "フィルモグラフィー", "のその他の作品"):
                    actress = t
        result["actress"] = actress
        result["actresses"] = [actress] if actress else []
        result["actress_url"] = actress_url

        # 厂商 maker
        m = re.search(r'"productionCompany"\s*:\s*\{\s*"@type"\s*:\s*"Organization"\s*,\s*"name"\s*:\s*"([^"]+)"', html)
        if not m:
            m = re.search(r'"productionCompany"\s*:\s*"([^"]+)"', html)
        result["maker"] = clean(m.group(1)) if m else None

        # 厂牌 label：优先 JSON-LD，退回元数据表（日/英两套 dt 标签）
        label = None
        m = re.search(r'"label"\s*:\s*\{\s*"@type"\s*:\s*"Organization"\s*,\s*"name"\s*:\s*"([^"]+)"', html)
        if m:
            label = clean(m.group(1))
        if not label:
            m = re.search(r'itemprop="label"[^>]*>([^<]+)<', html, re.I)
            if m:
                label = clean(m.group(1))
        if not label:
            label = _meta_dd(html, "レーベル", "Label")
        result["label"] = label

        # 系列 series：JSON-LD partOf.name；失败则退元数据表（シリーズ / Series）
        m = re.search(r'"partOf"\s*:\s*\{\s*"@type"\s*:\s*"CreativeWorkSeries"\s*,\s*"name"\s*:\s*"([^"]+)"', html)
        if not m:
            m = re.search(r'"partOf"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"', html)
        series = clean(m.group(1)) if m else None
        if not series:
            series = _meta_dd(html, "シリーズ", "Series")
        result["series"] = series

        # 时长 duration：优先元数据表（上映時間 / Runtime），退回 JSON-LD PTnHnM
        dur = None
        raw_dur = _meta_dd(html, "上映時間", "Runtime")
        if raw_dur:
            dm = re.search(r"(\d+)", raw_dur)
            if dm:
                dur = int(dm.group(1))
        if not dur:
            m = re.search(r'"duration"\s*:\s*"PT(?:(\d+)H)?(?:(\d+)M)?"', html)
            if m:
                h = int(m.group(1) or 0)
                mn = int(m.group(2) or 0)
                dur = h * 60 + mn
        result["duration"] = dur

        # 标签 tags：所有 /genre/ 链接文字，过滤导航噪音
        raw_tags = re.findall(r'href="[^"]*genre/[^"]*"[^>]*>([^<]+)</a>', html, re.I)
        noise = {"ジャンル", "genre", "🔎", "関連作品", "カテゴリ", "category", "すべて", "全て", "more...", "more"}
        seen = set()
        tags = []
        for t in raw_tags:
            t = clean(t)
            if not t or len(t) <= 1 or t in noise or t.startswith("🔎") or t in seen:
                continue
            seen.add(t)
            tags.append(t)
        result["tags"] = tags

        # 简介 synopsis
        m = re.search(r'"description"\s*:\s*"([^"]{20,})"', html)
        result["synopsis"] = clean(m.group(1)) if m else None

        # 评分 rating + 评价数
        m = re.search(r'"ratingValue"\s*:\s*"?([\d.]+)"?', html)
        result["rating"] = float(m.group(1)) if m else None
        m = re.search(r'"ratingCount"\s*:\s*"?(\d+)"?', html)
        result["rating_count"] = int(m.group(1)) if m else None

        # 封面 cover（og:image 或 JSON-LD image）
        m = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html, re.I)
        if not m:
            m = re.search(r'"image"\s*:\s*"([^"]+)"', html)
        result["cover"] = upgrade_cover_url(clean(m.group(1))) if m else None

        # 导演 director（codeav 偶发有）
        m = re.search(r'"director"\s*:\s*\{\s*"@type"\s*:\s*"Person"\s*,\s*"name"\s*:\s*"([^"]+)"', html)
        result["director"] = clean(m.group(1)) if m else None

        return result
