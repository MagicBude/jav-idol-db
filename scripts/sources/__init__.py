# -*- coding: utf-8 -*-
"""多源抓取器包。"""
from .base import Fetcher, canon_code, merge_work, attribution_conflict
from .codeav import CodeavFetcher
from .fanza import FanzaFetcher
from .javlibrary import JavlibraryFetcher
from .javbus import JavbusFetcher
from .javdb import JavdbFetcher
from .javdatabase import JavdatabaseFetcher
from .javmenu import JavmenuFetcher
from .websearch import WebSearchFetcher

# 回补链优先级（主源 → 官方 → 库 → 重 CF 源 → 兜底）
CHAIN = [
    CodeavFetcher,
    FanzaFetcher,
    JavlibraryFetcher,
    JavmenuFetcher,      # 静态可达（无 CF），series/director 补源
    JavbusFetcher,
    JavdbFetcher,
    JavdatabaseFetcher,
    WebSearchFetcher,
]

__all__ = [
    "Fetcher", "canon_code", "merge_work", "attribution_conflict",
    "CodeavFetcher", "FanzaFetcher", "JavlibraryFetcher",
    "JavmenuFetcher", "JavbusFetcher", "JavdbFetcher", "JavdatabaseFetcher",
    "WebSearchFetcher", "CHAIN",
]
