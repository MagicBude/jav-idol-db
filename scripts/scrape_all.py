#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scrape_all.py —— 批量抓取所有女优作品元数据，可续跑、可并发。

用法：
    python scripts/scrape_all.py                 # 全量，跳过已抓到(codeav)的
    python scripts/scrape_all.py --force         # 全量重抓（忽略已抓）
    python scripts/scrape_all.py --limit 50      # 先抓 50 个做稳定性测试
    python scripts/scrape_all.py --workers 8     # 调并发数

设计说明：
    - 直接遍历 data/works/*.json（单布局唯一真相源），用每个 work 自身的
      actress 字段作为 actress_hint（保证写回归属正确）。
    - 续跑：已 source=="codeav" 且非 --force 时跳过，避免重复打站。
    - 原 work 的 cover 路径传入，覆盖时不丢占位。
    - 线程池并发（网络 IO 密集型），失败标记 pending 不抛异常。
"""

import os
import sys
import json
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import scrape_codeav as sc  # noqa: E402

DATA_DIR = os.path.join(os.path.dirname(HERE), "data", "works")


def collect():
    tasks = []
    for fn in sorted(os.listdir(DATA_DIR)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(DATA_DIR, fn)
        try:
            with open(path, encoding="utf-8") as f:
                cur = json.load(f)
        except Exception:
            cur = {}
        code = cur.get("code")
        if not code:
            continue
        tasks.append((cur.get("actress") or "", code, cur.get("cover"), cur.get("source")))
    return tasks


def process(name, code, orig_cover, source, force):
    if (not force) and source == "codeav":
        return (code, "skip", None)
    try:
        work = sc.scrape_work(code, actress_hint=name, original_cover=orig_cover)
        sc.save_work(work)
        if work.get("source") == "codeav" and work.get("title"):
            return (code, "ok", None)
        return (code, "pending", None)
    except Exception as e:  # noqa: BLE001
        return (code, "error", str(e)[:200])


def main():
    ap = argparse.ArgumentParser(description="批量抓取 codeav 元数据")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--force", action="store_true", help="重抓已 codeav 的条目")
    ap.add_argument("--limit", type=int, default=0, help="只抓前 N 个（测试用）")
    args = ap.parse_args()

    tasks = collect()
    if args.limit:
        tasks = tasks[: args.limit]
    print(f"待抓 {len(tasks)} 个，workers={args.workers}，force={args.force}")

    stats = {"ok": 0, "pending": 0, "skip": 0, "error": 0}
    done = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [
            ex.submit(process, n, c, oc, src, args.force)
            for (n, c, oc, src) in tasks
        ]
        for fut in as_completed(futures):
            code, status, err = fut.result()
            stats[status] = stats.get(status, 0) + 1
            done += 1
            if status == "error":
                print(f"  [error] {code}: {err}")
            if done % 50 == 0 or done == len(tasks):
                elapsed = time.time() - t0
                print(
                    f"进度 {done}/{len(tasks)}  "
                    f"ok={stats['ok']} pending={stats['pending']} "
                    f"skip={stats['skip']} error={stats['error']}  {elapsed:.1f}s"
                )
    print(
        f"\n完成。ok={stats['ok']} pending={stats['pending']} "
        f"skip={stats['skip']} error={stats['error']}"
    )
    print("记得跑 `python scripts/build_index.py` 重新生成索引。")


if __name__ == "__main__":
    main()
