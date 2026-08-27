#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_index.py —— 扫描 data/works 下所有作品，生成两份汇总索引：
    1) data/index.json            —— 给程序 / API 用
    2) site/assets/js/data.js     —— window.JAV_DB = {...}，给站点用（支持 file:// 双击打开）

用法：
    python scripts/build_index.py
    python scripts/build_index.py --check   # 只校验数据完整性，不写文件

数据来源（单一扁平布局）：
    - data/works/<番号>.json   ← 唯一规范源（已合并原嵌套库 data/actresses/<女优>/works 的有效作品）

女优归属：
    · 每部作品取 owner = work['actress']，缺则取 work['actresses'][0]
    · 完全没有女优信息的归入「其他作品」聚合女优（保证不丢作品）
    · 女优的 work_count / codes 实时聚合，并从 data/actresses/<名>/profile.json
      合并 avatar/bio/aliases 等档案字段（若存在）。

中文层：data/zh.json（actress_zh / tag_zh）原样带入选定。
站点读 data.js（内联 JSON），所以改完 data/ 一定要重跑本脚本，站点才会更新。

数据安全约定：任何缺 code 字段的文件都会被跳过并在 stdout 告警，绝不静默丢弃
（历史上曾因空 code 互相覆盖而丢失 ~104 部，现已消除根因）。
"""

import argparse
import glob
import json
import os
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTRESSES_DIR = os.path.join(BASE, "data", "actresses")
WORKS_DIR = os.path.join(BASE, "data", "works")
INDEX_JSON = os.path.join(BASE, "data", "index.json")
DATA_JS = os.path.join(BASE, "site", "assets", "js", "data.js")
ZH_JSON = os.path.join(BASE, "data", "zh.json")

OTHER = "其他作品"  # 无主作品的聚合女优名


def load_zh():
    try:
        with open(ZH_JSON, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"actress_zh": {}, "tag_zh": {}}


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _owner_of(w):
    """返回作品的归属女优；都没有则返回 None。"""
    o = w.get("actress")
    if o:
        return o
    acts = w.get("actresses") or []
    return acts[0] if acts else None


def load_works():
    """返回 {code: work}，仅读扁平库 data/works（唯一真相源）。

    缺 code 字段的文件会被跳过并告警，绝不静默丢弃（避免历史上空 code
    互相覆盖丢失作品的回归）。
    """
    works = {}
    dropped = []
    if not os.path.isdir(WORKS_DIR):
        return works, dropped
    for fp in sorted(glob.glob(os.path.join(WORKS_DIR, "*.json"))):
        w = load_json(fp)
        if not w:
            dropped.append((os.path.basename(fp), "解析失败/非 JSON"))
            continue
        c = w.get("code")
        if not c:
            dropped.append((os.path.basename(fp), "缺 code 字段"))
            continue
        works[c] = w
    return works, dropped


def build():
    works, dropped = load_works()

    if dropped:
        print("跳过 %d 个文件（不参与索引，需人工补 code）：" % len(dropped))
        for fn, reason in dropped[:20]:
            print("   - %s  [%s]" % (fn, reason))
        if len(dropped) > 20:
            print("   ... 其余 %d 个省略" % (len(dropped) - 20))

    # 按女优分组
    by_owner = {}
    for code, w in works.items():
        owner = _owner_of(w) or OTHER
        by_owner.setdefault(owner, []).append(w)

    # 预载现有女优档案（avatar / bio / aliases 等）
    profiles = {}
    if os.path.isdir(ACTRESSES_DIR):
        for name in sorted(os.listdir(ACTRESSES_DIR)):
            adir = os.path.join(ACTRESSES_DIR, name)
            if not os.path.isdir(adir):
                continue
            p = load_json(os.path.join(adir, "profile.json")) or {}
            p["name"] = p.get("name") or name
            profiles[name] = p

    actresses = []
    for name in sorted(by_owner):
        works_list = by_owner[name]
        # 同女优内按 code 去重（安全网）
        seen = set()
        uniq = []
        for w in works_list:
            c = w.get("code")
            if c in seen:
                continue
            seen.add(c)
            uniq.append(w)
        uniq.sort(key=lambda x: x.get("code") or "")
        codes = sorted({w.get("code") for w in uniq if w.get("code")})

        meta = profiles.get(name, {"name": name})
        meta["name"] = meta.get("name") or name
        meta["work_count"] = len(uniq)
        meta["codes"] = codes
        meta["works"] = uniq
        actresses.append(meta)

    return actresses


def validate(actresses):
    problems = []
    for a in actresses:
        if not a.get("name"):
            problems.append("女优缺少 name")
        for w in a.get("works", []):
            if not w.get("code"):
                problems.append("%s 下有作品缺 code" % (a.get("name")))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只校验，不写文件")
    args = ap.parse_args()

    actresses = build()
    problems = validate(actresses)

    total_works = sum(a["work_count"] for a in actresses)
    print("聚合：%d 位女优 / %d 部作品" % (len(actresses), total_works))
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
        "zh": load_zh(),
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
    print("已生成：\n  %s\n  %s" % (INDEX_JSON, DATA_JS))


if __name__ == "__main__":
    main()
