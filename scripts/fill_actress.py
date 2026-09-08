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
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources.minnanoav import MinnanoavActressFetcher  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACTRESS_DIR = os.path.join(ROOT, "data", "actresses")
ALIAS_FILE = os.path.join(ROOT, "data", "actress", "alias.json")

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


def index_actress_names():
    """站点索引里的全部女优名（137 位），用于为无目录女优建档。"""
    idx = os.path.join(ROOT, "data", "index.json")
    with open(idx, encoding="utf-8") as f:
        return [a["name"] for a in json.load(f).get("actresses", [])]


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
    """LF + indent=2 写盘（仓库规范）；目录不存在则创建。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def fill_baike(names, apply=False):
    """百度百科补充：候选名直连试错，只补空档 + 中文名/中文别名/词条链接。"""
    from sources.baike import BaikeFetcher

    # Baike 侧可补空档的字段（existing 优先铁律同样适用）
    BAIKE_FILL = [
        "birthdate", "height", "bust", "waist", "hips", "cup",
        "birthplace", "blood_type",
    ]

    def _derive(name):
        """派生候选：々展开 → 繁/日汉字转简体 → JP 特有字映射。"""
        out = [name]
        # 々 展开为前一字符：奈々 → 奈奈
        exp = re.sub(r"(.)々", lambda m: m.group(1) + m.group(1), name)
        if exp != name:
            out.append(exp)
        base = exp
        try:
            from zhconv import convert
            simp = convert(base, "zh-cn")
            if simp != base:
                out.append(simp)
            base = simp
        except ImportError:
            pass
        # zhconv 不覆盖的日文汉字（实测：郷/瀬/戸 均保留日体）
        for src, dst in (("郷", "乡"), ("瀬", "濑"), ("戸", "户"), ("槇", "槙")):
            if src in base:
                base = base.replace(src, dst)
        if base != out[-1]:
            out.append(base)
        return out

    with open(ALIAS_FILE, encoding="utf-8") as f:
        clusters = json.load(f)

    def candidates_for(name, profile):
        """候选词条名：派生名 → alias.json 簇成员 → minnano/中文別名。"""
        cands = _derive(name)
        if name in clusters:
            cands += clusters[name]
        else:
            for v in clusters.values():
                if name in v:
                    cands += v
                    break
        cands += profile.get("aliases") or []
        cands += profile.get("aliases_zh") or []
        seen, out = set(), []
        for c in cands:
            if c and c not in seen:
                seen.add(c)
                out.append(c)
        return out

    fetcher = BaikeFetcher()
    stats = {"hit": 0, "miss": 0, "changed": 0}
    try:
        for name in names:
            existing, path = load_profile(name)
            hit = None
            for cand in candidates_for(name, existing):
                url, html = fetcher.fetch(cand)
                if not html:
                    continue
                from sources.baike import parse_baike_html
                info = parse_baike_html(html)
                if info:
                    hit = (cand, url, info)
                    break
            if not hit:
                print(f"[MISS] {name}: baike 无词条")
                stats["miss"] += 1
                continue
            cand, url, info = hit
            stats["hit"] += 1
            merged = dict(existing)
            changed = []
            for field in BAIKE_FILL:
                val = info.get(field)
                if val and (merged.get(field) in (None, "", [])):
                    merged[field] = val
                    changed.append(field)
            for field in ("name_zh", "aliases_zh", "notable_work", "real_name"):
                val = info.get(field)
                if val and not merged.get(field):
                    merged[field] = val
                    changed.append(field)
            if url and not merged.get("baike_url"):
                merged["baike_url"] = url
                changed.append("baike_url")
            # 中文名不应与目录名相同（如 永野一夏 词条名=永野一夏）
            if merged.get("name_zh") == name:
                # 仍保留（显示一致），但不算变更点
                changed = [c for c in changed if c != "name_zh"] or changed
            if not changed:
                print(f"[KEEP] {name}: baike 命中（{cand}）但无空档可补")
                continue
            stats["changed"] += 1
            if apply:
                save_profile(path, merged)
                print(f"[FILL] {name}: 命中「{cand}」 +{', '.join(changed)}")
            else:
                print(f"[DRY ] {name}: 命中「{cand}」 将补 {', '.join(changed)}")
    finally:
        fetcher.close()
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\n== baike {mode} == 命中 {stats['hit']} / 未命中 {stats['miss']} / "
          f"补全 {stats['changed']}")


def main():
    ap = argparse.ArgumentParser(description="minnanoav/baike 女优档案补全")
    ap.add_argument("--apply", action="store_true", help="正式写盘（默认 dry-run）")
    ap.add_argument("--name", help="只处理指定女优（目录名）")
    ap.add_argument("--query", help="检索名覆盖（目录名与 minnano 正式名不一致时用，"
                                     "如目录 永野一夏 / 正式名 永野いち夏），须与 --name 同用")
    ap.add_argument("--baike", action="store_true",
                    help="改用百度百科源补档（出生地/中文名/代表作等，Playwright 移动版）")
    ap.add_argument("--all", action="store_true",
                    help="遍历站点索引全部女优（含无目录者，自动建档）")
    ap.add_argument("--only-missing", action="store_true",
                    help="只处理无档案/关键字段为空的女优（birthdate/height/debut_work 全空）")
    ap.add_argument("--sync-alias", action="store_true",
                    help="把各 profile 的 minnano 別名并入 data/actress/alias.json 对应簇")
    ap.add_argument("--rebuild", action="store_true", help="完成后重建站点索引")
    args = ap.parse_args()
    if args.query and not args.name:
        ap.error("--query 必须与 --name 同用")

    if args.all:
        names = index_actress_names()
    else:
        names = sorted(
            d for d in os.listdir(ACTRESS_DIR)
            if os.path.isdir(os.path.join(ACTRESS_DIR, d))
        )
    if args.name:
        names = [n for n in names if n == args.name]
        if not names:
            print("未找到女优目录:", args.name)
            sys.exit(1)
    if args.only_missing:
        key_fields = ("birthdate", "height", "debut_work")
        before = len(names)
        names = [n for n in names
                 if not any(load_profile(n)[0].get(f) for f in key_fields)]
        print(f"--only-missing: {before} → {len(names)} 位待补")

    if args.baike:
        fill_baike(names, apply=args.apply)
        if args.rebuild and args.apply:
            import subprocess
            subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "build_index.py")],
                           check=True)
        return

    if args.sync_alias:
        sync_alias(apply=args.apply)
        return

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


def sync_alias(apply=False):
    """把 profile.json 里的 minnano 別名并入 alias.json 对应簇。

    规则：
    - 女优必须在 alias.json 已有簇（key 或成员），否则跳过并提示（不擅自建簇）
    - 目标名若是其他簇的 canonical key → 跳过（防跨簇污染）
    - 纯 ASCII 且 <5 字符的別名跳过（如 MOE，极易与其他数据撞名）
    """
    with open(ALIAS_FILE, encoding="utf-8") as f:
        alias = json.load(f)

    def find_cluster(name):
        if name in alias:
            return alias[name]
        for v in alias.values():
            if name in v:
                return v
        return None

    names = sorted(
        d for d in os.listdir(ACTRESS_DIR)
        if os.path.isdir(os.path.join(ACTRESS_DIR, d))
    )
    total = 0
    for name in names:
        profile, _ = load_profile(name)
        cluster = find_cluster(name)
        if cluster is None:
            print(f"[SKIP] {name}: alias.json 无此簇")
            continue
        added = []
        for al in profile.get("aliases") or []:
            if al == name or al in cluster or al in alias:
                continue
            if len(al) < 5 and al.isascii():
                print(f"[SKIP] {name}: 別名 {al!r} 过短（ASCII），防撞名不并入")
                continue
            cluster.append(al)
            added.append(al)
        if added:
            total += len(added)
            print(f"[ALIAS] {name}: +{', '.join(added)}")
        else:
            print(f"[KEEP] {name}: 簇已完整")
    if not total:
        print("alias.json 无需变更")
        return
    if apply:
        with open(ALIAS_FILE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(alias, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"已写入 {ALIAS_FILE}（共 +{total} 个別名）")
    else:
        print(f"DRY-RUN：将新增 {total} 个別名（--apply 落盘）")


if __name__ == "__main__":
    main()
