# -*- coding: utf-8 -*-
"""
115 网盘批量改名 · 编排脚本（按 115-av-rename 技能流程）
================================================================
针对「某女优合集」文件夹（内含 单体/VR/写真/合辑/共演 等子文件夹）。

流程：
  1) 连 115，递归列出子文件夹全部文件（fid + 文件名）。
  2) 从文件名抽 番号 / 画质标签(_4K60fps→[4K][60fps] 等) / 分卷(.partN)。
  3) 抓 codeav 全量元数据（标题+发行日+女优+片商+系列+标签…），并**永久存档**到
     data/works/<番号>.json（meta_store 负责，单布局唯一真相源，命中缓存不重抓）。
  4) 生成新名：{date} {code} {title}{[画质]}.partN.mp4
     —— 直接用 codeav 原始片名（title），【不】追加女优名：共演作品女优多、加谁都不合适，
        且片名本身已含信息，加女优名只徒增歧义/撞名。--actress 仅用于元数据归类（写进 work 的 actress 字段）。
  5) 默认 dry-run：写预览 HTML/CSV/JSON，打印统计。**不改动 115**。
     --apply 才执行批量改名（带备份 + 逐 fid 复核）。

用法：
  python tools/115rename.py --cid 3502028436149372789 --actress 八木奈々
  python tools/115rename.py --cid 3501918228345522045 --actress 村上悠華 --apply
  # 可选：--out-prefix 区分不同文件夹的预览/备份文件（默认 115）
"""
import os, re, sys, json, time, argparse, importlib.util
from concurrent.futures import ThreadPoolExecutor
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKILL = "C:/Users/Admin/.workbuddy/skills/115-av-rename/scripts"
PRIMARY_CACHE = os.path.join(ROOT, "data", "_codeav_primary_cache.json")

# ---- 加载 115 工具包（数字开头模块名，用 importlib）----
_sp = importlib.util.spec_from_file_location("t115", os.path.join(SKILL, "115_rename_toolkit.py"))
t115 = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(t115)
connect, list_all, batch_rename_exec, verify_renames, sanitize, dmm_id_to_ck = (
    t115.connect, t115.list_all, t115.batch_rename_exec, t115.verify_renames, t115.sanitize, t115.dmm_id_to_ck)

# 媒体扩展名：视频 + 封面图。仅这两类参与改名；.rar/.txt/.nfo/.98t/.zip 等一律跳过。
VIDEO_EXT = ("mp4", "iso", "mkv", "ts", "wmv", "mov")
IMAGE_EXT = ("jpg", "jpeg", "png", "webp", "gif", "bmp")
MEDIA_EXT = VIDEO_EXT + IMAGE_EXT

# ---- 加载元数据持久层（抓取 + 落盘 data/works/<番号>.json，单布局唯一真相源）----
sys.path.insert(0, HERE)
from meta_store import get_meta  # noqa: E402

# 主缓存：番号 -> 女优名（仅作女优名兜底，现代码已用 --actress 合集女优）
_primary = {}
if os.path.exists(PRIMARY_CACHE):
    try:
        _primary = json.load(open(PRIMARY_CACHE, encoding="utf-8"))
    except Exception:
        _primary = {}

# ---------------------------------------------------------------------------
# 文件名解析
# ---------------------------------------------------------------------------
_EXT_RE = re.compile(
    r"\.(mp4|iso|mkv|ts|wmv|mov|jpg|jpeg|png|webp|gif|bmp)"
    r"(?:\.(?:mp4|iso|mkv|ts|wmv|mov|jpg|jpeg|png|webp|gif|bmp))*$", re.I)
# 末尾画质段（仅此段可被识别为画质标签）：_4K60fps / _60fps / _4Ks / _4K / _8K / [4K] / [60fps] / [8K]
# 严禁全串搜索——否则标题正文里的「4K撮影」「4K超画質」会被误当画质标签，既截断标题又致撞名。
_QUAL_TAIL = re.compile(
    r"((?:[ _]?(?:4K60fps|60fps|4KS\d*|4Ks|4K|8K)|\[(?:4K|60fps|8K)\])+)$", re.I)

