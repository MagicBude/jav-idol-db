# -*- coding: utf-8 -*-
"""从 codeav 重抓缺失/损坏的封面 URL，统一为 DMM 等外链（不本地化）。

只处理 cover 非 http 的作品（即指向 site/assets/img 的本地死链）。
策略：用 CodeavFetcher 取 codeav 上的 cover_url；
  - 拿到 http(s) 地址 -> 写入 cover
  - 拿不到 -> cover 置 null（前端占位兜底）
其余字段原样保留。

用法:
  python scripts/repair_covers.py            # 全量修复
  python scripts/repair_covers.py --dry-run  # 仅统计，不写盘
"""
import os
import sys
import json
import glob
import argparse
import concurrent.futures as cf

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))  # 让 sources 成为包
from sources.codeav import CodeavFetcher  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT = os.path.join(BASE, "data", "actresses")


def is_local(v):
    return not (v and str(v).startswith("http"))


def collect_local():
    out = []
    for d in os.listdir(ACT):
        wd = os.path.join(ACT, d, "works")
        if not os.path.isdir(wd):
            continue
        for fn in glob.glob(os.path.join(wd, "*.json")):
            w = json.load(open(fn, encoding="utf-8"))
            if is_local(w.get("cover")):
                out.append((fn, w.get("code")))
    return out


def fetch_code(code):
    try:
        r = CodeavFetcher().fetch(code)
        cov = (r or {}).get("cover")
        if cov and str(cov).startswith("http"):
            return cov
    except Exception:
        pass
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = collect_local()
    print(f"待修复(本地/缺失封面): {len(items)} 个")

    if args.dry_run:
        codes = [c for _, c in items]
        print("样本:", codes[:10])
        return

    recovered = nulled = 0
    files_changed = []

    def work(item):
        fn, code = item
        cov = fetch_code(code)
        return fn, cov

    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        for fn, cov in ex.map(work, items):
            w = json.load(open(fn, encoding="utf-8"))
            if cov:
                w["cover"] = cov
                recovered += 1
            else:
                w["cover"] = None
                nulled += 1
            json.dump(w, open(fn, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            files_changed.append(fn)

    print(f"已修复: 重抓到外链 {recovered} 个 | 置 null(占位) {nulled} 个")
    print(f"改动文件: {len(files_changed)} 个")


if __name__ == "__main__":
    main()
