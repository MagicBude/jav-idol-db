# -*- coding: utf-8 -*-
"""
115 文件名「摘掉女优名后缀」专用脚本（安全版）
============================================
背景：早先 115rename.py 会在文件名后强制追加 `·女优`（有标题时）或 ` 女优`（缺标题时）。
      现决定文件名不携带女优名（共演作品加谁都不合适，原片名是什么就是什么）。

本脚本**以当前 115 文件名为唯一事实来源**，只摘掉我之前【额外追加】的女优名后缀，
绝不触碰标题正文里的任何内容（含标题中自带的女优名）。

摘除规则（精确、保守）：
  1) `·{女优}` 中点后缀：仅当它紧跟 [画质]/.part/扩展名/结尾时摘除
     —— 例： `...初収録·楓ふうあ.part2.mp4` -> `...初収録.part2.mp4`
  2) 独立 ` {女优}` 后缀：仅当它是「标题区唯一内容」即 `date? CODE 女优[画质]?` 时摘除
     （code 后直接空格+女优名，中间无其它标题文字）
     —— 例： `OFJE-186HHB 河北彩花.mp4` -> `OFJE-186HHB.mp4`
  3) 标题里自带的女优名（如 `ヘアーヌード／楓ふうあ II`、`彩伽のテク…`、`河北彩花がご奉仕…`）
     一律原样保留，因为既非 `·` 中点后缀、也非 code 后独立后缀。

注意：不再走「重新抓元数据再拼」的旧路——那会丢掉 115 上原本就带、但元数据缺失的真实标题
（如写真码 BTHA-089 的 `ヘアーヌード／楓ふうあ II`）。

用法：
  python tools/strip_actress.py --cid <根cid> --actress <合集女优> [--out-prefix P]
  python tools/strip_actress.py --cid <根cid> --actress <合集女优> --out-prefix P --apply
"""
import os, re, sys, json, time, argparse, importlib.util
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKILL = "C:/Users/Admin/.workbuddy/skills/115-av-rename/scripts"

_sp = importlib.util.spec_from_file_location("t115", os.path.join(SKILL, "115_rename_toolkit.py"))
t115 = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(t115)
connect, list_all, batch_rename_exec, verify_renames = (
    t115.connect, t115.list_all, t115.batch_rename_exec, t115.verify_renames)


def strip_actress_suffix(fn, actress):
    """摘除我之前追加的女优名后缀；标题/日期/番号/画质原样保留。"""
    a = actress
    # 1) 中点后缀 `·{女优}`（仅紧跟 [画质]/.part/扩展名/结尾）
    s = re.sub(r"·" + re.escape(a) + r"(?=[\[\.]|$)", "", fn)
    # 2) 独立后缀 ` {女优}`（仅 code 后直接空格+女优名，无其他标题文字）
    #    匹配：可选 date + code + 空格 + 女优名 + ([画质]/./结尾)
    pat = re.compile(
        r"^((\d{4}-\d{2}-\d{2})\s+)?([A-Za-z]+[-_]\d+[A-Za-z\d]*)\s+"
        + re.escape(a) + r"(?=[\[\.]|$)")
    def _repl(m):
        date = m.group(2)
        code = m.group(3)
        return (date + " " if date else "") + code
    s = pat.sub(_repl, s)
    return s


def collect(sid, root_cid):
    root, _ = list_all(sid, root_cid)
    subs = [(it["fn"], it["fid"]) for it in root if str(it.get("fc")) == "0"]
    items = []
    for fname, fid in subs:
        files, _ = list_all(sid, fid)
        for f in files:
            if str(f.get("fc")) == "1":
                items.append({"parent": fname, "fid": f.get("fid"), "fn": f.get("fn")})
    for it in root:
        if str(it.get("fc")) == "1":
            items.append({"parent": "", "fid": it.get("fid"), "fn": it.get("fn")})
    return items


def make_plan(items, actress):
    plan = []
    for it in items:
        old = it["fn"]
        new = strip_actress_suffix(old, actress)
        plan.append({**it, "new": new, "skip": new == old,
                     "reason": "" if new != old else "无需改动"})
    return plan


def check_conflicts(plan):
    cnt = Counter(o["new"] for o in plan if not o.get("skip"))
    return [n for n, c in cnt.items() if c > 1]


