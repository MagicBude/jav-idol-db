# -*- coding: utf-8 -*-
"""
reconcile_attribution.py —— 归属重对账（稳健版，保护种子）

背景：初始数据集把作品塞进 5 位女优目录时混入错归（同一部片同时出现在
两个目录、或主演其实是别的女优）。本脚本用 codeav 的「主演」字段作为
辅助真相，重新判定归属，但采取「保守保护种子」策略：

  - codeav 主演 ∈ 我们收录的女优（归一化）→ 归属该女优目录（移动+去重）
  - codeav 主演 ∉ 我们收录的女优（含 codeav 自身错归 / 真·未收录女优 / 查无）
        → 保护种子：去重后保留在原目录（记复核队列，不删除、不隔离）

为什么保守：codeav 数据偶有错误（实测 IPX-001 被错归为妃月るい，实为
桃乃木かな出道作）。盲信 codeav 会丢失正确种子。因此「主演∉我们」一律
不搬不删，只记 review 待人工 / 全量抓取时再决。

规则：
  - 每个 code 在最终数据里只保留一份（重复去重，保留首份目录）
  - 幂等：重跑安全；--dry-run 只报告不改动；--apply 先备份
  - 不创建 _quarantine（避免丢失数据），复核项写入 attribution_review.json

用法：
  python scripts/reconcile_attribution.py            # 默认 dry-run
  python scripts/reconcile_attribution.py --apply    # 实际执行
"""
import os
import sys
import json
import shutil
import time
import argparse
from collections import defaultdict, Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT = os.path.join(ROOT, "data", "actresses")
REVIEW = os.path.join(ROOT, "attribution_review.json")
BACKUP = os.path.join(ROOT, "data", "_backup_pre_reconcile")

# 我们收录的女优（目录名）。后续全量抓取会动态扩充，这里仅覆盖当前种子。
OUR_DIRS = ["桃乃木かな", "永野一夏", "河北彩花", "白桃はな", "石川澪"]

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sources.base import normalize_name  # noqa: E402


def load_all_codes():
    """返回 {code: [(dir, filepath), ...]}"""
    code_map = defaultdict(list)
    for d in OUR_DIRS:
        wd = os.path.join(ACT, d, "works")
        if not os.path.isdir(wd):
            continue
        for f in os.listdir(wd):
            if f.endswith(".json"):
                code_map[f[:-5]].append((d, os.path.join(wd, f)))
    return code_map


def fetch_codeav_primary(code):
    """取 codeav 主演，返回归一化名或 None（含限流退避）"""
    for attempt in range(2):
        try:
            from sources.codeav import CodeavFetcher
            f = CodeavFetcher()
            r = f.fetch(code)
            if not r:
                if attempt == 0:
                    time.sleep(2)  # 限流/网络抖动，退避重试
                    continue
                return None
            return normalize_name(r.get("actress") or "")
        except Exception:
            if attempt == 0:
                time.sleep(2)
                continue
            return None
    return None


def backup_once():
    if os.path.isdir(BACKUP):
        return
    os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
    shutil.copytree(ACT, BACKUP)
    print(f"  已备份 data/actresses -> {os.path.relpath(BACKUP, ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际执行移动/去重（默认 dry-run）")
    args = ap.parse_args()
    apply = args.apply

    code_map = load_all_codes()
    our_norm = {normalize_name(d): d for d in OUR_DIRS}

    cache_path = os.path.join(ROOT, "data", "_codeav_primary_cache.json")
    cache = {}
    if os.path.isfile(cache_path):
        try:
            cache = json.load(open(cache_path, encoding="utf-8"))
        except Exception:
            cache = {}
    # 清掉限流期产生的假 None，让它们重查
    stale_none = [k for k, v in cache.items() if v is None]
    for k in stale_none:
        del cache[k]
    if stale_none:
        print(f"  清除限流期假 None 缓存 {len(stale_none)} 条，将重查")

    def get_primary(code):
        if code in cache:
            return cache[code]
        val = fetch_codeav_primary(code)
        cache[code] = val
        if len(cache) % 30 == 0:
            json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(0.4)  # 温和限速，避免触发 codeav 限流
        return val

    print(f"{'APPLY' if apply else 'DRY-RUN'}  共 {len(code_map)} 个唯一 code")
    if apply:
        backup_once()

    owner_counts = Counter()
    moved = 0
    review = []
    clear_moved = 0   # 明确错归已修正
    kept_review = 0   # 保护种子记复核

    for code, entries in sorted(code_map.items()):
        primary = get_primary(code)
        owner = our_norm.get(primary) if primary else None
        dirs = [e[0] for e in entries]

        if owner:
            # 明确归该女优：移动过去，删其他目录副本（去重+修正错归）
            keep_path = next((p for d, p in entries if d == owner), entries[0][1])
            for d, p in entries:
                if d == owner:
                    owner_counts[owner] += 1
                else:
                    if apply:
                        os.remove(p)
                    moved += 1
                    clear_moved += 1
        else:
            # 主演∉我们（codeav错归 / 真未收录 / 查无）：保护种子
            # 去重：保留首份目录，删其余副本
            for d, p in entries[1:]:
                if apply:
                    os.remove(p)
                moved += 1
            keep_dir = entries[0][0]
            owner_counts[keep_dir] += 1
            kept_review += 1
            review.append({
                "code": code,
                "current_dirs": dirs,
                "codeav_primary": primary,
                "reason": ("no_codeav_data" if primary is None
                           else "primary_not_ours:" + primary),
                "status": "kept_seed_needs_review",
            })

    json.dump(cache, open(cache_path, "w", encoding="utf-8"), ensure_ascii=False)
    if apply:
        json.dump(review, open(REVIEW, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("---- 结果 ----")
    for k, v in sorted(owner_counts.items(), key=lambda x: -x[1]):
        print(f"  {k:14s} {v}")
    print(f"  去重/移动副本: {moved}  (其中明确错归修正: {clear_moved})")
    print(f"  保护种子记复核: {kept_review}  (复核队列 {len(review)} 条)")
    if not apply:
        print("\n（dry-run，未改动文件。加 --apply 执行）")


if __name__ == "__main__":
    main()
