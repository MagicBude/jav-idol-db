#!/usr/bin/env python3
"""把 data/genre/ 下多份跨源 genre 映射表合并为单一权威表 genre_all.csv。

设计要点
--------
- 合并键：以原始标签（日文 `ja` 优先）去重。
  * jav321 把日文放在 `translate` 列（`ja` 多为空），自动把该列提升为合并键。
  * 无日文来源（javdb）按 `en` / `zh_cn` / `id` 兜底作为合并键。
- 值列优先级：zh_cn -> zh_tw -> translate（按源优先级取首个非空）。
- 去重：同一合并键只保留一行，多来源用 `source` 列记录溯源。
- 输出整洁、可排序、UTF-8-BOM（Excel 直接正确打开中文）。

输出
----
- data/genre/genre_all.csv  ：结构化的单一权威映射表（供 scripts/genre_norm.py 消费）
- data/genre/genre_all.xlsx ：带样式的可读版本（冻结表头 + 彩色表头 + 自动列宽 + 筛选器）

用法
----
    python scripts/merge_genre.py
"""
import csv
import os
import sys
import glob

_HERE = os.path.dirname(os.path.abspath(__file__))
_GENRE_DIR = os.path.join(_HERE, "..", "data", "genre")
_OUT_CSV = os.path.join(_GENRE_DIR, "genre_all.csv")
_OUT_XLSX = os.path.join(_GENRE_DIR, "genre_all.xlsx")

# 源优先级：值列取「首个非空」时据此排序（越靠前越优先）
_PRIORITY = ["javdb", "javbus", "javlib", "avsox", "jav321"]

# 输出列（与 genre_norm 的键/值列保持一致，便于直接消费）
FIELDS = ["id", "url", "ja", "zh_cn", "zh_tw", "en", "translate", "note", "source"]


def _src_name(fn):
    base = os.path.basename(fn)
    if base.startswith("genre_") and base.endswith(".csv"):
        return base[len("genre_"):-len(".csv")]
    return base[:-4]


def _load_sources():
    """读取原始跨源 CSV。优先读 legacy/ 归档，否则读 data/genre/ 下除 genre_all 外的文件。"""
    legacy = os.path.join(_GENRE_DIR, "legacy")
    if os.path.isdir(legacy):
        pat = os.path.join(legacy, "genre_*.csv")
    else:
        pat = os.path.join(_GENRE_DIR, "genre_*.csv")
    files = [f for f in glob.glob(pat)
             if os.path.basename(f) != "genre_all.csv"]
    return sorted(files)


def _ja_eff(row, src):
    """解析该行的「原始标签键」：优先 ja；jav321 的日文在 translate 列；否则空。"""
    ja = (row.get("ja") or "").strip()
    if ja:
        return ja
    if src == "jav321":
        tr = (row.get("translate") or "").strip()
        if tr:
            return tr  # jav321 把日文放在 translate 列
    return ""


def _pick(members, valcol):
    """按源优先级取首个非空值列。"""
    for _, row, _ in members:
        v = (row.get(valcol) or "").strip()
        if v:
            return v
    return ""


def merge():
    groups = {}  # key -> list[(priority_idx, row, src)]
    for fp in _load_sources():
        src = _src_name(fp)
        try:
            with open(fp, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    key = _ja_eff(row, src)
                    if not key:
                        key = ((row.get("en") or "").strip()
                               or (row.get("zh_cn") or "").strip()
                               or (row.get("id") or "").strip())
                    if not key:
                        continue
                    pidx = _PRIORITY.index(src) if src in _PRIORITY else 99
                    groups.setdefault(key, []).append((pidx, row, src))
        except Exception as e:  # 容错：单文件损坏不影响整体
            print("跳过 %s: %s" % (fp, e), file=sys.stderr)

    rows = []
    for key, members in groups.items():
        members.sort(key=lambda m: m[0])
        merged = {fld: "" for fld in FIELDS}
        merged["ja"] = key  # 原始标签键（日文优先，缺则英文/中文/站点id）
        merged["zh_cn"] = _pick(members, "zh_cn")
        merged["zh_tw"] = _pick(members, "zh_tw")
        merged["en"] = _pick(members, "en")
        merged["translate"] = _pick(members, "translate")
        merged["id"] = (members[0][1].get("id") or "").strip()
        merged["url"] = (members[0][1].get("url") or "").strip()
        notes = []
        for _, row, _ in members:
            n = (row.get("note") or "").strip()
            if n and n not in notes:
                notes.append(n)
        merged["note"] = " / ".join(notes)
        merged["source"] = ";".join(sorted({m[2] for m in members}))
        rows.append(merged)

    # 排序：日文/原文在前，便于浏览
    rows.sort(key=lambda r: (r["ja"] or "\uffff", r["zh_cn"] or ""))

    with open(_OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print("合并完成：%d 个唯一标签 -> %s" % (len(rows), _OUT_CSV))
    return rows


def write_xlsx(rows):
    """生成带样式的可读 xlsx（CSV 无法承载样式，xlsx 可以）。"""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter
    except Exception as e:
        print("跳过 xlsx（openpyxl 不可用）: %s" % e, file=sys.stderr)
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "genre"
    headers = ["原始标签(ja)", "简中(zh_cn)", "繁中(zh_tw)",
               "英文(en)", "别名(translate)", "来源(source)"]
    ws.append(headers)
    head_fill = PatternFill("solid", fgColor="FF5C8A")
    for c in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for r in rows:
        ws.append([r["ja"], r["zh_cn"], r["zh_tw"],
                   r["en"], r["translate"], r["source"]])
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(headers)), len(rows) + 1)
    for i, width in enumerate([30, 22, 22, 28, 24, 24], start=1):
        ws.column_dimensions[get_column_letter(i)].width = width
    wb.save(_OUT_XLSX)
    print("已生成样式化 xlsx: %s" % _OUT_XLSX)


if __name__ == "__main__":
    rows = merge()
    write_xlsx(rows)