def _extract_quality(seg):
    """从末尾画质段字符串提取标签列表。

    - 组合 4K60fps 整体 -> [4K][60fps]（避免被拆成 4K+60fps 重复）
    - 4KS / 4KS1 / 4KS2 -> [4K] / [4K-S1] / [4K-S2]（保留数字区分同码多版本，避免撞名）
    - 4K 优先于 60fps，符合常见写法 [4K][60fps]
    - 去重
    - 调用方已限定 seg 仅为【末尾画质簇】，故不会误吞标题正文的「4K」字样"""
    tags = []
    if re.search(r"4K60fps", seg, re.I):
        tags.append("[4K][60fps]")
        seg = re.sub(r"4K60fps", "", seg, flags=re.I)  # 消费掉，避免被 4K/60fps 重复计入
    for m in re.finditer(r"4KS(\d*)", seg, re.I):
        n = m.group(1)
        tags.append(f"[4K-S{n}]" if n else "[4K]")
    seg = re.sub(r"4KS\d*", "", seg, flags=re.I)
    if re.search(r"4K", seg, re.I) and not any(t.startswith("[4K") for t in tags):
        tags.append("[4K]")
    if re.search(r"60fps", seg, re.I) and "[60fps]" not in tags:
        tags.append("[60fps]")
    if re.search(r"8K", seg, re.I) and "[8K]" not in tags:
        tags.append("[8K]")
    return tags

def parse_fn(fn):
    """返回 (code, part|None, tags[], copy|None, ext, date_prefix|None, body)。

    - 支持已改名文件的「YYYY-MM-DD 」前缀 / 完整标题（从开头抽码）
    - **保留前导零**：GHVR-04 -> GHVR-04 / RCTVR-002 -> RCTVR-002（绝不误去；
      仅在「无分隔符且明显是补零」时去前导零，如 ofje00186 -> OFJE-186）
    - 码允许尾部多字母（SS-055EX、NAAC-008B、hhb 共演后缀）
    - .partN 算段号（可出现在画质前）；画质标签 _4K60fps/_60fps/_4Ks/_8K 转 [4K][60fps]
    - 尾部 _1/_2 副本标记抽为 copy（避免两份拷贝撞名）
    - 支持 .iso/.mkv 等扩展名（新名保留原扩展名）
    - date_prefix：原文件名自带的「YYYY-MM-DD 」日期（若有）；body：码之后、画质/段号之前的
      标题正文（原片名，若有）。两者用于「原文件已带标题/日期则保留，不盲目用 codeav 覆盖」。"""
    s = fn
    date_prefix = None
    m0 = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(.*)$", s)
    if m0:
        date_prefix = m0.group(1)  # 保留原日期
        s = m0.group(2)  # 丢掉日期前缀
    ext = ""
    em = _EXT_RE.search(s)
    if em:
        ext = s[em.start():]; s = s[:em.start()]
    # 分卷（part 不一定在结尾，可能后接画质）
    part = None
    pm = re.search(r"\.part(\d+)", s, re.I)
    if pm:
        part = int(pm.group(1)); s = s[:pm.start()] + s[pm.end():]
    # 副本标记：末尾 " (N)"（空格括号，如 SONE-560 (1)/(2) 同内容两份拷贝）或 "_N"（如 SDAM-134v_4Ks3）。
    # 仅认空格括号 / 下划线数字，避免误吞码本身尾号（SONE-560HHB1 的 HHB1、BF-728 的 -728）。
    copy = None
    cm = re.search(r"\s\((\d+)\)$", s)
    if cm:
        copy = int(cm.group(1)); s = s[:cm.start()]
    else:
        cm2 = re.search(r"_(\d+)$", s)
        if cm2:
            copy = int(cm2.group(1)); s = s[:cm2.start()]
    # 画质标签：仅从文件名【末尾画质段】提取，严禁全串搜索（见 _QUAL_TAIL 注释）。
    tags = []
    qm = _QUAL_TAIL.search(s)
    if qm:
        seg = qm.group(1); s = s[:qm.start()]
        tags = _extract_quality(seg)
    # 抽番号：标准码优先（保留前导零），DMM 内码兜底。
    # 关键：标准码 PREFIX-NNN（前缀≥2字母）必须【保留原始前导零】——
    #   FNS-015 / SONE-013 / SS-055EX 绝不能误成 FNS-15。旧逻辑先走 dmm_id_to_ck→canon_key
    #   用 %d 把前导零吞掉，且返回的码与索引 key（data/works 用 FNS-015）不一致，
    #   导致重跑 make_plan 时元数据 lookup 失败、已改名文件被错误回退。
    #   仅认「字母前缀+连字符+数字」形态，避开 DMM 内码（1stars*/h_*/13dsvr*/55t* 等以数字
    #   或单字母 h_ 开头，不会命中「≥2 字母前缀」约束），其余仍交 dmm_id_to_ck 权威解析。
    code = None
    body = ""
    # 1) 标准码（前缀≥2字母 + 连字符 + 数字[+尾字母]）：保留前导零
    m = re.match(r"^([A-Za-z]{2,})[-_](\d+)([A-Za-z\d]*)", s, re.I)
    if m:
        prefix = m.group(1).upper(); num = m.group(2); tail = m.group(3).upper()
        code = f"{prefix}-{num}{tail}"
        body = s[m.end():].strip()  # 码之后的标题正文（原片名）
    # 2) DMM 内码（无连字符/带 h_ 前缀等）：交给 dmm_id_to_ck 权威解析（返回 # 格式，转 -）
    if not code:
        try:
            for c in dmm_id_to_ck(s):
                cc = c.replace("#", "-").upper()
                if cc:
                    code = cc
                    break
        except Exception:
            pass
    # 3) 无分隔符拼接码兜底（如 ofje00186hhb）：去前导零归 canonical（OFJE-186HHB）
    if not code:
        m2 = re.match(r"^([A-Za-z]+)[-_]?(\d+)([A-Za-z\d]*)", s, re.I)
        if m2:
            prefix = m2.group(1).upper(); num = str(int(m2.group(2))); tail = m2.group(3).upper()
            code = f"{prefix}-{num}{tail}"
            body = s[m2.end():].strip()
    if not code:
        return None
    return code, part, tags, copy, ext, date_prefix, body

