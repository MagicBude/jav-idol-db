# -*- coding: utf-8 -*-
"""
javlibrary.com Fetcher —— 老牌库，结构稳定，CF 偶发拦截
详情页按番号：https://www.javlibrary.com/?v={std}
选择器为该站长期稳定结构（h3.post-title / #video_date / #video_maker 等）。
"""
from .base import Fetcher, canon_code, clean, run_with_browser, wait_past_cf


class JavlibraryFetcher(Fetcher):
    name = "javlibrary"

    def _extract(self, page, std):
        title = clean(page.locator("h3.post-title").first.inner_text())
        date = None
        try:
            d = page.locator("#video_date .text").first
            if d.count():
                date = clean(d.inner_text())
        except Exception:
            pass
        maker = None
        try:
            m = page.locator("#video_maker a").first
            if m.count():
                maker = clean(m.inner_text())
        except Exception:
            pass
        actress = None
        actresses = []
        try:
            for a in page.locator("#video_cast .cast").all():
                t = clean(a.inner_text())
                if t:
                    actresses.append(t)
            if actresses:
                actress = actresses[0]
        except Exception:
            pass
        tags = []
        try:
            for g in page.locator("#video_genres a").all():
                t = clean(g.inner_text())
                if t and t not in tags:
                    tags.append(t)
        except Exception:
            pass
        cover = None
        try:
            img = page.locator("#video_jacket img").first
            if img.count():
                cover = clean(img.get_attribute("src"))
        except Exception:
            pass
        if not title:
            return None
        return {
            "code": std, "source": self.name,
            "source_url": f"https://www.javlibrary.com/?v={std.lower()}",
            "title": title, "date": date, "actress": actress,
            "actresses": actresses, "maker": maker, "label": None,
            "series": None, "duration": None, "tags": tags,
            "synopsis": None, "rating": None, "rating_count": None,
            "cover": cover, "director": None,
        }

    def fetch(self, code, hint=None):
        std = canon_code(code)
        try:
            def _go(page):
                page.goto(f"https://www.javlibrary.com/?v={std.lower()}",
                          wait_until="domcontentloaded", timeout=30000)
                if not wait_past_cf(page, page.locator("h3.post-title"), timeout=60000):
                    return None
                return self._extract(page, std)
            return run_with_browser(_go, locale="ja-JP")
        except Exception:
            return None
