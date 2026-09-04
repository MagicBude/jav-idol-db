# -*- coding: utf-8 -*-
"""
enrich_from_javdatabase.py —— 用 javdatabase（英文站）回补本地缺失字段
============================================================================
背景：codeav 已把 label/duration 补全，但 director 仍缺 35%、maker 缺 9.8%、
series 缺 85%。javdatabase 是**沙箱内静态可达**的英文站，能给出这些字段，
但全是英文/罗马音（Idea Pocket / Dragon Nishikawa），而本站以日文为准
（アイデアポケット / ドラゴン西川）。直填英文会造出破碎字段。

核心思路：反向标注 + 映射回填
----------------------------------------------------------------
本站已有 1307 部带日文 director、1815 部带日文 maker。拿这些作品的番号去
抓 javdatabase，就得到成对的 (英文, 日文) 标注样本：
    MIDV-404  本地 director=ドラゴン西川   javdatabase=Dragon Nishikawa
    IPZZ-396  本地 director=...           javdatabase=...
把全库配对汇总，即得「罗马音→日文」映射表。再用它给**缺失**的作品回填日文值。
一个英文值若对应多个日文值 → 视为歧义（撞名或数据错误），丢弃不用。

字段分级处理
----------------------------------------------------------------
| 字段     | 处理                                                     |
|----------|----------------------------------------------------------|
| duration | 直接填（纯数字，与语言无关）                              |
| date     | 直接填（YYYY-MM-DD）                                      |
| cover    | 直接填（og:image 是 DMM 高清原图，与本站格式一致）          |
| director | 经映射表转日文后填；无映射/歧义 → 不填                     |
| maker    | 同上                                                      |
| series   | **默认不填**：javdatabase 该字段大量是英文标题片段而非真系列 |
| title    | 永不填（英文标题会污染日文标题库）                         |
| actress  | 永不填（罗马音与日文目录名体系不同，会污染归属判定）         |

用法：
  python scripts/enrich_from_javdatabase.py --fetch          # 只抓取/建缓存
  python scripts/enrich_from_javdatabase.py --dry-run        # 试算，不落盘
  python scripts/enrich_from_javdatabase.py --apply          # 实际写盘
  python scripts/enrich_from_javdatabase.py --apply --limit 50
  python scripts/enrich_from_javdatabase.py --refresh        # 忽略缓存重抓

产出：
  - 改写 data/works/<码>.json（indent=1，与仓库既有格式一致）
  - data/en_map.json  罗马音→日文映射表（可人工修订）
  - _cache/javdatabase/<码>.json  原始抓取缓存（不入 git，断点续传用）
"""
import os
import re
import sys
import json
import time
import argparse
import threading
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from sources.javdatabase import JavdatabaseFetcher  # noqa: E402

DATA = os.path.join(ROOT, "data", "works")
CACHE = os.path.join(ROOT, "_cache", "javdatabase")
EN_MAP = os.path.join(ROOT, "data", "en_map.json")

# 仓库既有格式统一为 indent=2 + LF 行尾（已用 .gitattributes 强制）。
DUMP = dict(ensure_ascii=False, indent=2)

_print_lock = threading.Lock()


def log(msg):
    with _print_lock:
        print(msg, flush=True)


# ---------------------------------------------------------------------------
# 抓取（并发 + 缓存 + 断点续传）
# ---------------------------------------------------------------------------
def cache_path(code):
    return os.path.join(CACHE, f"{code}.json")


def load_cache(code):
    """读缓存。返回二元组 (是否命中过缓存, 记录)。

    缓存里存 null 表示「确认未收录/404」——与「没抓过」是两种状态，
    必须区分，否则每次重跑都要把 404 番号再抓一遍（实测 287 个白等 2 分钟）。
    """
    p = cache_path(code)
    if not os.path.exists(p):
        return False, None
    try:
        return True, json.load(open(p, encoding="utf-8"))
    except Exception:
        return False, None


def save_cache(code, rec):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{code}.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)
    os.replace(tmp, p)