# ---------------------------------------------------------------------------
# 生成新名
# ---------------------------------------------------------------------------
def build_newname(code, part, tags, title, date, copy=None, ext=".mp4"):
    segs = []
    if date:
        segs.append(date)
    segs.append(code)
    if title:
        segs.append(title)  # 直接用 codeav 原始片名，不追加女优名（共演作品女优多、加谁都不合适）
    name = " ".join(segs) + "".join(tags)
    if copy is not None:
        name += f" ({copy})"
    if part is not None:
        name += f".part{part}"
    name += ext
    return sanitize(name)

# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def collect(sid, root_cid):
    root, _ = list_all(sid, root_cid)
    subs = [(it["fn"], it["fid"]) for it in root if str(it.get("fc")) == "0"]
    items = []
    for fname, fid in subs:
        files, _ = list_all(sid, fid)
        for f in files:
            if str(f.get("fc")) == "1":
                items.append({"parent": fname, "fid": f.get("fid"), "fn": f.get("fn")})
    # 根目录直接挂的文件（无子文件夹）也支持
    for it in root:
        if str(it.get("fc")) == "1":
            items.append({"parent": "", "fid": it.get("fid"), "fn": it.get("fn")})
    return items

def make_plan(items, folder_actress, workers=8):
    # 唯一码 -> 全量元数据（meta_store：命中缓存不重抓；未命中抓 codeav 并落盘）
    codes = {}
    for it in items:
        p = parse_fn(it["fn"])
        if p:
            codes.setdefault(p[0], None)
    meta = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for c, m in zip(codes, ex.map(lambda c: get_meta(c, actress=folder_actress), codes)):
            meta[c] = m
    # 生成每条
    plan = []
    for it in items:
        p = parse_fn(it["fn"])
        if not p:
            plan.append({**it, "skip": True, "reason": "无法解析番号", "new": it["fn"]})
            continue
        code, part, tags, copy, ext, date_prefix, body = p
        # 仅视频 + 封面图参与改名；.rar/.txt/.nfo/.98t/.zip 等非媒体一律跳过
        ext_clean = ext.lower().lstrip(".")
        if ext_clean not in MEDIA_EXT:
            plan.append({**it, "skip": True, "reason": "非媒体文件", "new": it["fn"]})
            continue
        is_cover = ext_clean in IMAGE_EXT
        m = meta.get(code, {}) or {}
        codeav_title = m.get("title")
        codeav_date = m.get("date")
        # 规则：原文件名已自带标题/日期则【保留】，不盲目用 codeav 覆盖
        # （满足用户「原片名是啥样就用啥样」；仅当原文件缺标题/日期时才用 codeav 补全）
        title = body if body else codeav_title
        date = date_prefix or codeav_date
        # --actress 仅用于元数据归类（写进 work 的 actress 字段），不再写进文件名
        actress = folder_actress
        new = build_newname(code, part, tags, title, date, copy=copy, ext=ext)
        issues = []
        if not title:
            issues.append("缺标题")
        if not date:
            issues.append("缺日期")
        src_title = "existing" if body else ("codeav" if codeav_title else "none")
        src_date = "existing" if date_prefix else ("codeav" if codeav_date else "none")
        plan.append({**it, "code": code, "part": part, "tags": tags, "copy": copy, "ext": ext,
                     "title": title, "date": date, "actress": actress,
                     "new": new, "issues": issues, "skip": False,
                     "type": "cover" if is_cover else "video",
                     "src_title": src_title, "src_date": src_date})
    return plan, meta