def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_preview(plan, conflicts, path_html, path_csv, path_json):
    with open(path_csv, "w", encoding="utf-8-sig", newline="") as f:
        f.write("parent,fid,old,new,changed\n")
        for o in plan:
            f.write(",".join('"' + (str(x or "").replace('"', '""')) + '"'
                             for x in [o.get("parent"), o.get("fid"),
                                       o.get("fn"), o.get("new"),
                                       "Y" if not o.get("skip") else "N"]) + "\n")
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    rows = ""
    for o in plan:
        if o.get("skip"):
            continue
        cls = "bad" if o.get("issues") else ""
        rows += (f'<tr class="{cls}"><td>{esc(o.get("parent",""))}</td>'
                 f'<td class="old">{esc(o.get("fn"))}</td>'
                 f'<td class="new">{esc(o.get("new"))}</td></tr>')
    conflict_html = ("<p class='warn'>⚠ 重复新名：" +
                     "; ".join(f"<code>{esc(c)}</code>" for c in conflicts) + "</p>") if conflicts else ""
    html = f"""<!doctype html><html lang=zh><head><meta charset=utf-8>
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}}
h1{{font-size:20px}}table{{border-collapse:collapse;width:100%;font-size:13px;background:#fff}}
td,th{{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#f0f0f0}}.old{{color:#888}}.new{{color:#116}}.bad{{background:#fff3f3}}
.warn{{color:#c0392b;font-weight:600}}code{{background:#f0f0f0;padding:1px 4px;border-radius:3px}}</style></head>
<body><h1>115 摘女优名后缀预览（{len([o for o in plan if not o.get('skip')])} 个将改名 / 共 {len(plan)}）</h1>
<p>规则：仅摘掉之前追加的 <code>·女优</code> / 独立 <code> 女优</code> 后缀；标题正文里的女优名原样保留。</p>
{conflict_html}
<table><tr><th>子文件夹</th><th>原名</th><th>新名</th></tr>{rows}</table></body></html>"""
    with open(path_html, "w", encoding="utf-8") as f:
        f.write(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cid", required=True, help="115 根文件夹 cid")
    ap.add_argument("--actress", required=True, help="该合集女优（仅用于定位要摘掉的后缀）")
    ap.add_argument("--out-prefix", default="strip", help="预览/备份文件前缀")
    ap.add_argument("--apply", action="store_true", help="真正执行（默认仅预览）")
    args = ap.parse_args()
    ROOT_CID, ACTRESS, PREFIX = args.cid, args.actress, args.out_prefix
    print(f"连接 115 ... cid={ROOT_CID} actress={ACTRESS}", flush=True)
    sid = connect()
    items = collect(sid, ROOT_CID)
    print(f"共 {len(items)} 个文件，计算摘除女优名后缀...", flush=True)
    plan = make_plan(items, ACTRESS)
    conflicts = check_conflicts(plan)
    changed = [o for o in plan if not o.get("skip")]
    unchanged = [o for o in plan if o.get("skip")]
    print(f"  将改名: {len(changed)} | 无需改动: {len(unchanged)}", flush=True)
    if conflicts:
        print("  ⚠ 重复新名:", conflicts, flush=True)
    ph = os.path.join(HERE, f"{PREFIX}_preview.html")
    pc = os.path.join(HERE, f"{PREFIX}_plan.csv")
    pj = os.path.join(HERE, f"{PREFIX}_plan.json")
    write_preview(plan, conflicts, ph, pc, pj)
    print(f"预览已写：\n  {ph}\n  {pc}\n  {pj}", flush=True)
    if not args.apply:
        print("\n（dry-run）未改动 115。确认预览无误后加 --apply 执行。", flush=True)
        return
    if conflicts:
        print("存在重复新名，停止执行。", flush=True)
        return
    renames = {o["fid"]: o["new"] for o in plan if not o.get("skip")}
    if not renames:
        print("没有需要改名的文件。", flush=True)
        return
    # 自管备份：{fid:{old,new}}，便于回滚
    backup = os.path.join(HERE, f"{PREFIX}_rename_backup.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump({k: {"old": next(o["fn"] for o in plan if o["fid"] == k),
                       "new": v} for k, v in renames.items()},
                  f, ensure_ascii=False, indent=2)
    print(f"执行批量改名：{len(renames)} 个 ...", flush=True)
    ok_n, fail_n, failed, sid, _ = batch_rename_exec(sid, renames, batch=20)
    print(f"提交结果：success={ok_n} failed={fail_n}", flush=True)
    if failed:
        print("失败明细：", failed[:10], flush=True)
    print("逐 fid 复核 ...", flush=True)
    root, _ = list_all(sid, ROOT_CID)
    cids = {it["fn"]: it["fid"] for it in root if str(it.get("fc")) == "0"}
    vok, bad, _ = verify_renames(sid, cids, plan, key="new")
    print(f"复核通过：{vok} / 失败：{len(bad)}", flush=True)
    if bad:
        print("未生效：", bad[:10], flush=True)


if __name__ == "__main__":
    main()
