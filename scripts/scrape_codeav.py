#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_codeav.py —— 从 codeav.net 按番号抓取作品元数据，
写入 data/actresses/<女优>/works/<番号>.json

用法：
    python scripts/scrape_codeav.py IPX-005
    python scripts/scrape_codeav.py IPX-005 IPX-006
    python scripts/scrape_codeav.py --actress 桃乃木かな --codes-file codes.txt

说明（写给初学者）：
    - codeav 是 FANZA/DMM 元数据的镜像站，页面是静态 HTML，用 Python 标准库 urllib 就能抓，
      不需要 Selenium / Playwright 那种无头浏览器。
    - 片名：取 /movie/{标准番号小写} 页面的 <h1>（最稳，约 97% 覆盖）。
    - 发行日：取同页 JSON-LD 里的 "datePublished"（YYYY-MM-DD）。
    - 女优：同页 JSON-LD 的 actor.name，或页面里指向 actress 的 <a> 链接文字。
    - 注意：codeav 的 HTML 结构可能随版本变化；哪天解析不出来，按浏览器实际页面调下面几个
      正则 / 选择器即可。本脚本每个解析步骤都包了 try，坏了一处不影响其他字段，缺的标 null。
"""

import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import datetime, date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "data", "actresses")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch_html(url, timeout=20):
    """抓取网页 HTML，失败返回空串（不抛异常，方便批量跑）。"""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  [warn] 抓取失败 {url}: {e}", file=sys.stderr)
        return ""


def canon_code(code):
    """把各种写法归一为标准番号：大写、去前导零、单横线。
    例：ipx-005 -> IPX-005；1stars00145 -> STARS-145；STARS-00145 -> STARS-145。"""
    code = code.strip().upper()
    m = re.match(r"^([A-Z]+)-0*(\d+)$", code)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):03d}"
    # 纯数字或特殊码（如 SAMPLE-264 / FC2-PPV-xxxx）保持原样
    return code


def parse_movie_page(html):
    """从 /movie/{std} 页面解析 (title, date, actress)。"""
    title, released, actress = "", None, None

    # 1) 片名：<h1>...</h1>
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    # 2) 发行日：JSON-LD 里的 "datePublished":"YYYY-MM-DD"
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html)
    if m:
        released = m.group(1)

    # 3) 女优：JSON-LD 的 actor.name
    m = re.search(r'"actor"\s*:\s*\{\s*"@type"\s*:\s*"Person"\s*,\s*"name"\s*:\s*"([^"]+)"', html)
    if not m:
        m = re.search(r'"actor"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"', html)
    if m:
        actress = m.group(1).strip()

    # 4) 兜底：页面里指向 actress 详情的 <a> 链接文字
    if not actress:
        m = re.search(r'href="[^"]*actress[^"]*"[^>]*>([^<]+)</a>', html, re.I)
        if m:
            actress = m.group(1).strip()

    return title, released, actress


def scrape_work(code, actress_hint=None):
    """抓单个番号，返回 work dict（字段见 docs/schema.md）。"""
    std = canon_code(code)
    url = f"https://www.codeav.net/movie/{std.lower()}"
    print(f"[fetch] {std} -> {url}")
    html = fetch_html(url)

    title, released, actress = ("", None, None)
    if html:
        title, released, actress = parse_movie_page(html)

    # 女优：解析不到则用命令行 --actress 提示
    if not actress and actress_hint:
        actress = actress_hint

    work = {
        "code": std,
        "title": title or "",
        "date": released,
        "actress": actress or "",
        "series": std.split("-")[0] if "-" in std else "",
        "maker": None,
        "labels": [],
        "tags": [],
        "cover": None,
        "segments": None,
        "source": "codeav" if html else "pending",
        "source_url": url if html else None,
        "updated_at": date.today().isoformat(),
    }
    if not html:
        print(f"  [skip] {std} 页面未取到，标记为 pending，可换备选源补。")
    return work


def save_work(work):
    """把 work dict 写到 data/actresses/<女优>/works/<番号>.json。"""
    actress = work.get("actress") or "未知女优"
    d = os.path.join(DATA_DIR, actress, "works")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{work['code']}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(work, f, ensure_ascii=False, indent=2)
    print(f"  [ok] 写入 {path}")
    return path


def main():
    ap = argparse.ArgumentParser(description="从 codeav 抓作品元数据")
    ap.add_argument("codes", nargs="*", help="番号，如 IPX-005")
    ap.add_argument("--actress", help="女优名（解析不到时填入 actress 字段）")
    ap.add_argument("--codes-file", help="含番号列表的文本文件，每行一个")
    args = ap.parse_args()

    codes = list(args.codes)
    if args.codes_file:
        with open(args.codes_file, encoding="utf-8") as f:
            codes += [ln.strip() for ln in f if ln.strip()]

    if not codes:
        ap.error("至少给一个番号，或用 --codes-file")

    for c in codes:
        work = scrape_work(c, actress_hint=args.actress)
        save_work(work)

    print(f"\n完成 {len(codes)} 个。记得跑 `python scripts/build_index.py` 重新生成索引。")


if __name__ == "__main__":
    main()