def check_conflicts(plan):
    # 仅拦截「同一子文件夹内」的撞名；不同子文件夹允许同名（115 语义允许，
    # 如 单体/共演 与 新增 各存一份同一视频——按用户规矩「两份拷贝都保留」）。
    cnt = Counter((o.get("parent"), o["new"]) for o in plan if not o.get("skip"))
    return [n for (p, n) in cnt.items() if cnt[(p, n)] > 1]

def write_preview(plan, conflicts, path_html, path_csv, path_json):
    # CSV
    with open(path_csv, "w", encoding="utf-8-sig", newline="") as f:
        f.write("parent,fid,type,old,new,code,date,actress,title,issues\n")
        for o in plan:
            f.write(",".join(('"' + (str(x or "")).replace('"', '""') + '"')
                             for x in [o.get("parent"), o.get("fid"), o.get("type", "video"),
                                       o.get("fn"), o.get("new"), o.get("code"), o.get("date"),
                                       o.get("actress"), o.get("title"),
                                       ";".join(o.get("issues", []))]) + "\n")
    # JSON（apply 用）
    with open(path_json, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)
    # HTML
    rows = ""
    for o in plan:
        cls = "skip" if o.get("skip") else ("bad" if o.get("issues") else "")
        old = o.get("fn"); new = o.get("new")
        iss = ";".join(o.get("issues", [])) or "OK"
        rows += (f'<tr class="{cls}"><td>{o.get("parent","")}</td>'
                 f'<td class="old">{esc(old)}</td><td class="new">{esc(new)}</td>'
                 f'<td>{esc(o.get("actress") or "")}</td><td>{esc(iss)}</td></tr>')
    conflict_html = ("<p class='warn'>⚠ 重复新名：" +
                     "; ".join(f"<code>{esc(c)}</code>" for c in conflicts) + "</p>") if conflicts else ""
    html = f"""<!doctype html><html lang=zh><head><meta charset=utf-8>
<style>body{{font-family:system-ui,sans-serif;margin:24px;background:#fafafa;color:#222}}
h1{{font-size:20px}}table{{border-collapse:collapse;width:100%;font-size:13px;background:#fff}}
td,th{{border:1px solid #ddd;padding:6px 8px;text-align:left;vertical-align:top}}
th{{background:#f0f0f0}}.old{{color:#888}}.new{{color:#116}}.bad{{background:#fff3f3}}
.skip{{background:#f5f5f5;color:#999}}.warn{{color:#c0392b;font-weight:600}}
code{{background:#f0f0f0;padding:1px 4px;border-radius:3px}}</style></head>
<body><h1>115 改名预览（{len(plan)} 个文件）</h1>
<p>格式：<code>日期 番号 标题[画质].partN.mp4</code>（直接用 codeav 原始片名，不追加女优名） · 红底=缺标题/日期，灰底=跳过。</p>
{conflict_html}
<table><tr><th>子文件夹</th><th>原名</th><th>新名</th><th>女优</th><th>状态</th></tr>{rows}</table></body></html>"""
    with open(path_html, "w", encoding="utf-8") as f:
        f.write(html)

