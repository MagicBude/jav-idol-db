# -*- coding: utf-8 -*-
"""
javbus.com Fetcher —— 中文圈常用，CF 拦截较重。详情页按番号：
https://www.javbus.com/{std}
选择器为该站长稳结构（info 区的 發行日期 / 製作商 / 類別 / 演員）。
"""
import re
from .base import Fetcher, canon_code, clean, run_with_browser, wait_past_cf


class JavbusFetcher(Fetcher):
    name = "javbus"

    def _extract(self, page, std):
        title = None
        try:
            h = page.locator("h3").first
            if h.count():
                title = clean(h.inner_text())
            if not title and page.title():
                title = clean(page.title().split("|")[0])
        except Exception:
            pass
        date = None
        maker = None
        actress = None
        actresses = []
        tags = []
        try:
            for p in page.locator(".col-md-3.info p, .info p").all():
                txt = clean(p.inner_text())
                if "發行日期" in txt or "发行日期" in txt:
                    m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                    if m:
                        date = m.group(1)
                elif "製作商" in txt or "制作商" in txt:
                    a = p.locator("a").first
                    if a.count():
                        maker = clean(a.inner_text())
                elif "演員" in txt or "演员" in txt:
                    for a in p.locator("a").all():
                        t = clean(a.inner_text())
                        if t:
                            actresses.append(t)
                    if actresses:
                        actress = actresses[0]
                elif "類別" in txt or "类别" in txt:
                    for a in p.locator("a").all():
                        t = clean(a.inner_text())
                        if t and t not in tags:
                            tags.append(t)
        except Exception:
            pass
        cover = None
        try:
            img = page.locator("#cover, .bigImage img, a.bigImage img").first
            if img.count():
                cover = clean(img.get_attribute("src"))
        except Exception:
            pass
        if not title:
            return None
        return {
            "code": std, "source": self.name, "source_url": page.url,
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
                page.goto(f"https://www.javbus.com/{std}",
                          wait_until="domcontentloaded", timeout=30000)
                if not wait_past_cf(page, page.locator("h3, #cover, .bigImage"), timeout=70000):
                    return None
                return self._extract(page, std)
            return run_with_browser(_go, locale="zh-TW")
        except Exception:
            return None
