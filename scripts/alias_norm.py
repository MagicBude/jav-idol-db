#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""alias_norm.py —— 女优别名归一化（借鉴 JavSP data/actress_alias.json，独立实现）

数据来源：data/actress/alias.json（取自 JavSP，GPL-3.0，见同目录 SOURCES.md），
内容为 canonical 名 -> 全部别名（含简/繁中、旧艺名）的映射。

设计原则（以 JavSP 别名表为准，整组合并 + 冲突告警）：
  · 楓カレン 与 田中レモン 确为同一人：JavSP 表以 田中レモン 为 canonical，把
    楓カレン / 楓花戀 / 枫花恋 均列为其别名；中文习惯还称 枫可怜 / 楓可怜。
  · 「整组 cluster 并入」：对精选女优 c，除取 c 作为 canonical key 的别名列表外，
    还把「把 c 列为别名」的每一个 canonical 的整组别名都并入，确保 田中レモン /
    田中檸檬 等不会因 c 不是 key 而被整组丢弃。
  · normalize_actress / actress_search_terms / expand_query：均基于上面的 cluster；
    同名若同时落入 ≥2 个精选 cluster，则视为 JavSP 表「真实误并」，仅告警、不自动合并。

本模块只做数据查询，不修改任何源文件。
"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALIAS_PATH = os.path.join(BASE, "data", "actress", "alias.json")

_loaded = False
_ALIAS = {}
_REV = {}
_CURATED_ALIASES = {}
_NAME_TO_CURATED = {}


def _curated_set():
    d = os.path.join(BASE, "data", "actresses")
    out = set()
    if os.path.isdir(d):
        for n in os.listdir(d):
            if os.path.isdir(os.path.join(d, n)) and n not in ("S1オールスター", "其他作品"):
                out.add(n)
    return out


def _load_once():
    global _loaded, _ALIAS, _REV, _CURATED_ALIASES, _NAME_TO_CURATED
    if _loaded:
        return
    try:
        _ALIAS = json.load(open(ALIAS_PATH, encoding="utf-8"))
    except Exception:
        _ALIAS = {}
    _REV = {}
    for canon, alist in _ALIAS.items():
        _REV.setdefault(canon, set()).add(canon)
        for a in alist:
            _REV.setdefault(a, set()).add(canon)
    cur = _curated_set()
    for c in cur:
        cluster = set([c])
        # 1) c 自身作为 canonical key 的别名列表
        if c in _ALIAS:
            cluster.update(_ALIAS[c])
        # 2) 「把 c 列为别名」的每一个 canonical 的整组别名都并入
        #    （处理 JavSP 以他人为 canonical、c 仅作 alias 的情形，如 楓カレン 挂
        #     在 田中レモン 名下，使其整组别名不因 c 不是 key 而被丢弃）
        for canon in _REV.get(c, set()):
            cluster.add(canon)
            cluster.update(_ALIAS.get(canon, []))
        _CURATED_ALIASES[c] = sorted(t for t in cluster if t)
    # 反向索引：任一别名/变体 -> 首个命中的精选 canonical
    for c, terms in _CURATED_ALIASES.items():
        for t in terms:
            _NAME_TO_CURATED.setdefault(t, c)
    # 冲突检测：同一名字若同时属于 ≥2 个精选 cluster，说明 JavSP 表存在「真实误并」，
    # 不应自动合并；此处仅告警，不改写任何数据。
    collisions = {}
    for c in cur:
        for t in _CURATED_ALIASES[c]:
            owners = [cc for cc in cur if t in _CURATED_ALIASES[cc]]
            if len(owners) > 1:
                collisions.setdefault(t, sorted(set(owners)))
    if collisions:
        import sys
        sys.stderr.write("WARN alias-collisions (NOT auto-merged): %s\n"
                         % json.dumps(collisions, ensure_ascii=False))
    _loaded = True


def normalize_actress(name):
    """把某个女优名归一到精选 canonical（整组 cluster 并入；冲突名不改写）。"""
    _load_once()
    if not name:
        return name
    if name in _CURATED_ALIASES:  # 已是精选 canonical
        return name
    return _NAME_TO_CURATED.get(name, name)  # 经 cluster 反查归一（如 田中レモン->楓カレン）


def actress_search_terms(name):
    """返回某女优名对应的全部可搜索别名（用于站点搜索匹配）。"""
    _load_once()
    n = normalize_actress(name)
    return _CURATED_ALIASES.get(n, [n])


def expand_query(q):
    """给定自由文本，返回可能命中的精选女优名集合（用于搜索）。"""
    _load_once()
    ql = (q or "").strip().lower()
    if not ql:
        return set()
    out = set()
    for c, terms in _CURATED_ALIASES.items():
        if any(ql == t.lower() or ql in t.lower() for t in terms):
            out.add(c)
    for a, canons in _REV.items():
        if ql == a.lower() or ql in a.lower():
            for cc in canons:
                if cc in _CURATED_ALIASES:
                    out.add(cc)
    return out


if __name__ == "__main__":
    # 自检
    cases = ["楓カレン", "枫花恋", "田中レモン", "田中檸檬",
             "永野いち夏", "桃乃木香奈"]
    for t in cases:
        print("%-10s -> normalize=%s  search=%s" % (
            t, normalize_actress(t), actress_search_terms(t)))
    print("expand('枫花恋')   =", expand_query("枫花恋"))
    print("expand('田中レモン') =", expand_query("田中レモン"))
