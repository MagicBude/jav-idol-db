# -*- coding: utf-8 -*-
"""
fill_actress.py —— 用 minnano-av 批量补全女优档案
============================================================================
遍历 data/actresses/<名>/ 目录，用 minnanoav 源抓取档案并**只补空档**：

合并策略（铁律：existing 非空值永远优先，不覆盖人工/researched 值）：
  - 字段为 null / 缺失 / 空串 → 用 minnano 值填充
  - aliases → 并集合并（去重，不删已有）
  - avatar 已有 → 不动；minnano 头图存为 photo_url 备用
  - 有任何变更才写盘（防 EOF 换行伪 diff），写盘 LF + 保留 2 空格缩进
  - 记录 minnano_url（档案页链接，站点可作外链）

用法：
  python scripts/fill_actress.py                # dry-run 预览全部
  python scripts/fill_actress.py --apply        # 正式写盘
  python scripts/fill_actress.py --name 楓カレン # 只跑一人
  python scripts/fill_actress.py --apply --rebuild  # 顺带重建站点索引
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources.minnanoav import MinnanoavActressFetcher  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTRESS_DIR = os.path.join(ROOT, "data", "actresses")

# minnano 字段 → profile.json 字段（同名直填）
FILL_FIELDS = [
    "birthdate", "height", "bust", "waist", "hips", "cup",
    "agency", "hobby", "blog", "official_site", "debut_date",
    "debut_work", "career_periods", "reading", "roman_name",
    "birthplace", "blood_type",  # minnano 通常没有，有就补
]


def load_profile(name):
    """读 profile.json；不存在则返回最小骨架。"""
    path = os.path.join(ACTRESS_DIR, name, "profile.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f), path
    return {"name": name}, path


def merge_profile(existing, fetched):
    """只补空档，返回 (merged, changed_keys)。"""
    merged = dict(existing)
    changed = []

    def is_empty(v):
        return v is None or v == "" or v == []

    for field in FILL_FIELDS:
        val = fetched.get(field)
        if val and is_empty(merged.get(field)):
            merged[field] = val
            changed.append(field)

    # aliases 并集
    new_aliases = [a for a in (fetched.get("aliases") or [])
                   if a and a not in (merged.get("aliases") or [])]
    if new_aliases:
        merged["aliases"] = (merged.get("aliases") or []) + new_aliases
        changed.append("aliases")

    # 头图：avatar 有则不动；photo_url 作为备用字段
    if fetched.get("photo_url") and not merged.get("photo_url"):
        merged["photo_url"] = fetched["photo_url"]
        if not merged.get("avatar"):
            merged["avatar"] = fetched["photo_url"]
            changed.append("avatar")
        changed.append("photo_url")

    # 档案页外链
    if fetched.get("minnano_url") and not merged.get("minnano_url"):
        merged["minnano_url"] = fetched["minnano_url"]
        changed.append("minnano_url")

    if changed:
        merged["updated_at"] = "2026-09-07"
    return merged, changed


def save_profile(path, data):
    """LF + indent=2 写盘（仓库规范）。"""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main():
    ap = argparse.ArgumentParser(description="minnanoav 女优档案补全")
    ap.add_argument("--apply", action="store_true", help="正式写盘（默认 dry-run）")
    ap.add_argument("--name", help="只处理指定女优（目录名）")
    ap.add_argument("--query", help="检索名覆盖（目录名与 minnano 正式名不一致时用，"
                                     "如目录 永野一夏 / 正式名 永野いち夏），须与 --name 同用")
    ap.add_argument("--rebuild", action="store_true", help="完成后重建站点索引")
    args = ap.parse_args()
    if args.query and not args.name:
        ap.error("--query 必须与 --name 同用")

    names = sorted(
        d for d in os.listdir(ACTRESS_DIR)
        if os.path.isdir(os.path.join(ACTRESS_DIR, d))
    )
    if args.name:
        names = [n for n in names if n == args.name]
        if not names:
            print("未找到女优目录:", args.name)
            sys.exit(1)

    fetcher = MinnanoavActressFetcher()
    stats = {"hit": 0, "miss": 0, "changed": 0, "error": 0}
    for name in names:
        existing, path = load_profile(name)
        query = args.query if args.query and name == args.name else name
        try:
            fetched = fetcher.lookup_actress(query)
        except Exception as e:
            print(f"[ERR ] {name}: {type(e).__name__} {e}")
            stats["error"] += 1
            continue
        if not fetched:
            print(f"[MISS] {name}: minnanoav 未命中（query={query}）")
            stats["miss"] += 1
            continue
        stats["hit"] += 1
        merged, changed = merge_profile(existing, fetched)
        if not changed:
            print(f"[KEEP] {name}: 无空档可补")
            continue
        stats["changed"] += 1
        if args.apply:
            save_profile(path, merged)
            print(f"[FILL] {name}: +{', '.join(changed)}")
        else:
            print(f"[DRY ] {name}: 将补 {', '.join(changed)}")

    mode = "APPLY" if args.apply else "DRY-RUN"
    print(f"\n== {mode} == 命中 {stats['hit']} / 未命中 {stats['miss']} / "
          f"补全 {stats['changed']} / 错误 {stats['error']}")
    if args.rebuild and args.apply:
        import subprocess
        subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_index.py")],
                       check=True)


if __name__ == "__main__":
    main()
