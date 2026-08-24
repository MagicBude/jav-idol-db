#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_index.py —— 扫描 data/ 下所有女优档案与作品，生成两份汇总索引：
    1) data/index.json            —— 给程序 / API 用
    2) site/assets/js/data.js     —— window.JAV_DB = {...}，给站点用（支持 file:// 双击打开）

用法：
    python scripts/build_index.py
    python scripts/build_index.py --check   # 只校验数据完整性，不写文件

设计（写给初学者）：
    - data/actresses/<名>/profile.json 是女优属性；works/<番号>.json 是作品。
    - 女优的 work_count / codes 不手存，这里实时聚合，避免和 works/ 不一致。
    - 站点读 data.js（内联 JSON），所以改完 data/ 一定要重跑本脚本，站点才会更新。
"""

import argparse
import json
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTRESSES_DIR = os.path.join(BASE, "data", "actresses")
INDEX_JSON = os.path.join(BASE, "data", "index.json")
DATA_JS = os.path.join(BASE, "site", "assets", "js", "data.js")


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def build():
    actresses = []
    for name in sorted(os.listdir(ACTRESSES_DIR)):
        adir = os.path.join(ACTRESSES_DIR, name)
        if not os.path.isdir(adir):
            continue
        profile = load_json(os.path.join(adir, "profile.json")) or {"name": name}
        works_dir = os.path.join(adir, "works")
        works = []
        if os.path.isdir(works_dir):
            for fn in sorted(os.listdir(works_dir)):
                if fn.endswith(".json"):
                    w = load_json(os.path.join(works_dir, fn))
                    if w:
                        works.append(w)
        # 聚合 codes 与 count
        codes = sorted({w.get("code") for w in works if w.get("code")})
        profile["work_count"] = len(works)
        profile["codes"] = codes
        profile["name"] = profile.get("name") or name
        profile["works"] = works
        actresses.append(profile)
    return actresses


def validate(actresses):
    problems = []
    for a in actresses:
        if not a.get("name"):
            problems.append("女优缺少 name")
        for w in a.get("works", []):
            if not w.get("code"):
                problems.append(f"{a.get('name')} 下有作品缺 code")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args()

    actresses = build()
    problems = validate(actresses)

    total_works = sum(a["work_count"] for a in actresses)
    print(f"聚合：{len(actresses)} 位女优 / {total_works} 部作品")
    if problems:
        print("数据问题：")
        for p in problems:
            print("  -", p)
    else:
        print("校验通过，无结构问题。")

    if args.check:
        return

    index = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "counts": {"actresses": len(actresses), "works": total_works},
        "actresses": actresses,
    }
    os.makedirs(os.path.dirname(INDEX_JSON), exist_ok=True)
    with open(INDEX_JSON, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    os.makedirs(os.path.dirname(DATA_JS), exist_ok=True)
    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write("window.JAV_DB = ")
        json.dump(index, f, ensure_ascii=False)
        f.write(";\n")
    print(f"已生成：\n  {INDEX_JSON}\n  {DATA_JS}")


if __name__ == "__main__":
    main()
