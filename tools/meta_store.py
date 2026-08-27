# -*- coding: utf-8 -*-
"""
meta_store —— 通用 JAV 元数据持久层（一次抓取，永久存档）
================================================================
定位：把 codeav 抓到的「全量元数据」（标题/日期/女优/片商 maker/厂牌 label/
      系列 series/标签 tags/时长/简介/封面/评分…）落盘到项目的标准仓库：

      data/works/<番号>.json          ← 番号级共享仓库（权威，所有女优文件夹共用一份）
      data/actresses/<女优>/works/<番号>.json  ← 女优目录镜像（供女优页/旧脚本枚举）

并维护 data/_code_meta_index.json（番号 -> 文件路径，指向共享仓库）做 O(1) 缓存命中，
这样之后无论改名、建站、还是回答「这部的标签/片商是什么」都不再重新联网抓取。
合集/共演码（OFJE-/MIZD-/SONE- 等）只存一份，跨女优永不重复抓取。

用法：
  from meta_store import get_meta
  m = get_meta("MIDA-220", actress="八木奈々")   # 命中缓存直接返回；未命中则抓取并落盘
  m["title"]; m["maker"]; m["series"]; m["tags"] ...

设计要点：
  - actress 参数 = 「该文件所属的女优合集」（由调用方按 115 文件夹传入）。
    落盘时把 actress 字段强制写成它，并放到对应女优目录下 —— 保证「谁的文件归谁」。
  - 若 codeav 抓不到（404/限流），仍写一个最小 stub（code+actress+updated_at），
    避免反复打网络。
"""
import os, re, sys, json, time, threading

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 复用 tools/jav.py 的抓取内核（codeav 直连 + 多源回退）
sys.path.insert(0, HERE)
from jav import codeav_product, fetch_product  # noqa: E402
from sources.base import canon_code  # noqa: E402

WORKS_ROOT = os.path.join(ROOT, "data", "actresses")
WORKS_SHARED = os.path.join(ROOT, "data", "works")   # 番号级共享仓库（合集/共演码跨女优复用，权威）
INDEX_PATH = os.path.join(ROOT, "data", "_code_meta_index.json")
ZH_PATH = os.path.join(ROOT, "data", "zh.json")


# ---------------------------------------------------------------------------
def _today():
    return time.strftime("%Y-%m-%d")


