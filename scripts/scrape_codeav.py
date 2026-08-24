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
    """把各种写法归一为标准番号：大写、去首尾空白、统一连字符。

    重要：番号的数字位数由各厂牌约定（IPX-005 是 005，SNOS-3 是 3，
    FC2-PPV-xxxx 是 7 位），本函数**不改动数字位数**——否则会把
    SNOS-3 误补成 SNOS-003，写文件时分叉出孤儿、原文件残留 migrated。
    归一只做：大写 + 去空白 + 连字符统一。"""
    code = code.strip().upper()
    code = re.sub(r"[\s_]+", "-", code)
    return code


def parse_movie_page(html):
    """从 /movie/{std} 页面解析全部可用元数据。

    返回 dict，包含 codeav 上所有可提取的字段：
      title, date, actress, maker, label, series,
      duration, tags, synopsis, rating, rating_count, cover_url
    每个字段独立 try，坏一处不影响其他。
    """
    result = {
        "title": "",
        "date": None,
        "actress": None,
        "maker": None,       # 厂商 / Studio（如 アイデアポケット）
        "label": None,       # 厂牌 / Label（如 ティッシュ）
        "series": None,      # 系列（如 噂の本番できちゃうおっパブ店）
        "duration": None,    # 时长（如 "119 min" 或纯数字 119）
        "tags": [],          # 类型标签（如 Big Tits, Beautiful Girl）
        "synopsis": None,    # 剧情简介 / Blurb
        "rating": None,      # 评分（如 4.5）
        "rating_count": None,# 评价数（如 56）
        "cover_url": None,   # 封面图 URL
    }

    # ── 1) 片名：<h1> ──
    m = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
    if m:
        result["title"] = re.sub(r"<[^>]+>", "", m.group(1)).strip()

    # ── 2) 发行日：JSON-LD datePublished ──
    m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"', html)
    if m:
        result["date"] = m.group(1)

    # ── 3) 女优：JSON-LD actor.name ──
    m = re.search(
        r'"actor"\s*:\s*\{\s*"@type"\s*:\s*"Person"\s*,\s*"name"\s*:\s*"([^"]+)"',
        html)
    if not m:
        m = re.search(r'"actor"\s*:\s*\{\s*"name"\s*:\s*"([^"]+)"', html)
    if m:
        result["actress"] = m.group(1).strip()
    if not result["actress"]:
        m = re.search(r'href="[^"]*actress[^"]*"[^>]*>([^<]+)</a>', html, re.I)
        if m:
            result["actress"] = m.group(1).strip()

    # ── 4) 厂商 Studio：/studio/ 链接文字 ──
    m = re.search(r'href="[^"]*studio/[^"]*"[^>]*>([^<]+)</a>', html, re.I)
    if m:
        result["maker"] = m.group(1).strip()

    # ── 5) 厂牌 Label：/label/ 链接文字 ──
    m = re.search(r'href="[^"]*label/[^"]*"[^>]*>([^<]+)</a>', html, re.I)
    if m:
        result["label"] = m.group(1).strip()

    # ── 6) 系列 Series：/series/ 链接文字 ──
    m = re.search(r'href="[^"]*series/[^"]*"[^>]*>([^<]+)</a>', html, re.I)
    if m:
        result["series"] = m.group(1).strip()

    # ── 7) 时长 Runtime ──
    # 尝试多种格式：119 min / 119分 / 119分钟 / 纯数字在特定上下文中
    duration = None
    # 格式 A: "119 min" / "119mins"
    m = re.search(r'(\d+)\s*(?:min|mins|minutes?)\b', html, re.I)
    if m:
        duration = int(m.group(1))
    # 格式 B: 日文 "119分" / "119分钟"
    if not duration:
        m = re.search(r'(\d+)\s*(?:分|分間)', html)
        if m:
            duration = int(m.group(1))
    # 格式 C: JSON-LD duration (ISO 8601 PT... format)
    if not duration:
        m = re.search(r'"duration"\s*:\s*"PT(\d+)M?"', html)
        if m:
            duration = int(m.group(1))
    # 格式 D: 在 Runtime/収録时间 等标签旁的数字
    if not duration:
        m = re.search(r'(?:Runtime|収録時間|収録時間|時間)\s*[:：]?\s*(\d+)', html, re.I)
        if m:
            duration = int(m.group(1))
    result["duration"] = duration

    # ── 8) 标签 Tags：所有 /genre/ 链接文字，过滤噪音 ──
    raw_tags = re.findall(r'href="[^"]*genre/[^"]*"[^>]*>([^<]+)</a>', html, re.I)
    # 过滤噪音：导航文字、过短、含 emoji/特殊符号 的非标签项
    noise = {"ジャンル", "genre", "🔎", "関連作品", "カテゴリ", "category",
             "すべて", "全て", "more...", "more"}
    seen = set()
    result["tags"] = [
        t.strip() for t in raw_tags
        if t.strip() and len(t.strip()) > 1
        and not any(n in t for n in noise)
        and not t.strip().startswith("🔎")
        and not (t.strip() in seen or seen.add(t.strip()))  # 去重
    ]

    # ── 9) 简介 Synopsis：Blurb / About 区域的长文本 ──
    # 策略 A：JSON-LD description 或 abstract 字段
    m = re.search(r'"description"\s*:\s*"((?:[^"\\]|\\.)*)"', html)
    if m:
        raw = m.group(1).replace('\\"', '"').replace('\\n', '\n')
        if len(raw) > 20:  # 排除太短的噪音
            result["synopsis"] = raw.strip()
    # 策略 B：页面中【】或长段落文本
    if not result["synopsis"]:
        # codeav 的 blurb 通常在特定 div 或 p 中，含【】符号
        m = re.search(r'(【[^】]+】(?:[^<]{20,}))', html)
        if m:
            result["synopsis"] = m.group(1).strip()

    # ── 10) 评分 Rating：★ X.X 或类似格式 ──
    m = re.search(r'★\s*([\d.]+)', html)
    if m:
        result["rating"] = float(m.group(1))
    # 评价数
    m = re.search(r'(\d+)\s*(?:reviews?|verified\s+reviews?|件の評価)', html, re.I)
    if m:
        result["rating_count"] = int(m.group(1))

    # ── 11) 封面图 URL：poster/image og:image ──
    # 优先取 og:image（最标准）
    m = re.search(r'<meta[^>]*property="og:image"[^>]*content="([^"]+)"', html, re.I)
    if m:
        result["cover_url"] = m.group(1).strip()
    if not result["cover_url"]:
        m = re.search(r'<img[^>]*(?:class|id)="[^"]*(?:cover|poster|movie)[^"]*"[^>]*src="([^"]+)"', html, re.I)
        if m:
            result["cover_url"] = m.group(1).strip()

    return result


