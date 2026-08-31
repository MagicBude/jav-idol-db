#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""fix_genre_zhcn.py —— 补全 data/genre/genre_*.csv 的 zh_cn 简体列。

背景：站点中文视图（zh）的标签来自 data/genre 映射表，取值优先级
zh_cn > zh_tw > translate。许多行只填了繁体 zh_tw（或 zh_cn 本身也是繁体），
导致中文视图出现「简体女优名 + 繁体标签」混排。

本脚本对每一行：
- 取候选值 base = zh_cn 或 zh_tw 或 translate（按优先级）
- 若 base 是「纯中文且含繁体字」（用 zhconv 检测；含平/片假名视为日文，跳过）
  则把简体结果写回 zh_cn 列
- 不改动日文标签（保留原文，符合「源为日文」设计）

运行：python scripts/fix_genre_zhcn.py
"""
import csv
import os
import re
import zhconv

GENRE_DIR = os.path.join("data", "genre")
# 平假名 \u3040-\u309f / 片假名 \u30a0-\u30ff / 半角片假名 \u31f0-\u31ff
_KANA = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u31f0-\u31ff]")


def is_japanese(s):
    return bool(_KANA.search(s))


def main():
    total = 0
    fixed = 0
    for fn in sorted(os.listdir(GENRE_DIR)):
        if not (fn.startswith("genre_") and fn.endswith(".csv")):
            continue
        path = os.path.join(GENRE_DIR, fn)
        rows = []
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = list(reader.fieldnames or [])
            if "zh_cn" not in fields:  # 原文没有该列则补齐（置于末尾）
                fields.append("zh_cn")
            for r in reader:
                total += 1
                cn = (r.get("zh_cn") or "").strip()
                tw = (r.get("zh_tw") or "").strip()
                tr = (r.get("translate") or "").strip()
                base = cn or tw or tr
                if base and not is_japanese(base):
                    simp = zhconv.convert(base, "zh-cn")
                    if simp != base:
                        r["zh_cn"] = simp
                        fixed += 1
                rows.append(r)
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in rows:
                w.writerow(r)
    print("扫描行数: %d，补全 zh_cn(繁->简) 行数: %d" % (total, fixed))


if __name__ == "__main__":
    main()