def fetch_all(codes, workers=4, delay=0.25, refresh=False):
    """并发抓取，结果落缓存。返回 {code: rec}（含未命中的 None 记录）。"""
    os.makedirs(CACHE, exist_ok=True)
    todo = []
    results = {}
    cached = 0
    for c in codes:
        if not refresh:
            hit, rec = load_cache(c)
            if hit:
                results[c] = rec  # 可能为 None：已确认该站未收录
                cached += 1
                continue
        todo.append(c)

    if todo:
        log(f"[抓取] 缓存命中 {cached}，待抓 {len(todo)}（{workers} 线程）")
        fetcher = JavdatabaseFetcher()
        idx = [0]
        lock = threading.Lock()

        def worker():
            f = JavdatabaseFetcher()
            while True:
                with lock:
                    if idx[0] >= len(todo):
                        return
                    i = idx[0]
                    idx[0] += 1
                    c = todo[i]
                rec = f.fetch(c)
                save_cache(c, rec)
                with lock:
                    results[c] = rec
                if (i + 1) % 100 == 0:
                    log(f"  进度 {i + 1}/{len(todo)}")
                time.sleep(delay)

        threads = [threading.Thread(target=worker, daemon=True) for _ in range(workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    ok = sum(1 for v in results.values() if v)
    log(f"[抓取] 完成：命中 {ok} / 总 {len(results)}")
    return results


# ---------------------------------------------------------------------------
# 映射表：罗马音 -> 日文
# ---------------------------------------------------------------------------
def _norm_en(s):
    """英文值归一化：去空白、统一大小写用于比对。"""
    return " ".join((s or "").split()).strip()


_RE_LEAD = re.compile(r"^([A-Z]+)")


def is_code_prefix(value, code):
    """series 值是否只是该作品番号的字母前缀，而非真正的系列名。

    本站历史上混入过一批「series = 番号前缀」的数据（SONE-114 的 series 写成
    SONE、SIVR-157 写成 SIVR）。这类值不是系列，且会让筛选页凭空多出一堆
    「系列」。注意含空格的真系列名不受影响：SIVR-157 的字母前缀是 SIVR，
    与真系列名「S1 VR」不相等，不会被误判。"""
    if not value or not code:
        return False
    m = _RE_LEAD.match(str(code).strip().upper())
    return bool(m) and m.group(1) == str(value).strip().upper()


def build_map(works, fetched, field_en, field_ja, skip_prefix=False):
    """用已有日文值的作品做配对标注。

    skip_prefix=True 时，日文值若只是该作品番号的字母前缀则跳过——避免把
    历史污染（series=SONE）当成有效标注再传播给别的作品。

    返回 (mapping, ambiguous, samples)：
      mapping    : {英文: 日文}  高置信（唯一对应）
      ambiguous  : {英文: [日文...]}  多对多，弃用
      samples    : {英文: 出现次数}
    """
    pairs = defaultdict(Counter)
    for code, w in works.items():
        ja = w.get(field_ja)
        rec = fetched.get(code)
        if not rec:
            continue
        en = _norm_en(rec.get(field_en))
        if not en or not ja:
            continue
        ja = str(ja).strip()
        if skip_prefix and is_code_prefix(ja, code):
            continue
        pairs[en][ja] += 1

    mapping, ambiguous, samples = {}, {}, {}
    for en, ja_counter in pairs.items():
        samples[en] = sum(ja_counter.values())
        if len(ja_counter) == 1:
            # 唯一对应：取票数最高的那个（此时只有一个）
            mapping[en] = ja_counter.most_common(1)[0][0]
        else:
            top, topn = ja_counter.most_common(1)[0]
            total = sum(ja_counter.values())
            # 若压倒性多数（≥80%）指向同一日文，仍视为可用（容忍个别错标）
            if topn / total >= 0.8:
                mapping[en] = top
            else:
                ambiguous[en] = dict(ja_counter)
    return mapping, ambiguous, samples


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true", help="只抓取并建缓存")
    ap.add_argument("--apply", action="store_true", help="实际写盘（默认试算）")
    ap.add_argument("--dry-run", action="store_true", help="试算，不落盘")
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 个")
    ap.add_argument("--refresh", action="store_true", help="忽略缓存重抓")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--series", action="store_true",
                    help="填 series：仅采用能在本地已有日文系列中稳定对应的英文值；"
                         "同时修正 series 被写成番号前缀的污染数据")
    ap.add_argument("--content-id", action="store_true",
                    help="写入 DMM content_id（默认关：全库命中率高，一开就淹没 diff；"
                         "真要接 DMM 交叉源时再开，缓存已是热的，秒级补齐）")
    args = ap.parse_args()

    works = {}
    for fn in sorted(os.listdir(DATA)):
        if fn.endswith(".json"):
            try:
                works[fn[:-5]] = json.load(open(os.path.join(DATA, fn), encoding="utf-8"))
            except Exception as e:
                log(f"[跳过] {fn}: {e}")
    codes = sorted(works)
    if args.limit:
        codes = codes[: args.limit]
        works = {c: works[c] for c in codes}
    log(f"[载入] {len(works)} 部作品")

    fetched = fetch_all(codes, workers=args.workers, refresh=args.refresh)

    # ---- 构建映射表 ----
    log("\n[映射] 构建罗马音→日文映射表…")
    dir_map, dir_amb, dir_samp = build_map(works, fetched, "director_en", "director")
    mk_map, mk_amb, mk_samp = build_map(works, fetched, "maker_en", "maker")
    log(f"  director: 高置信 {len(dir_map)}  歧义 {len(dir_amb)}  "
        f"(英文值覆盖 {len(dir_samp)} 个)")
    log(f"  maker   : 高置信 {len(mk_map)}  歧义 {len(mk_amb)}  "
        f"(英文值覆盖 {len(mk_samp)} 个)")
    for en, ja in list(dir_map.items())[:8]:
        log(f"    {en} → {ja}")

    # ---- series 映射 ----
    # javdatabase 的 series 字段混杂：既有真系列（S1 VR / Idea Pocket VR），
    # 也有大批英文标题片段（"Her mother hits my sexuality harder than..."）。
    # 判据：能在本站已有日文 series 里找到稳定对应（且非番号前缀污染）的，
    # 才是可信系列；其余一律不填。
    se_map, se_amb, se_samp = build_map(
        works, fetched, "series_en", "series", skip_prefix=True
    )
    log(f"\n[series] 映射：高置信 {len(se_map)}  歧义 {len(se_amb)}")
    for en, ja in list(se_map.items())[:10]:
        log(f"    {en[:40]:42s} → {ja[:34]}")

    # 统计"有英文 series 但映射不上"的量，供判断剩余空间
    unmatched_series = Counter()
    for code, rec in fetched.items():
        if not rec:
            continue
        s = _norm_en(rec.get("series_en"))
        if s and s not in se_map:
            unmatched_series[s] += 1
    log(f"  未能映射的英文 series 值 {len(unmatched_series)} 个"
        f"（多为标题片段，不予采用）；其中出现≥3次的："
        f"{sum(1 for v in unmatched_series.values() if v >= 3)} 个")

    # 保存映射表（供人工修订与后续复用）
    en_map = {
        "_comment": "javdatabase 英文值 → 本站日文值映射。由已有日文标注反向生成，"
                    "歧义项已剔除。可人工修订后重跑本脚本。",
        "director": dir_map,
        "maker": mk_map,
        "series": se_map,
        "ambiguous": {"director": dir_amb, "maker": mk_amb, "series": se_amb},
    }
    if args.apply:
        with open(EN_MAP, "w", encoding="utf-8", newline="\n") as f:
            json.dump(en_map, f, ensure_ascii=False, indent=2)
            f.write("\n")
        log(f"\n[保存] {EN_MAP}")

    if args.fetch:
        log("\n[完成] 仅抓取模式，未改动作品数据")
        return

    # ---- 回填 ----
    log("\n[回填] 计算变更…")
    stats = Counter()
    touched = {}
    for code, w in works.items():
        changed = False

        # ---- series 番号前缀污染清扫（与抓取是否命中无关）----
        # 历史遗留：series 被写成自身番号的字母前缀（SONE-114 的 series=SONE）。
        # 这不是系列，会让筛选页凭空多出伪系列条目，必须无条件清掉。
        # 清掉后若本轮能拿到可信日文系列名，会在下面回填，计为 fix_series_prefix。
        polluted = bool(w.get("series")) and is_code_prefix(w["series"], code)
        if polluted:
            w.pop("series", None)
            stats["clear_series_prefix"] += 1
            changed = True

        rec = fetched.get(code)
        if not rec:
            stats["no_hit"] += 1
            if changed:
                w["updated_at"] = time.strftime("%Y-%m-%d")
                touched[code] = w
            continue

        # 直接可信字段
        for f_src, f_dst in (("duration", "duration"), ("date", "date"), ("cover", "cover")):
            v = rec.get(f_src)
            if v and not w.get(f_dst):
                w[f_dst] = v
                stats[f"fill_{f_dst}"] += 1
                changed = True

        # 经映射的日文字段
        for en_key, ja_field, mp in (
            ("director_en", "director", dir_map),
            ("maker_en", "maker", mk_map),
        ):
            if w.get(ja_field):
                continue
            en = _norm_en(rec.get(en_key))
            ja = mp.get(en)
            if ja:
                w[ja_field] = ja
                stats[f"fill_{ja_field}"] += 1
                changed = True
            elif en:
                stats[f"unmapped_{ja_field}"] += 1

        # ---- series 回填 ----
        # 仅采用「能在本地已有日文系列中稳定对应」的英文值；
        # javdatabase 该字段大量是英文标题片段，映射不上的一律不填。
        if args.series and not w.get("series"):
            ja = se_map.get(_norm_en(rec.get("series_en")))
            if ja:
                w["series"] = ja
                stats["fix_series_prefix" if polluted else "fill_series"] += 1
                changed = True

        # content_id 作为附加线索保存（不参与展示，仅交叉核对用）
        if args.content_id:
            cid = rec.get("content_id")
            if cid and not w.get("content_id"):
                w["content_id"] = cid
                stats["fill_content_id"] += 1
                changed = True

        if changed:
            w["updated_at"] = time.strftime("%Y-%m-%d")
            touched[code] = w

    log(f"  可补全作品 {len(touched)} 部")
    for k in sorted(stats):
        log(f"    {k:22s} {stats[k]}")

    if not args.apply:
        log("\n[试算] 未写盘。加 --apply 实际写入。")
        return

    # newline="\n" 是硬性要求：仓库存 LF，而 Windows 文本模式默认会把 \n
    # 写成 \r\n，导致每个被改动的文件在 git 里显示成整份重写，真实 diff 被淹没。
    for code, w in touched.items():
        p = os.path.join(DATA, f"{code}.json")
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(w, f, **DUMP)
            f.write("\n")
        os.replace(tmp, p)
    log(f"\n[写盘] {len(touched)} 部作品已更新")


if __name__ == "__main__":
    main()
