#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_attribution2.py — 女优归属修正（安全版）

背景
----
update_metadata.py 的 attribution_conflict() 早期用「原始字符串」比对，未做
去括号别名/变体归一，导致「河北彩花」vs「河北彩花（河北彩伽）」被误报冲突。
本脚本用强归一化（normalize_name）重判。

⚠️ 历史事故（2026-09-01，勿重演）
--------------------------------
旧版本曾在默认情况下直接把 23 部作品的归属从「用户 115 文件名」改成 codeav 的
JSON-LD actor 单例，例如 PIYO-117：
    "actress": "白桃はな", "source": "filename"   →   "actress": "波多野結衣"
而 `source` 仍停留在 "filename"，形成**溯源说谎**。

根因：codeav 按设计只返回 1 个女优（共演作品只报主演）。因此
「cast 只有 1 人且与 owner 不同」极可能是误判，**不能据此改归属**。

安全策略（本版）
---------------
1. **默认只读**：不加 --apply 一律只报告，不写任何文件。
2. **信任源保护**：owner 的 source 属于可信来源（用户文件名 / 人工修正 /
   网页搜索人工确认）时，即便加了 --apply 也**拒绝改动**，只会列入待人工。
   可信来源见 TRUSTED_SOURCES；--force 可强行突破（不推荐）。
3. **溯源同步**：确需搬移时，`source` 与 `actress` 一起更新，杜绝说谎。

用法
----
  python scripts/fix_attribution2.py             # 只读报告（默认，安全）
  python scripts/fix_attribution2.py --apply     # 仅搬移抓取器来源的归属
  python scripts/fix_attribution2.py --apply --force  # 连可信源也搬（危险）
"""
import os
import sys
import json
import glob
import argparse

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
from sources.base import normalize_name  # 去括号 + 变体映射

DATA = os.path.join(os.path.dirname(_HERE), "data", "works")

# 归属「可信来源」：出自用户自己的归档命名或人工确认。
# 项目铁律：115 文件名是唯一事实源 —— 这类归属绝不允许被抓取器单例覆盖。
TRUSTED_SOURCES = {"filename", "dir", "manual", "user_correction",
                   "websearch-manual", "websearch_verify"}


def norm(n):
    return normalize_name(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true",
                    help="真正落盘（默认只读，只报告）")
    ap.add_argument("--force", action="store_true",
                    help="连可信来源（filename/人工）也一并搬移 —— 危险，不推荐")
    args = ap.parse_args()

    fixed, flagged, protected, ok = [], [], [], 0
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
        if no in set(nc):
            ok += 1
            continue

        # owner 归一时不在 cast 中
        src = w.get("source") or ""
        trusted = src in TRUSTED_SOURCES

        if len(nc) == 1:
            suggested = cast[0]  # 保留原始写法（带括号也不影响显示）
            if suggested == owner:
                ok += 1
                continue
            entry = {"code": w.get("code"), "from": owner, "to": suggested,
                     "cast": cast, "source": src}
            if trusted and not args.force:
                # 铁律：可信来源只报告，绝不自动改
                protected.append(entry)
                flagged.append(entry)
                continue
            fixed.append(entry)
            if args.apply:
                w["actress"] = suggested
                # 溯源同步：值来自抓取器，source 就不能继续声称来自文件名
                if trusted:
                    w["source"] = "user_correction"
                elif src in (None, "", "pending"):
                    w["source"] = "attribution_fix"
                if suggested not in w.get("actresses", []):
                    w.setdefault("actresses", []).append(suggested)
                json.dump(w, open(fp, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
        else:
            flagged.append({"code": w.get("code"), "owner": owner,
                            "cast": cast, "source": src})

    mode = "【落盘模式 --apply】" if args.apply else "【只读报告，未改动任何文件】"
    print("=" * 60)
    print("fix_attribution2  %s" % mode)
    print("=" * 60)
    print("归属一致的        : %d 部" % ok)
    print("单人cast拟修正    : %d 部" % len(fixed))
    for r in fixed[:20]:
        print("  %-12s %s -> %s   (source=%s)" % (r["code"], r["from"], r["to"], r["source"]))
    if len(fixed) > 20:
        print("  ... 其余 %d 部" % (len(fixed) - 20))
    if protected:
        print()
        print("⚠️ 可信来源已保护（未改动，需人工确认）: %d 部" % len(protected))
        for r in protected[:15]:
            print("  %-12s %s -> %s   (source=%s)" % (r["code"], r["from"], r["to"], r["source"]))
        if len(protected) > 15:
            print("  ... 其余 %d 部" % (len(protected) - 15))
    print()
    print("多人cast待人工    : %d 部" % len(flagged))
    for r in flagged[:15]:
        print("  %-12s owner=%-12s cast=%s" % (r["code"], r.get("owner") or r.get("from"), (r["cast"] or [])[:3]))
    if len(flagged) > 15:
        print("  ... 其余 %d 部" % (len(flagged) - 15))

    if flagged:
        json.dump(flagged,
                  open(os.path.join(os.path.dirname(DATA), "attribution_pending.json"),
                       "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("\n已写出 data/attribution_pending.json（%d 部待人工）" % len(flagged))

    if not args.apply and fixed:
        print("\n提示：以上为预演结果。确认无误后加 --apply 才会落盘。")


if __name__ == "__main__":
    main()
