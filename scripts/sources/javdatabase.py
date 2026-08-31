# -*- coding: utf-8 -*-
"""
javdatabase.com Fetcher —— 英文元数据站，作为 codeav 的「第二源」交叉校验
============================================================================
详情页按番号（小写）：https://javdatabase.com/movies/{code}/

设计要点（对应 jav-idol-db 需求）：
- 该站受 Cloudflare 保护（探测报告 cf_blocked=true），需 wait_past_cf 过验证；
  无年龄墙（age_gate=false），click_age_gate 不会误触。
- 页面返回的女优是「罗马音」（如 Kana Momonogi），与本站日文目录名
  （如 桃乃木かな）写法体系不同，无法用于归属校验，强填会污染 attribution
  判定与女优列表。因此本 Fetcher **不返回 actress / actresses**，仅补全
  描述性元数据（标题 / 发行日 / 片商 / 标签 / 系列 / 时长 / 导演 / 封面 / 简介），
  充当 codeav 缺失字段的回填与交叉校验来源。
- 若日后需要罗马音↔日文女优名映射，再在此扩展 cast 字段即可。

提取策略：优先取 h1 标题；详情以「Label: value」文本行解析（Release Date /
Studio / Label / Series / Director / Duration / Tags / Genre），面包屑回退片商，
og:image 回退封面。多选择器 + 整页 innerText 回退，尽量稳健。
"""
import re
from .base import Fetcher, canon_code, clean, run_with_browser, wait_past_cf

# 详情行标签：Label: value
_RELABEL = re.compile(
    r"^(Release\s*Date|Studio|Label|Series|Director|Duration|Runtime|Tags|Genre|Actresses|Idols)\s*[:：]?\s*(.*)$",
    re.I,
)
_RE_DATE = re.compile(r"(\d{4}[-/]\d{2}[-/]\d{2})")
_RE_INT = re.compile(r"(\d+)")


class JavdatabaseFetcher(Fetcher):
    name = "javdatabase"

    def _extract(self, page, std):
        # ---- 标题 ----
        title = None
        try:
            h = page.locator("h1.entry-title, h1, .entry-title").first
            if h.count():
                title = clean(h.inner_text())
        except Exception:
            pass
        if not title:
            try:
                t = page.title()
                if t and " - JAV Database" in t:
                    title = clean(t.split(" - JAV Database")[0])
                elif t:
                    title = clean(t)
            except Exception:
                pass
        if not title:
            return None

        info = {
            "date": None, "maker": None, "label": None, "series": None,
            "duration": None, "director": None, "tags": [], "synopsis": None,
            "cover": None,
        }

        # ---- 收集详情文本 ----
        full = ""
        try:
            blocks = page.locator(
                ".entry-content p, .entry-content div, .movie-meta li, .movie-info div"
            ).all()
            lines = []
            for b in blocks:
                try:
                    txt = clean(b.inner_text())
                except Exception:
                    continue
                if txt:
                    lines.append(txt)
            full = "\n".join(lines)
        except Exception:
            full = ""
        if not full:
            try:
                full = page.inner_text()
            except Exception:
                full = ""

        # ---- 逐行解析 label:value ----
        for line in full.splitlines():
            line = line.strip()
            m = _RELABEL.match(line)
            if not m:
                continue
            key = m.group(1).lower()
            val = clean(m.group(2))
            if not val:
                continue
            if key == "release date":
                dm = _RE_DATE.search(val)
                if dm:
                    info["date"] = dm.group(1).replace("/", "-")
            elif key == "studio":
                info["maker"] = val
            elif key == "label":
                info["label"] = val
            elif key == "series":
                info["series"] = val
            elif key in ("director",):
                info["director"] = val
            elif key in ("duration", "runtime"):
                im = _RE_INT.search(val)
                if im:
                    info["duration"] = int(im.group(1))
            elif key in ("tags", "genre"):
                for t in re.split(r"[,/、]", val):
                    t = clean(t)
                    if t and t not in info["tags"]:
                        info["tags"].append(t)

        # ---- 封面 ----
        try:
            img = page.locator(
                "#poster img, .poster img, .entry-content img, meta[property='og:image']"
            ).first
            if img.count():
                cover = clean(img.get_attribute("src") or "")
                if not cover:
                    cover = clean(img.get_attribute("content") or "")
                info["cover"] = cover or None
        except Exception:
            pass

        # ---- 简介（较长段落）----
        try:
            for p in page.locator(".entry-content p").all():
                txt = clean(p.inner_text())
                if len(txt) > 80 and "Release Date" not in txt and "Studio" not in txt:
                    info["synopsis"] = txt
                    break
        except Exception:
            pass

        # ---- 片商回退：面包屑 Home > Movies > Studio > CODE ----
        if not info["maker"]:
            try:
                crumb = page.locator(".breadcrumb, nav").first
                if crumb.count():
                    links = [clean(a.inner_text()) for a in crumb.locator("a").all()]
                    if len(links) >= 3:
                        info["maker"] = links[-2]
            except Exception:
                pass

        return {
            "code": std, "source": self.name, "source_url": page.url,
            "title": title,
            "date": info["date"], "actress": None, "actresses": [],
            "maker": info["maker"], "label": info["label"],
            "series": info["series"], "duration": info["duration"],
            "tags": info["tags"], "synopsis": info["synopsis"],
            "rating": None, "rating_count": None, "cover": info["cover"],
            "director": info["director"],
        }

    def fetch(self, code, hint=None):
        std = canon_code(code)
        url = f"https://javdatabase.com/movies/{std.lower()}/"
        try:
            def _go(page):
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if not wait_past_cf(
                    page, page.locator("h1, .entry-title, #poster, .poster"),
                    timeout=70000,
                ):
                    return None
                return self._extract(page, std)
            return run_with_browser(_go, locale="en-US")
        except Exception:
            return None