def _load_index():
    if os.path.isfile(INDEX_PATH):
        try:
            return json.load(open(INDEX_PATH, encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_index(idx):
    os.makedirs(os.path.dirname(INDEX_PATH), exist_ok=True)
    json.dump(idx, open(INDEX_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def _path_for(actress, code):
    return os.path.join(WORKS_ROOT, actress, "works", f"{code}.json")


def _path_shared(code):
    return os.path.join(WORKS_SHARED, f"{code}.json")


def _zh_actress(name):
    """查 data/zh.json 的中文别名（若有）。"""
    if not name:
        return None
    try:
        d = json.load(open(ZH_PATH, encoding="utf-8"))
        return (d.get("actress_zh", {}) or {}).get(name)
    except Exception:
        return None


_idx_lock = threading.Lock()


def _write_shared(d, ckey):
    """写番号级共享仓库（权威），并刷新索引指向它。"""
    p = _path_shared(ckey)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    with _idx_lock:
        cur = _load_index()
        cur[ckey] = p
        _save_index(cur)


def _write_mirror(d, actress, ckey):
    """写女优目录镜像（供旧脚本/女优页按女优枚举作品）。不改变索引（索引永远指向共享）。"""
    if not actress:
        return
    p = _path_for(actress, ckey)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(d, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def rebuild_index():
    """从磁盘重建索引：data/works（共享，权威，优先） + data/actresses/*/works（仅补充）。
    保证合集/共演码只保留一份权威记录，不被女优镜像覆盖。"""
    idx = {}
    if os.path.isdir(WORKS_SHARED):
        for fn in os.listdir(WORKS_SHARED):
            if fn.endswith(".json"):
                idx[fn[:-5].upper()] = os.path.join(WORKS_SHARED, fn)
    if os.path.isdir(WORKS_ROOT):
        for a in sorted(os.listdir(WORKS_ROOT)):
            wp = os.path.join(WORKS_ROOT, a, "works")
            if os.path.isdir(wp):
                for fn in os.listdir(wp):
                    if fn.endswith(".json"):
                        k = fn[:-5].upper()
                        if k not in idx:
                            idx[k] = os.path.join(wp, fn)
    _save_index(idx)
    return len(idx)


# ---------------------------------------------------------------------------
def get_meta(code, actress=None, use_cache=True):
    """返回全量元数据 dict。

    元数据本质是「番号级」的——一部作品只有一个标题/日期/片商，与它落在哪个女优
    文件夹无关。因此优先读写 data/works/<番号>.json 共享仓库（权威）；女优目录只作镜像，
    供旧脚本/女优页按女优枚举。这样合集/共演码（OFJE-/MIZD-/SONE- 等）只存一份、
    跨女优文件夹永久复用，不会再出现「昨天有今天没」的重复抓取。

    code      : 番号（任意大小写/格式）
    actress   : 该文件所属女优合集（仅用于写女优镜像 + 文件名归属），不影响共享记录的标题/日期。
    use_cache : False 时强制重新抓取。
    """
    ckey = canon_code(code).upper()

    # 缓存命中：优先共享仓库，其次女优镜像（二者都要求 title 非空才算命中）
    if use_cache:
        cand = None
        sp = _path_shared(ckey)
        if os.path.isfile(sp):
            cand = sp
        else:
            idx = _load_index()
            if ckey in idx and os.path.isfile(idx[ckey]):
                cand = idx[ckey]
        if cand:
            try:
                d = json.load(open(cand, encoding="utf-8"))
                if d.get("title"):
                    return d
            except Exception:
                pass

    # 抓取：codeav 优先（沙箱直连、最快）；未命中（404/限流/未收录）则回退
    # javbus/javdb/fanza。其余源需本机宽网络 + Playwright，沙箱会自动优雅降级，
    # 不影响 codeav 命中路径——但到了用户本机就能补上 codeav 没收录的码
    #（合辑/VR/老码常遇到），不再需要人工逐个 WebSearch。
    raw = None
    try:
        raw = codeav_product(code)
    except Exception:
        raw = None
    if not (raw and raw.get("title")):
        try:
            merged, _ = fetch_product(code, ["javbus", "javdb", "fanza"])
            if merged and merged.get("title"):
                raw = merged
        except Exception:
            pass

    if raw and raw.get("title"):
        # 落盘：写共享仓库（权威）+ 女优镜像；actress 取合集女优（保证镜像「谁的文件归谁」）
        owner = actress or raw.get("actress") or ""
        raw["code"] = ckey
        raw["actress"] = owner or raw.get("actress")
        raw["updated_at"] = _today()
        zh = _zh_actress(owner)
        if zh:
            raw["actress_zh"] = zh
        _write_shared(raw, ckey)
        _write_mirror(raw, owner, ckey)
        return raw

    # 抓不到也写 stub 到共享仓库（关键：避免每个女优文件夹都重复打网络 / 重复写空）
    owner = actress or (raw.get("actress") if raw else None) or ""
    if owner:
        d = {"code": ckey, "title": None, "actress": owner,
             "updated_at": _today(), "source": "pending"}
        _write_shared(d, ckey)
        _write_mirror(d, owner, ckey)
        return d
    return {"code": ckey, "title": None}


def get_meta_bulk(codes, actress=None, workers=8):
    """批量抓取并落盘；返回 {code_upper: meta_dict}。并发抓取提速。"""
    from concurrent.futures import ThreadPoolExecutor
    out = {}
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for c, m in zip(codes, ex.map(lambda c: get_meta(c, actress=actress), codes)):
            out[canon_code(c).upper()] = m
    return out


if __name__ == "__main__":
    import sys as _sys
    if len(_sys.argv) > 1:
        code = _sys.argv[1]
        a = _sys.argv[2] if len(_sys.argv) > 2 else None
        print(json.dumps(get_meta(code, actress=a), ensure_ascii=False, indent=2))
