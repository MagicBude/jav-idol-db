#!/usr/bin/env python3
"""把 data/genre/ 下多份跨源 genre 映射表合并为单一权威表 genre.csv。

设计要点
--------
- 合并键：以原始标签（日文 `ja` 优先）去重。
  * jav321 把日文放在 `translate` 列（`ja` 多为空），自动把该列提升为合并键。
  * 无日文来源（javdb）按 `en` / `zh_cn` / `id` 兜底作为合并键。
- 值列补全（让单一文档本身就是完整可读的资料库）：
  * `zh_cn`：优先 source zh_cn -> 否则 zhconv(源 zh_tw 繁->简) -> 否则
    源 translate（若为中文）繁->简 -> 否则 data/zh.json 的 tag_zh[ja] 人工精修。
  * `zh_tw`：优先 source zh_tw -> 否则 zhconv(源 zh_cn 简->繁)，两列互补填满。
- 去重：同一合并键只保留一行，多来源用 `source` 列记录溯源。
- 输出整洁、可排序、UTF-8-BOM（Excel 直接正确打开中文）。

输出
----
- data/genre/genre.csv  ：结构化的单一权威映射表（供 scripts/genre_norm.py 消费，也是可读资料库）
- data/genre/genre.xlsx ：带样式的可读版本（冻结表头 + 彩色表头 + 自动列宽 + 筛选器）

用法
----
    python scripts/merge_genre.py
"""
import csv
import json
import os
import sys
import glob
import zhconv

_HERE = os.path.dirname(os.path.abspath(__file__))
_GENRE_DIR = os.path.join(_HERE, "..", "data", "genre")
_OUT_CSV = os.path.join(_GENRE_DIR, "genre.csv")
_OUT_XLSX = os.path.join(_GENRE_DIR, "genre.xlsx")

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
    """读取原始跨源 CSV。优先读 legacy/ 归档，否则读 data/genre/ 下除 genre.csv 外的文件。"""
    legacy = os.path.join(_GENRE_DIR, "legacy")
    if os.path.isdir(legacy):
        pat = os.path.join(legacy, "genre_*.csv")
    else:
        pat = os.path.join(_GENRE_DIR, "genre*.csv")
    files = [f for f in glob.glob(pat)
             if os.path.basename(f) != "genre.csv"]
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


def _is_chinese(s):
    """含汉字且不含假名，视为中文（可用于补全 zh_cn）。"""
    has_han = False
    for ch in s:
        o = ord(ch)
        if 0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF:
            has_han = True
        elif 0x3040 <= o <= 0x30FF:  # 假名 -> 日文，排除
            return False
    return has_han


def _fill_zh_cn(members, ja, zh_json):
    """按优先级补全简中：源 zh_cn -> 源 zh_tw(繁->简) -> 源 translate(中,繁->简) -> zh.json 精修。"""
    for _, row, _ in members:
        v = (row.get("zh_cn") or "").strip()
        if v:
            return v
    for _, row, _ in members:
        v = (row.get("zh_tw") or "").strip()
        if v:
            return zhconv.convert(v, "zh-cn")
    for _, row, _ in members:
        v = (row.get("translate") or "").strip()
        if v and _is_chinese(v):
            return zhconv.convert(v, "zh-cn")
    if ja and ja in zh_json:
        return zh_json[ja]
    return ""


def _fill_zh_tw(members):
    """补全繁中：源 zh_tw -> 源 zh_cn(简->繁)。"""
    for _, row, _ in members:
        v = (row.get("zh_tw") or "").strip()
        if v:
            return v
    for _, row, _ in members:
        v = (row.get("zh_cn") or "").strip()
        if v:
            return zhconv.convert(v, "zh-tw")
    return ""


def merge():
    # 载入人工精修的中文映射（data/zh.json 的 tag_zh），作为 zh_cn 的最高优先级补充
    zh_json = {}
    try:
        with open(os.path.join(_HERE, "..", "data", "zh.json"), encoding="utf-8") as f:
            zh_json = (json.load(f).get("tag_zh") or {})
    except Exception:
        pass

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
    empty_before = 0
    for key, members in groups.items():
        members.sort(key=lambda m: m[0])
        merged = {fld: "" for fld in FIELDS}
        merged["ja"] = key  # 原始标签键（日文优先，缺则英文/中文/站点id）
        merged["zh_cn"] = _fill_zh_cn(members, key, zh_json)
        if not merged["zh_cn"]:
            empty_before += 1
        merged["zh_tw"] = _fill_zh_tw(members)
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
    print("合并完成：%d 个唯一标签 -> %s（补全后空 zh_cn: %d）"
          % (len(rows), _OUT_CSV, empty_before))
    return rows


def _pick(members, valcol):
    """按源优先级取首个非空值列。"""
    for _, row, _ in members:
        v = (row.get(valcol) or "").strip()
        if v:
            return v
    return ""


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
