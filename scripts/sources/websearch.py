# -*- coding: utf-8 -*-
"""
WebSearch 兜底 Fetcher —— 搜索引擎（DuckDuckGo HTML）最后兜底。
严格模式：只有当某条结果标题/摘要里**确实出现该番号**时才采用，
避免把搜索首页/百科页的噪声标题当成了作品名（垃圾比 pending 更糟）。
"""
import re
import urllib.parse
import urllib.request
from .base import Fetcher, canon_code, clean, UA


class WebSearchFetcher(Fetcher):
    name = "websearch"

    def fetch(self, code, hint=None):
        std = canon_code(code)
        # 同时匹配带横线 / 去横线两种写法
        variants = {std.lower(), std.replace("-", "").lower()}
        q = urllib.parse.quote(f"{std} 番号 発売日")
        url = f"https://html.duckduckgo.com/html/?q={q}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            html = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        except Exception:
            return None

        # 逐条结果：标题 + 摘要，必须包含番号才可信
        blocks = re.findall(r'class="result[^"]*"[^>]*>(.*?)(?=class="result[^"]*"|<script|</body>)',
                             html, re.S)
        for blk in blocks:
            title = clean(re.sub(r"<[^>]+>", "", re.search(r'class="result__a"[^>]*>(.*?)</a>', blk, re.S).group(1))) \
                if re.search(r'class="result__a"[^>]*>(.*?)</a>', blk, re.S) else ""
            snip = clean(re.sub(r"<[^>]+>", "", re.search(r'class="result__snippet"[^>]*>(.*?)</a>', blk, re.S).group(1))) \
                if re.search(r'class="result__snippet"[^>]*>(.*?)</a>', blk, re.S) else ""
            hay = (title + " " + snip).lower()
            if not any(v in hay for v in variants):
                continue  # 这条结果不含番号，跳过（大概率是噪声）
            # 从摘要抽发行日
            date = None
            m = re.search(r"(\d{4}[-/年]\d{1,2}[-/月]\d{1,2})", snip)
            if m:
                date = m.group(1).replace("年", "-").replace("月", "-").replace("/", "-")
                date = re.sub(r"-(\d)(?=-|$)", r"-0\1", date)
            # 标题需看起来像作品名（不是站点首页）——含番号且不太长
            if title and any(v in title.lower() for v in variants) and len(title) < 80:
                return {
                    "code": std, "source": self.name, "source_url": url,
                    "title": title, "date": date, "actress": hint,
                    "actresses": [hint] if hint else [], "maker": None, "label": None,
                    "series": None, "duration": None, "tags": [], "synopsis": None,
                    "rating": None, "rating_count": None, "cover": None, "director": None,
                }
        return None
