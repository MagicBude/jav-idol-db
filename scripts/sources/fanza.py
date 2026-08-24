# -*- coding: utf-8 -*-
"""
fanza.co.jp (DMM) Fetcher —— 官方源，最权威。结构 JS 渲染 + 年龄墙，
必须用无头浏览器。按番号搜索后取首条结果进详情页取元数据。
"""
from .base import Fetcher, canon_code, clean, run_with_browser, wait_past_cf, click_age_gate


class FanzaFetcher(Fetcher):
    name = "fanza"

    def _extract_detail(self, page, std):
        title = None
        try:
            h1 = page.locator("h1.item-title, h1").first
            if h1.count():
                title = clean(h1.inner_text())
        except Exception:
            pass
        if not title:
            try:
                title = clean(page.title())
            except Exception:
                pass
        date = None
        try:
            for td in page.locator("th").all():
                t = clean(td.inner_text())
                if "発売日" in t or "配信開始" in t:
                    v = td.locator("xpath=following-sibling::td").first
                    if v.count():
                        date = clean(v.inner_text())
                        break
        except Exception:
            pass
        maker = None
        try:
            for td in page.locator("th").all():
                t = clean(td.inner_text())
                if "メーカー" in t or "サークル" in t:
                    v = td.locator("xpath=following-sibling::td").first
                    if v.count():
                        maker = clean(v.inner_text())
                        break
        except Exception:
            pass
        actress = None
        actresses = []
        try:
            for a in page.locator("a[href*='artist']").all():
                t = clean(a.inner_text())
                if t and t not in actresses:
                    actresses.append(t)
            if actresses:
                actress = actresses[0]
        except Exception:
            pass
        tags = []
        try:
            for g in page.locator("a[href*='genre']").all():
                t = clean(g.inner_text())
                if t and t not in tags:
                    tags.append(t)
        except Exception:
            pass
        cover = None
        try:
            img = page.locator("img.item-image, .product-image img").first
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
                page.goto(f"https://www.fanza.co.jp/digital/videoa/-/search/=/searchword={std}/",
                          wait_until="domcontentloaded", timeout=30000)
                click_age_gate(page)
                if not wait_past_cf(page, page.locator("p.item-title, .item-title, a.title"),
                                     timeout=60000):
                    return None
                link = page.locator("a[href*='/detail/']").first
                if link.count():
                    href = link.get_attribute("href")
                    if href:
                        page.goto(href, wait_until="domcontentloaded", timeout=30000)
                        click_age_gate(page)
                        page.wait_for_timeout(2000)
                return self._extract_detail(page, std)
            return run_with_browser(_go, locale="ja-JP")
        except Exception:
            return None
