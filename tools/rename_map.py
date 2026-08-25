# -*- coding: utf-8 -*-
"""
rename_map.py —— 【示例应用】把通用查询工具(jav.py)的输出用到文件改名上
==========================================================================
重要定位：本文件不是工具本身，只是 jav.py（通用 JAV 元数据查询工具）的一个
「示例消费者」。jav.py 才是核心：它按番号/女优/关键词查到标准化元数据(JSON)，
任何下游都能消费——文件改名(115/本地)、文件夹整理、导出表格、生成索引……都可以。

本示例做的事：扫描任意目录，从文件名抽番号 → 调 jav.py 查元数据 →
按 --fmt 模板生成新文件名映射（默认「日期 番号 标题」，可改成任何格式）。

这只是其中一种用法。模板可以自由定义，例如：
  115 改名      : --fmt "{date} {code} {title}"
  本地整理(女优): --fmt "{actress}/{code} {title}"
  纯番号+标题   : --fmt "{code} {title}"
  仅导出表格    : 看输出的 rename_map.csv，改名交给别的工具

输出：
  - 默认 dry-run，打印映射表 + 写入 rename_map.csv（old,new,code,title,actress,date,found）
  - --apply  真正在本地重命名（仅对本地/同步盘文件有效；纯云端 115 请用 CSV 交给 115 改名工具）
  - --json   打印 JSON

依赖：复用 tools/jav.py 的 codeav_product（带缓存，避免重复请求触发 429）

示例：
  python tools/rename_map.py --dir "D:/115/桃乃木かな"
  python tools/rename_map.py --dir "D:/Downloads" --fmt "{actress}/{code} {title}"
"""
import os
import re
import sys
import csv
import json
import argparse
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from jav import codeav_product, canon_code  # noqa: E402

ILLEGAL = re.compile(r'[\\/:*?"<>|]')


def extract_code(filename):
    """从文件名抽番号，如 STARS-145 / stars145 / 1stars00145。"""
    m = re.search(r'([A-Za-z]{2,8})[_ -]?(\d{2,5})', filename, re.I)
    if not m:
        return None
    return canon_code(m.group(1) + "-" + m.group(2))


def safe_name(text, limit=120):
    if not text:
        return ""
    t = ILLEGAL.sub("_", text).strip()
    t = re.sub(r"\s+", " ", t)
    return t[:limit].rstrip()


def build_new_name(meta, code, fmt="{date} {code} {title}"):
    date = (meta.get("date") or "") if meta else ""
    title = safe_name(meta.get("title")) if meta else ""
    actress = safe_name(meta.get("actress")) if meta else ""
    return fmt.format(date=date, code=code, title=title, actress=actress).strip()


def main():
    ap = argparse.ArgumentParser(
        description="【示例应用】扫描目录→抽番号→查 jav.py→生成改名映射(模板可配)。"
                    " 115/本地整理/导出表格等皆可用，工具本身是通用的。")
    ap.add_argument("--dir", required=True, help="要扫描的目录（本地/同步盘/任意）")
    ap.add_argument("--apply", action="store_true", help="真正重命名（本地文件）")
    ap.add_argument("--out", default=None, help="CSV 输出路径（默认 <dir>/rename_map.csv）")
    ap.add_argument("--fmt", default="{date} {code} {title}",
                    help="新文件名模板，可用 {date}{code}{title}{actress}，如 \"{actress}/{code} {title}\"")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    ap.add_argument("--no-cache", action="store_true", help="禁用 codeav 缓存")
    args = ap.parse_args()

    d = args.dir
    if not os.path.isdir(d):
        print(f"目录不存在：{d}", file=sys.stderr)
        sys.exit(1)

    files = [f for f in sorted(os.listdir(d)) if os.path.isfile(os.path.join(d, f))]
    rows = []
    for f in files:
        code = extract_code(f)
        if not code:
            rows.append({"old": f, "new": f, "code": "", "title": "", "actress": "",
                         "date": "", "found": False, "reason": "no_code"})
            continue
        try:
            meta = codeav_product(code)
        except Exception as e:
            meta = None
            print(f"  [warn] {code} 查询失败: {e}", file=sys.stderr)
        new_base = build_new_name(meta, code, args.fmt) if meta else code
        ext = os.path.splitext(f)[1]
        new_name = new_base + ext
        rows.append({
            "old": f, "new": new_name, "code": code,
            "title": (meta or {}).get("title", ""),
            "actress": (meta or {}).get("actress", ""),
            "date": (meta or {}).get("date", ""),
            "found": bool(meta), "reason": "" if meta else "not_found",
        })
        time.sleep(0.25)  # 礼貌限速

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return

    out_csv = args.out or os.path.join(d, "rename_map.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["old", "new", "code", "title", "actress", "date", "found", "reason"])
        w.writeheader()
        w.writerows(rows)

    found = sum(1 for r in rows if r["found"])
    print(f"扫描 {len(rows)} 个文件，命中 codeav {found} 个，未命中 {len(rows)-found} 个")
    print(f"映射已写入：{out_csv}")
    print("-" * 70)
    for r in rows:
        if r["found"]:
            print(f"  {r['old']}\n    -> {r['new']}")
    if not args.apply:
        print("\n(dry-run，未改名。加 --apply 执行本地重命名)")
    else:
        for r in rows:
            if not r["found"] or r["old"] == r["new"]:
                continue
            try:
                os.rename(os.path.join(d, r["old"]), os.path.join(d, r["new"]))
            except Exception as e:
                print(f"  [fail] {r['old']}: {e}", file=sys.stderr)
        print("已执行本地重命名。")


if __name__ == "__main__":
    main()