def esc(s):
    return str(s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cid", default="3502028436149372789", help="115 根文件夹 cid")
    ap.add_argument("--actress", default="八木奈々", help="该合集所属女优（写入文件名+落盘目录）")
    ap.add_argument("--out-prefix", default="115", help="预览/备份文件前缀（区分不同文件夹）")
    ap.add_argument("--apply", action="store_true", help="真正执行改名（默认仅预览）")
    ap.add_argument("--skip-codes", default="", help="逗号分隔的番号，跳过不改名")
    args = ap.parse_args()
    ROOT_CID = args.cid
    FOLDER_ACTRESS = args.actress
    PREFIX = args.out_prefix
    print(f"连接 115 ... cid={ROOT_CID} actress={FOLDER_ACTRESS}", flush=True)
    sid = connect()
    print("列出文件 ...", flush=True)
    items = collect(sid, ROOT_CID)
    print(f"共 {len(items)} 个文件，解析并抓取全量元数据（落盘 data/works/ 唯一真相源）...", flush=True)
    plan, meta = make_plan(items, FOLDER_ACTRESS)
    if args.skip_codes:
        skipset = {c.strip().upper() for c in args.skip_codes.split(",") if c.strip()}
        for o in plan:
            if o.get("code") in skipset:
                o["skip"] = True
                o["reason"] = "用户指定跳过"
        print(f"  已跳过番号：{', '.join(sorted(skipset))}", flush=True)
    conflicts = check_conflicts(plan)
    skipped = [o for o in plan if o.get("skip")]
    no_title = [o for o in plan if "缺标题" in o.get("issues", [])]
    no_date = [o for o in plan if "缺日期" in o.get("issues", [])]
    ok = [o for o in plan if not o.get("skip") and not o.get("issues")]
    videos = [o for o in plan if o.get("type") == "video" and not o.get("skip")]
    covers = [o for o in plan if o.get("type") == "cover" and not o.get("skip")]
    print(f"  视频可改名: {len(videos)} | 封面可改名: {len(covers)}", flush=True)
    print(f"  可改名(标题+日期齐全): {len(ok)}", flush=True)
    print(f"  缺标题: {len(no_title)} | 缺日期: {len(no_date)} | 解析失败/跳过: {len(skipped)}", flush=True)
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
    # ---- 执行 ----
    if conflicts:
        print("存在重复新名，停止执行，请先处理。", flush=True)
        return
    # 仅对「新名≠原名」的做改名（二次 pass 时跳过已改好的，避免无谓重命名）
    renames = {o["fid"]: o["new"] for o in plan if not o.get("skip") and o["new"] != o["fn"]}
    if not renames:
        print("没有需要改名的文件（全部已是最新命名）。", flush=True)
        return
    backup = os.path.join(HERE, f"{PREFIX}_rename_backup.json")
    print(f"执行批量改名：{len(renames)} 个 ...", flush=True)
    ok_n, fail_n, failed, sid, _ = batch_rename_exec(sid, renames, backup_path=backup, batch=20)
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
