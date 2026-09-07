# -*- coding: utf-8 -*-
"""
update_metadata.py —— 多源自主回补编排器
================================================================
把零散抓取器串成一条可重复跑、幂等的回补链：
    codeav → fanza → javlibrary → [--hard: javmenu, javbus, javdb, javdatabase] → websearch

用法：
  # 回补所有 pending（缺标题/发行日的）作品
  python scripts/update_metadata.py --pending

  # 只回补某几个番号
  python scripts/update_metadata.py --code IPX-005 SNOS-3

  # 全部重跑（只填空缺字段，不覆盖好数据）
  python scripts/update_metadata.py --all

  # 攻克模式：额外启用 javbus / javdb / javdatabase（CF 重，慢）
  python scripts/update_metadata.py --pending --hard

  # 只校验归属、把归属写错的 work 的 actress 字段原地修正
  python scripts/update_metadata.py --pending --fix-attribution

  # 试跑前 10 个（不落盘）
  python scripts/update_metadata.py --pending --limit 10 --dry-run

产出：
  - 直接改写 data/works/<码>.json（幂等合并，单布局唯一真相源）
  - data/pending_review.json  仍 unresolved 的码（交给 agent WebSearch 回填）
  - data/attribution_report.json  归属冲突记录
"""
import os
import sys
import json
import argparse
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from sources import (
    CHAIN, CodeavFetcher, FanzaFetcher, JavlibraryFetcher,
    JavmenuFetcher, JavbusFetcher, JavdbFetcher, JavdatabaseFetcher,
    WebSearchFetcher,
    canon_code, merge_work, attribution_conflict,
)
from sources.base import _is_empty

DATA = os.path.join(ROOT, "data", "works")


def collect_targets(args):
    targets = []  # (actress_hint, code, path)
    if args.code:
        for c in args.code:
            std = canon_code(c)
            p = os.path.join(DATA, f"{std}.json")
            hint = None
            if os.path.exists(p):
                try:
                    hint = json.load(open(p, encoding="utf-8")).get("actress")
                except Exception:
                    pass
            targets.append((hint, std, p if os.path.exists(p) else None))
        return targets

    for fn in sorted(os.listdir(DATA)):
        if not fn.endswith(".json"):
            continue
        std = fn[:-5]
        p = os.path.join(DATA, fn)
        try:
            w = json.load(open(p, encoding="utf-8"))
        except Exception:
            targets.append((None, std, p))
            continue
        hint = w.get("actress")
        if args.missing:
            # 只处理指定字段为空的作品（如 --missing series 攻克系列缺口）
            if _is_empty(w.get(args.missing)):
                targets.append((hint, std, p))
            continue
        if args.all:
            targets.append((hint, std, p))
        elif args.pending:
            title = (w.get("title") or "").strip()
            src = w.get("source")
            if not title or src in (None, "pending"):
                targets.append((hint, std, p))
    return targets


def build_chain(use_hard):
    chain = [CodeavFetcher(), FanzaFetcher(), JavlibraryFetcher()]
    if use_hard:
        # javmenu 静态可达（无 CF），排在 CF 重源前面先跑
        chain += [JavmenuFetcher(), JavbusFetcher(), JavdbFetcher(), JavdatabaseFetcher()]
    chain.append(WebSearchFetcher())
    return chain


def build_chain_from_args(args):
    if args.sources:
        name_map = {
            "codeav": CodeavFetcher, "fanza": FanzaFetcher,
            "javlibrary": JavlibraryFetcher, "javmenu": JavmenuFetcher,
            "javbus": JavbusFetcher,
            "javdb": JavdbFetcher, "javdatabase": JavdatabaseFetcher,
            "websearch": WebSearchFetcher,
        }
        chain = []
        for s in args.sources.split(","):
            s = s.strip()
            if s in name_map:
                chain.append(name_map[s]())
        if chain:
            return chain
    return build_chain(args.hard)


def _detect_indent(path):
    """探测既有文件的缩进空格数（data/works 历史上有 indent=1 / indent=2 并存）。"""
    try:
        raw = open(path, "rb").read(8192)
    except Exception:
        return 2
    for line in raw.split(b"\n"):
        if line[:1] in (b" ", b"\t"):
            lead = len(line) - len(line.lstrip(b" \t"))
            if lead >= 1:
                return lead
    return 2


