#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_fields.py —— 数据质量自检（只读，不写任何文件）。

回答三个问题：
  1) 每个字段的覆盖率如何？（title/cover/date/actress/...）
  2) 各女优作品收集是否齐全？（按作品数排序，找异常偏少/偏多）
  3) 哪些作品缺关键字段？（title/cover/date/actress 任一缺失即列出）

用法：
    python scripts/audit_fields.py                # 打印完整报告
    python scripts/audit_fields.py --json out.json # 同时导出机器可读报告
    python scripts/audit_fields.py --min-coverage 90  # 只显示覆盖率低于该值的字段

注意：本工具只反映「已抓取多少」，不代表「该女优真实应有总数」。
若要知道「收齐了没」，需另对外部站做基准比对（不在本工具范围）。
"""
import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.path.dirname(HERE)
WORKS_DIR = os.path.join(BASE, "data", "works")
sys.path.insert(0, HERE)
from build_index import load_works  # 复用唯一真相源的加载逻辑

# 关键字段：缺任一即视为「该作品展示不完整」，单独列出
KEY_FIELDS = ["title", "cover", "date", "actress"]

# 全部字段（按展示重要性排序）
ALL_FIELDS = [
    "code", "title", "date", "actress", "series", "maker", "label",
    "duration", "tags", "synopsis", "rating", "rating_count",
    "cover", "source", "source_url", "updated_at",
]


def _has_value(w, fld):
    v = w.get(fld)
    if v is None:
        return False
    if isinstance(v, (str, list)) and len(v) == 0:
        return False
    if isinstance(v, (int, float)) and v == 0:
        return False
    return True


def _report_one(works, code):
    """回答「某部作品什么信息不全」：逐字段列出命中/缺失。"""
    code = code.upper()
    w = works.get(code)
    if not w:
        print("未找到作品：%s（data/works 中无此番号）" % code)
        sys.exit(2)
    print("=== 作品 %s 字段明细 ===" % code)
    for fld in ALL_FIELDS:
        ok = _has_value(w, fld)
        mark = "✅" if ok else "❌ 缺失"
        val = w.get(fld)
        if isinstance(val, (list, dict)):
            val = "%d 项" % len(val)
        elif isinstance(val, str) and len(val) > 40:
            val = val[:40] + "…"
        print("  %-12s %s  %s" % (fld, mark, val if ok else ""))
    miss = [f for f in KEY_FIELDS if not _has_value(w, f)]
    print()
    if miss:
        print("结论：资料不全，缺关键字段 -> %s" % ", ".join(miss))
    else:
        print("结论：关键字段齐全 ✅")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="导出机器可读报告到此路径")
    ap.add_argument("--min-coverage", type=int, default=0,
                    help="只显示覆盖率低于该百分比的字段（0=全部）")
    ap.add_argument("--code", help="只查单个番号的字段明细（如 IPX-005），回答「某部作品什么信息不全」")
    args = ap.parse_args()

    works, dropped = load_works()
    if args.code:
        return _report_one(works, args.code)
    n = len(works)

    # 也能发现 load_works 跳过的文件（缺 code / 解析失败）
    all_files = set(os.path.basename(p) for p in glob.glob(os.path.join(WORKS_DIR, "*.json")))
    loaded_files = set(c + ".json" for c in works.keys())
    skipped = sorted(all_files - loaded_files)

    print("=" * 64)
    print("数据质量审计报告")
    print("=" * 64)
    print("作品总数（含 code 的有效文件）: %d" % n)
    print("被 build_index 跳过的文件       : %d" % len(skipped))
    if skipped:
        for fn in skipped[:10]:
            print("   - %s" % fn)
        if len(skipped) > 10:
            print("   ... 其余 %d 个省略" % (len(skipped) - 10))

    # 1) 字段覆盖率
    print("\n--- 字段覆盖率 ---")
    low = []
    for fld in ALL_FIELDS:
        ok = sum(1 for w in works.values() if _has_value(w, fld))
        pct = (100 * ok // n) if n else 0
        flag = "  <-- 偏低" if pct < args.min_coverage else ""
        if pct < args.min_coverage:
            low.append(fld)
        print("  %-12s %5d/%-5d  %3d%%%s" % (fld, ok, n, pct, flag))

    # 2) 各女优作品数
    print("\n--- 各女优作品数（按多少排序）---")
    by_owner = {}
    for w in works.values():
        o = w.get("actress")
        if not o:
            acts = w.get("actresses") or []
            o = acts[0] if acts else "其他作品"
        by_owner.setdefault(o, 0)
        by_owner[o] += 1
    for name in sorted(by_owner, key=lambda k: -by_owner[k]):
        print("  %-14s %4d 部" % (name, by_owner[name]))

    # 3) 缺关键字段的作品
    print("\n--- 缺关键字段的作品（title/cover/date/actress）---")
    problems = []
    for c, w in sorted(works.items()):
        miss = [f for f in KEY_FIELDS if not _has_value(w, f)]
        if miss:
            problems.append((c, miss, w.get("actress", "")))
    print("共 %d 部缺至少一项关键字段" % len(problems))
    for c, miss, owner in problems[:30]:
        print("  %-14s 缺[%s]  owner=%s" % (c, ",".join(miss), owner or "无"))
    if len(problems) > 30:
        print("   ... 其余 %d 部省略" % (len(problems) - 30))

    # 导出
    if args.json:
        report = {
            "total_works": n,
            "skipped_files": skipped,
            "field_coverage": {
                f: sum(1 for w in works.values() if _has_value(w, f)) for f in ALL_FIELDS
            },
            "by_actress": by_owner,
            "missing_key_field": [
                {"code": c, "missing": m, "owner": o} for c, m, o in problems
            ],
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print("\n已导出报告: %s" % args.json)


if __name__ == "__main__":
    main()
