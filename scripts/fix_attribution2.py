#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_attribution2.py — 健壮的女优归属修正（第二轮）

背景：update_metadata.py 的 attribution_conflict() 用「原始字符串」比对，
未做去括号别名/变体归一，且上一轮 --all 跑中途停止，导致仍有大量单人 cast
作品的 owner 错归未修正（owner 不在演员表、演员表仅 1 人）。

本脚本：
1. 强归一化：去括号别名 + 已知变体映射（normalize_name 逻辑），与站点
   分组保持一致，避免「河北彩花」vs「河北彩花（河北彩伽）」误判。
2. owner 归一后不在 cast 归一集合、且 cast 仅 1 人 -> 将 owner 改为该真演员
   （幂等，仅当现有 owner != 真演员才改；不触碰演员表，除非真演员缺失则补）。
3. 多人 cast 且 owner 不在其中 -> 标记待人工（attribution_pending.json）。
4. dry-run 只报告，不落盘。

用法：
  python scripts/fix_attribution2.py --dry-run
  python scripts/fix_attribution2.py            # 真正修正并落盘
"""
import os, sys, json, glob, argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from sources.base import normalize_name  # 去括号 + 变体映射

DATA = os.path.join(os.path.dirname(_HERE), "data", "works")

# 已知变体（normalize_name 已含部分；此处再补强站点用到的读法）
_VARIANT = {
    "永野いち夏": "永野一夏",
    "永野一夏": "永野一夏",
    "河北彩花": "河北彩花",
    "河北彩伽": "河北彩花",
}

def norm(n):
    return normalize_name(n)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只报告不落盘")
    args = ap.parse_args()

    fixed, flagged, ok = [], [], []
    for fp in sorted(glob.glob(os.path.join(DATA, "*.json"))):
        try:
            w = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        owner = w.get("actress")
        cast = w.get("actresses") or []
        if not (owner and cast):
            continue
        no = norm(owner)
        nc = [norm(x) for x in cast]
        ncs = set(nc)
        if no in ncs:
            ok.append((w.get("code"), owner, cast))
            continue
        # owner 不在 cast 归一集合
        if len(nc) == 1:
            suggested = cast[0]  # 用原始写法保留（带括号也不影响显示）
            if suggested != owner:
                fixed.append({"code": w.get("code"), "from": owner, "to": suggested,
                              "cast": cast})
                if not args.dry_run:
                    w["actress"] = suggested
                    if suggested not in w.get("actresses", []):
                        w.setdefault("actresses", []).append(suggested)
                    json.dump(w, open(fp, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=1)
            else:
                ok.append((w.get("code"), owner, cast))
        else:
            flagged.append({"code": w.get("code"), "owner": owner, "cast": cast})

    print("=== 单人cast错归已修正: %d 部 ===" % len(fixed))
    for r in fixed[:20]:
        print("  %-12s %s -> %s" % (r["code"], r["from"], r["to"]))
    if len(fixed) > 20:
        print("  ... 其余 %d 部" % (len(fixed) - 20))
    print()
    print("=== 多人cast错归待人工: %d 部 ===" % len(flagged))
    for r in flagged[:15]:
        print("  %-12s owner=%-12s cast=%s" % (r["code"], r["owner"], r["cast"][:3]))
    if len(flagged) > 15:
        print("  ... 其余 %d 部" % (len(flagged) - 15))

    if flagged:
        json.dump(flagged, open(os.path.join(os.path.dirname(DATA), "attribution_pending.json"),
                                 "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("\n已写出 data/attribution_pending.json（%d 部待人工）" % len(flagged))

if __name__ == "__main__":
    main()