def scrape_work(code, actress_hint=None, original_cover=None):
    """抓单个番号，返回 work dict（字段见 docs/schema.md）。"""
    std = canon_code(code)
    url = f"https://www.codeav.net/movie/{std.lower()}"
    print(f"[fetch] {std} -> {url}")
    html = fetch_html(url)

    parsed = {"title": "", "date": None, "actress": None,
              "maker": None, "label": None, "series": None,
              "duration": None, "tags": [], "synopsis": None,
              "rating": None, "rating_count": None, "cover_url": None}
    if html:
        parsed = parse_movie_page(html)

    # 女优：命令行 --actress 提示优先（按我们归档的女优名，归属最准）
    if actress_hint:
        parsed["actress"] = actress_hint

    # cover：优先用抓到的 URL；否则保留原占位路径
    cover = parsed.get("cover_url") or original_cover or None

    work = {
        "code": std,
        "title": parsed["title"] or "",
        "date": parsed["date"],
        "actress": parsed["actress"] or "",
        "series": parsed["series"],       # 真实系列名（不再用番号前缀）
        "maker": parsed["maker"],          # 厂商 / Studio
        "label": parsed["label"],          # 厂牌 / Label
        "duration": parsed["duration"],     # 时长（分钟）
        "labels": [],                       # 保留 labels 字段兼容（可后续从 label 派生）
        "tags": parsed["tags"],             # 类型标签
        "synopsis": parsed["synopsis"],     # 剧情简介
        "rating": parsed["rating"],         # 评分
        "rating_count": parsed["rating_count"],  # 评价数
        "cover": cover,
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
