# -*- coding: utf-8 -*-
"""
javdb.com Fetcher —— 搜索后取首条结果进详情。CF 重，且主域常被墙，
带 .tv 镜像兜底。选择器为该站长稳结构（.title / .facts / .tags）。
"""
import re
from .base import Fetcher, canon_code, clean, run_with_browser, wait_past_cf, click_age_gate


class JavdbFetcher(Fetcher):
    name = "javdb"
    DOMAINS = ["https://javdb.com", "https://javdb.tv", "https://javdb39.com"]

    def _extract(self, page, std):
        title = None
        try:
            h = page.locator("h2.title, .title").first
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
            for it in page.locator(".facts .fact, .facts li").all():
                txt = clean(it.inner_text())
                if not txt:
                    continue
                if "發行" in txt or "发行" in txt or "date" in txt.lower():
                    m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
                    if m:
                        date = m.group(1)
                elif "製作" in txt or "制作" in txt or "studio" in txt.lower():
                    a = it.locator("a, span").last
                    if a.count():
                        maker = clean(a.inner_text())
                elif "演員" in txt or "演员" in txt or "actor" in txt.lower():
                    for a in it.locator("a").all():
                        t = clean(a.inner_text())
                        if t and t not in actresses:
                            actresses.append(t)
                    if actresses:
                        actress = actresses[0]
        except Exception:
            pass
        try:
            for a in page.locator(".tags a, .genres a").all():
                t = clean(a.inner_text())
                if t and t not in tags:
                    tags.append(t)
        except Exception:
            pass
        cover = None
        try:
            img = page.locator(".column-left img, .video-cover img, img.cover").first
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
        last = None
        for domain in self.DOMAINS:
            try:
                def _go(page):
                    page.goto(f"{domain}/search?q={std}&f=all",
                              wait_until="domcontentloaded", timeout=30000)
                    click_age_gate(page)
                    if not wait_past_cf(page, page.locator("a[href^='/v/'], .item-title a"),
                                         timeout=60000):
                        return None
                    link = page.locator("a[href^='/v/']").first
                    if not link.count():
                        return None
                    href = link.get_attribute("href")
                    if not href:
                        return None
                    page.goto(domain + href, wait_until="domcontentloaded", timeout=30000)
                    click_age_gate(page)
                    page.wait_for_timeout(2000)
                    return self._extract(page, std)
                res = run_with_browser(_go, locale="ja-JP")
                if res:
                    return res
                last = res
            except Exception:
                continue
        return last