def _save_work(path, data):
    """落盘单个作品：保留原缩进 + 强制 LF，避免整份重写噪声。"""
    indent = _detect_indent(path)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", nargs="*", help="指定番号")
    ap.add_argument("--pending", action="store_true", help="只处理缺标题/待补的")
    ap.add_argument("--all", action="store_true", help="全部重跑（填空缺字段）")
    ap.add_argument("--hard", action="store_true", help="启用 javmenu/javbus/javdb（攻克模式）")
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 个")
    ap.add_argument("--dry-run", action="store_true", help="不落盘")
    ap.add_argument("--fix-attribution", action="store_true", help="自动搬移放错目录的作品")
    ap.add_argument("--no-websearch", action="store_true", help="禁用 websearch 兜底")
    ap.add_argument("--sources", default="", help="仅用指定源(逗号分隔)，如 codeav,javlibrary")
    ap.add_argument("--missing", default="",
                    help="只处理指定字段为空的作品（如 series），与 --all 互斥、用于攻克特定缺口")
    args = ap.parse_args()

    if not (args.code or args.pending or args.all or args.missing):
        ap.error("需指定 --code / --pending / --all / --missing 之一")

    targets = collect_targets(args)
    if args.limit:
        targets = targets[: args.limit]
    print(f"[目标] {len(targets)} 个作品待回补", flush=True)

    chain = build_chain_from_args(args)
    if args.no_websearch and isinstance(chain[-1], WebSearchFetcher):
        chain = chain[:-1]

    stats = {"total": len(targets), "filled": 0, "still_pending": 0,
             "attrib_moved": 0, "attrib_flagged": 0, "by_source": {}}
    pending_review = []
    attrib_report = []

    for idx, (dir_actress, std, path) in enumerate(targets, 1):
        print(f"\n[{idx}/{len(targets)}] {std}" + (f"  (dir={dir_actress})" if dir_actress else "  (未归档)"), flush=True)
        existing = {}
        if path and os.path.exists(path):
            try:
                existing = json.load(open(path, encoding="utf-8"))
            except Exception:
                existing = {}

        filled_from = None
        work_changed = False   # 只有真变更才落盘，避免未命中文件被无脑重写产生伪 diff
        for fetcher in chain:
            try:
                res = fetcher.fetch(std, hint=dir_actress)
            except Exception as e:
                print(f"    [{fetcher.name}] ERR {e}", flush=True)
                continue
            if not res:
                continue
            changed = merge_work(existing, res)
            if changed:
                work_changed = True
                filled_from = fetcher.name
                stats["by_source"][fetcher.name] = stats["by_source"].get(fetcher.name, 0) + 1
                print(f"    [{fetcher.name}] + " +
                      (res.get("title") or "")[:40] +
                      (f" | {res.get('date')}" if res.get("date") else ""), flush=True)
                # 拿到标题即视为可用，停止链式（避免无谓的慢源）
                if (existing.get("title") or "").strip():
                    break

        if not (existing.get("title") or "").strip():
            stats["still_pending"] += 1
            pending_review.append({"code": std, "dir": dir_actress})
            print(f"    [未解决] 写入 pending_review", flush=True)
        else:
            if filled_from:
                stats["filled"] += 1

        # 归属校验
        fetched_actresses = list(existing.get("actresses") or [])
        if dir_actress and fetched_actresses:
            conflict, suggested = attribution_conflict(dir_actress, fetched_actresses)
            if conflict:
                rec = {"code": std, "dir": dir_actress, "fetched": fetched_actresses,
                       "suggested": suggested}
                attrib_report.append(rec)
                if suggested and args.fix_attribution and path:
                    # 单布局下归属直接体现在 work 的 actress 字段，原地修正即可
                    existing["actress"] = suggested
                    if suggested not in existing.get("actresses", []):
                        existing.setdefault("actresses", []).append(suggested)
                    work_changed = True
                    stats["attrib_moved"] += 1
                    print(f"    [归属修正] {dir_actress} → {suggested}", flush=True)
                else:
                    stats["attrib_flagged"] += 1
                    print(f"    [归属冲突] dir={dir_actress} vs fetched={fetched_actresses}", flush=True)

        # 落盘（仅在有真实变更时）
        if work_changed and path and os.path.exists(path) and not args.dry_run:
            _save_work(path, existing)

    # 收尾
    for f in chain:
        try:
            f.close()
        except Exception:
            pass

    if pending_review and not args.dry_run:
        json.dump(pending_review, open(os.path.join(ROOT, "data", "pending_review.json"),
                                        "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)
    if attrib_report and not args.dry_run:
        json.dump(attrib_report, open(os.path.join(ROOT, "data", "attribution_report.json"),
                                       "w", encoding="utf-8", newline="\n"),
                  ensure_ascii=False, indent=1)

    print("\n================ 回补统计 ================")
    print(f"  目标总数     : {stats['total']}")
    print(f"  成功补全     : {stats['filled']}")
    print(f"  仍 pending   : {stats['still_pending']}")
    print(f"  归属搬移     : {stats['attrib_moved']}")
    print(f"  归属待人工   : {stats['attrib_flagged']}")
    print(f"  各源命中     : {stats['by_source']}")
    print("==========================================")


if __name__ == "__main__":
    main()
