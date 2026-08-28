# -*- coding: utf-8 -*-
"""
enrich_gaps.py —— 用 codeav 回填「资料不全」作品的缺失字段。

设计要点：
- 只处理 build 期被标记 incomplete 的作品（缺 title/cover/date/actress 任一）。
- 客观字段（标题/日期/封面/厂牌/系列/标签/简介/评分/导演等）缺失即从 codeav 补，
  不覆盖已有值。
- `actress` 例外：只在本片 codeav 女优属于「精选女优名单」（data/actresses/ 下
  真实目录）时才补，避免把非精选女优写进精选库、污染站点分组。

用法：
    python scripts/enrich_gaps.py            # 真实回填
    python scripts/enrich_gaps.py --dry-run  # 只统计可补数量，不写文件
"""
import glob
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sources.codeav import CodeavFetcher  # noqa: E402

WORKS_DIR = os.path.join(HERE, "..", "data", "works")
KEY_FIELDS = ["title", "cover", "date", "actress"]
OBJECTIVE_FIELDS = [
    "title", "date", "cover", "maker", "label", "series",
    "duration", "tags", "synopsis", "rating", "rating_count", "director",
]


def _has(v):
    if v is None:
        return False
    if isinstance(v, (str, list)) and len(v) == 0:
        return False
    if isinstance(v, (int, float)) and v == 0:
        return False
    return True


def curated_actresses():
    base = os.path.join(HERE, "..", "data", "actresses")
    out = set()
    if not os.path.isdir(base):
        return out
    for name in os.listdir(base):
        p = os.path.join(base, name, "profile.json")
        # 排除聚合项（其目录通常也含 profile，但名字是 S1オールスター/其他作品）
        if name in ("S1オールスター", "其他作品"):
            continue
        if os.path.isfile(p):
            out.add(name)
    return out


def main():
    dry = "--dry-run" in sys.argv
    fetcher = CodeavFetcher()
    curated = curated_actresses()

    files = sorted(glob.glob(os.path.join(WORKS_DIR, "*.json")))
    gaps = []
    for fp in files:
        try:
            w = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        if any(not _has(w.get(k)) for k in KEY_FIELDS):
            gaps.append((fp, w))

    print("缺关键字段作品: %d" % len(gaps))
    print("精选女优名单(%d): %s" % (len(curated), " ".join(sorted(curated))))

    filled = Counter()
    actress_curated_hit = 0
    actress_noncurated = 0
    changed = 0
    unreachable = 0

    for fp, w in gaps:
        code = w.get("code")
        r = fetcher.fetch(code) if code else None
        if not r:
            unreachable += 1
            continue
        did = False
        for f in OBJECTIVE_FIELDS:
            if not _has(w.get(f)) and _has(r.get(f)):
                w[f] = r[f]
                filled[f] += 1
                did = True
        ca = r.get("actress")
        if not _has(w.get("actress")) and _has(ca):
            if ca in curated:
                w["actress"] = ca
                filled["actress"] += 1
                actress_curated_hit += 1
                did = True
            else:
                actress_noncurated += 1
        if did:
            changed += 1
            if not dry:
                json.dump(w, open(fp, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=2)

    print()
    print("=== 回填结果%s ===" % ("（dry-run，未写文件）" if dry else ""))
    for f in ["title", "date", "cover", "maker", "label", "series",
              "duration", "tags", "synopsis", "rating", "rating_count", "director", "actress"]:
        if filled.get(f):
            print("  %-12s +%d" % (f, filled[f]))
    print("  修改文件数: %d" % changed)
    print("  codeav 不可达/无结果: %d" % unreachable)
    print("  女优命中精选(已补): %d  女优非精选(跳过): %d"
          % (actress_curated_hit, actress_noncurated))

    # 剩余缺口
    remain = len(gaps) - changed
    print()
    print("回填后预计剩余缺口作品: %d（原 %d）" % (remain, len(gaps)))


if __name__ == "__main__":
    main()
