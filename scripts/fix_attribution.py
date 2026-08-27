# -*- coding: utf-8 -*-
"""按审计结果修复错归（保守策略）。

规则（仅搬高置信，其余进复核队列）：
  - codeav 正确女优 必须 ∈ 我们收录的 5 位女优之一（否则进复核：指向未收录女优）
  - 标题不得像合集/多女优（総集編 / ○名 / 全員 / たち / レズ共演 / ベスト 等）
  - codeav 女优为单一名字（无 、/ 等分隔）
满足以上 → 移动 work.json 到正确女优目录（必要时新建目录+profile），
            并更新 work.actress；若封面是本地图则一并移动。
否则 → 写入 attribution_review.json 复核队列。

用法：
  python scripts/fix_attribution.py --dry-run     # 只统计，不移动
  python scripts/fix_attribution.py               # 执行移动
"""
import os
import sys
import json
import glob
import shutil
import argparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT = os.path.join(BASE, "data", "actresses")
OUR = [d for d in sorted(os.listdir(ACT)) if os.path.isdir(os.path.join(ACT, d))]
OUR_SET = set(OUR)

COMP_RE = __import__("re").compile(
    r"総集編|総集|全員|全裸カタログ|○名|名のJ系|人もの|集め|まとめ|"
    r"ベスト|BEST|極選|名作|名場面|レズビアン|Wレズ|共演|スワップ|交換|"
    r"たちに|たちへ|達の|複数|キス魔|ハーレム|ハーレン"
)


def strip_name(s):
    # "Nia（伊東める）" -> "Nia"；"白桃はな" -> "白桃はな"
    for sep in ("（", "("):
        if sep in s:
            s = s.split(sep)[0]
    return s.strip()


def is_clear_move(codeav_actress, title):
    if not codeav_actress:
        return False, "codeav 无女优"
    if "、" in codeav_actress or "/" in codeav_actress:
        return False, "多女优"
    clean = strip_name(codeav_actress)
    if clean not in OUR_SET:
        return False, f"正确女优未收录({codeav_actress})"
    if COMP_RE.search(title or ""):
        return False, "疑似合集/多女优"
    return True, clean


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rep = json.load(open(os.path.join(BASE, "audit_report.json"), encoding="utf-8"))
    conflicts = rep.get("conflicts", [])
    print(f"审计冲突总数: {len(conflicts)} | 收录女优: {OUR}")

    moves, review = [], []
    for c in conflicts:
        code = c["code"]
        cur = c["dir"]
        ca = c["codeav_actress"]
        title = c.get("title") or ""
        ok, info = is_clear_move(ca, title)
        if ok:
            moves.append((code, cur, info))
        else:
            review.append({"code": code, "current": cur, "codeav": ca,
                           "reason": info, "title": title})

    print(f"\n将移动(高置信): {len(moves)}")
    print(f"进复核队列:     {len(review)}")
    if args.dry_run:
        print("\n--- 抽样将移动 ---")
        for code, cur, dst in moves[:15]:
            print(f"  {code:14s} {cur} -> {dst}")
        print("\n--- 抽样复核 ---")
        for r in review[:15]:
            print(f"  {r['code']:14s} {r['current']} codeav={r['codeav']} [{r['reason']}]")
        return

    # 执行移动
    moved = skipped = 0
    for code, cur, dst in moves:
        src = os.path.join(ACT, cur, "works", code + ".json")
        if not os.path.exists(src):
            skipped += 1
            continue
        dst_works = os.path.join(ACT, dst, "works")
        os.makedirs(dst_works, exist_ok=True)
        if not os.path.exists(os.path.join(ACT, dst, "profile.json")):
            json.dump({"name": dst, "source": "attribution-fix",
                       "updated_at": "2026-08-24"},
                      open(os.path.join(ACT, dst, "profile.json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        dst_file = os.path.join(dst_works, code + ".json")
        if os.path.exists(dst_file):
            skipped += 1
            continue
        w = json.load(open(src, encoding="utf-8"))
        w["actress"] = dst
        # 封面本地图一并移动
        cover = w.get("cover")
        if cover and not str(cover).startswith("http") and os.path.exists(os.path.join(BASE, cover)):
            new_cover = os.path.join("assets", "img", dst, code + ".jpg")
            new_cover_abs = os.path.join(BASE, new_cover)
            os.makedirs(os.path.dirname(new_cover_abs), exist_ok=True)
            shutil.move(os.path.join(BASE, cover), new_cover_abs)
            w["cover"] = new_cover
        json.dump(w, open(dst_file, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        os.remove(src)
        moved += 1

    json.dump(review, open(os.path.join(BASE, "attribution_review.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(f"\n已移动: {moved} | 跳过(冲突/缺失): {skipped}")
    print(f"复核队列已写入: attribution_review.json ({len(review)} 条)")


if __name__ == "__main__":
    main()
