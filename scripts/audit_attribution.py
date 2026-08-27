# -*- coding: utf-8 -*-
"""归属审计：用 codeav 真实女优名逐一比对磁盘目录名，揪出错归作品。

用法：
  python scripts/audit_attribution.py            # 全量审计（可续跑，结果落 audit_report.json）
  python scripts/audit_attribution.py --code IPX-005   # 单码验证

说明：
  - codeav 无数据的作品（pending）无法在此核对，需后续多源链（FANZA/javlibrary/javbus/javdb）
    在用户本机跑时再校验。
  - 仅当 codeav 真实女优名 与 目录名 不一致且都有效时，才标记为候选错归。
"""
import os
import sys
import json
import glob
import argparse
import concurrent.futures as cf

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sources.codeav import CodeavFetcher
from sources.base import canon_code


PLACEHOLDERS = {"女優", "女优", "actor", "actress", ""}


def dir_of(code_path):
    # .../actresses/<姓名>/works/<CODE>.json
    return os.path.basename(os.path.dirname(os.path.dirname(code_path)))


def audit_one(path, fetcher):
    code = os.path.splitext(os.path.basename(path))[0]
    dir_name = dir_of(path)
    try:
        r = fetcher.fetch(code)
    except Exception:
        return None
    if not r:
        return {"code": code, "dir": dir_name, "codeav_actress": None,
                "status": "no_codeav_data"}
    ca = (r.get("actress") or "").strip()
    if ca in PLACEHOLDERS:
        return {"code": code, "dir": dir_name, "codeav_actress": ca,
                "status": "codeav_placeholder"}
    if ca and ca != dir_name:
        return {"code": code, "dir": dir_name, "codeav_actress": ca,
                "status": "CONFLICT", "maker": r.get("maker"),
                "date": r.get("date"), "title": r.get("title")}
    return {"code": code, "dir": dir_name, "codeav_actress": ca,
            "status": "ok"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", help="仅审计单个番号")
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    report_path = os.path.join(ROOT, "audit_report.json")
    if args.code:
        f = CodeavFetcher()
        print(json.dumps(audit_one(
            os.path.join(ROOT, "data", "works", args.code + ".json"),
            f), ensure_ascii=False, indent=2))
        return

    paths = sorted(glob.glob(os.path.join(ROOT, "data", "works", "*.json")))
    print(f"待审计作品数: {len(paths)}")

    conflicts, placeholders, nocodeav, ok = [], [], [], 0
    f = CodeavFetcher()
    with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(audit_one, p, f): p for p in paths}
        done = 0
        for fut in cf.as_completed(futs):
            r = fut.result()
            done += 1
            if r is None:
                continue
            if r["status"] == "CONFLICT":
                conflicts.append(r)
            elif r["status"] == "codeav_placeholder":
                placeholders.append(r)
            elif r["status"] == "no_codeav_data":
                nocodeav.append(r)
            else:
                ok += 1
            if done % 100 == 0:
                print(f"  ...{done}/{len(paths)}")

    out = {
        "total": len(paths),
        "ok": ok,
        "conflicts": conflicts,
        "codeav_placeholder_only": len(placeholders),
        "no_codeav_data": len(nocodeav),
    }
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print("\n================ 归属审计结果 ================")
    print(f"  总作品       : {len(paths)}")
    print(f"  目录一致 OK  : {ok}")
    print(f"  候选错归     : {len(conflicts)}")
    print(f"  codeav无数据 : {len(nocodeav)} (需本机多源链补)")
    print(f"  codeav占位   : {len(placeholders)}")
    if conflicts:
        print("\n--- 候选错归清单（目录名 ≠ codeav真实女优）---")
        for c in conflicts:
            print(f"  {c['code']:14s} 目录={c['dir']}  codeav={c['codeav_actress']}  ({c.get('title','')[:20]})")
    print(f"\n报告已写入: {report_path}")


if __name__ == "__main__":
    main()
