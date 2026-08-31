"""标签中文归一化（本仓库自有实现）。

背景：codeav 等数据源返回的 tags 多为日文/英文裸标签（如「中出し」「ハイビジョン」
「4時間以上作品」），站点直接展示可读性差。本模块加载 data/genre/ 下多份跨源
genre 映射表（见 SOURCES.md），把裸标签翻译、归一化为中文。

设计要点（映射约定）：
- 键（可匹配的原始标签）：各 CSV 的 id / ja(日文) / en(英文) 列
- 值（中文翻译）：优先 zh_cn，否则 zh_tw，否则 translate 列
- 翻译为空 -> 表示该标签应当被丢弃
- 保持顺序、保持去重

用法：
    from genre_norm import normalize_tags
    zh = normalize_tags(["中出し", "ハイビジョン", "4時間以上作品"])
    # -> ["中出", "高清", "4小时以上作品"]
"""

import csv
import json
import os
import zhconv  # 繁->简兜底，统一中文视图用字

_HERE = os.path.dirname(os.path.abspath(__file__))
_GENRE_DIR = os.path.join(_HERE, "..", "data", "genre")

# 作为「键」去匹配原始标签的列；顺序靠前的优先级更高
_KEY_COLS = ("ja", "en", "id")
# 作为「值」的中文翻译列；顺序靠前的优先级更高
_VALUE_COLS = ("zh_cn", "zh_tw", "translate")

# 模块加载时构建一次映射表：raw(原始标签) -> zh(中文)
_MAP: dict[str, str] = {}
_LOADED = False


def _load_once():
    global _MAP, _LOADED
    if _LOADED:
        return
    merged: dict[str, str] = {}
    if not os.path.isdir(_GENRE_DIR):
        _LOADED = True
        return
    # 优先加载单一权威合并表 genre_all.csv（由 scripts/merge_genre.py 生成，
    # 已按日文标签去重并聚合多源）。原始分源文件归档在 data/genre/legacy/ 后
    # 不再被扫描，避免重复标签污染映射表。
    all_csv = os.path.join(_GENRE_DIR, "genre_all.csv")
    if os.path.isfile(all_csv):
        csv_files = [all_csv]
    else:
        csv_files = [
            os.path.join(_GENRE_DIR, fn)
            for fn in sorted(os.listdir(_GENRE_DIR))
            if fn.startswith("genre_") and fn.endswith(".csv")
        ]
    for path in csv_files:
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    value = ""
                    for vc in _VALUE_COLS:
                        v = (row.get(vc) or "").strip()
                        if v:
                            value = v
                            break
                    if not value:
                        continue  # 译文为空 -> 该标签应被丢弃
                    for kc in _KEY_COLS:
                        raw = (row.get(kc) or "").strip()
                        if not raw:
                            continue
                        # 同一原始标签若已被更高优先级来源映射，则不覆盖
                        if raw not in merged:
                            merged[raw] = value
        except (UnicodeDecodeError, KeyError):
            # 容错：单个文件损坏不影响整体
            continue
    # 本仓库 data/zh.json 的 tag_zh 为人工维护的简中映射，优先覆盖（简中优先）
    zh_path = os.path.join(_HERE, "..", "data", "zh.json")
    try:
        with open(zh_path, encoding="utf-8") as f:
            zh = json.load(f)
        for k, v in (zh.get("tag_zh") or {}).items():
            k = (k or "").strip()
            v = (v or "").strip()
            if k and v:
                merged[k] = v
    except Exception:
        pass
    _MAP = merged
    _LOADED = True


def translate_aligned(raw_tags):
    """与 raw_tags 严格 1:1 等长、同序的中文翻译数组。

    用于构建 data.js 的 tags_zh，必须与原始 tags 位置对齐，
    否则前端按 index 并行 zip（tags[i] <-> tags_zh[i]）会把
    邻居的中文翻译错配到别的标签上（如「近親相姦」错位成「罵倒」）。

    规则：
    - 不丢、不减、不去重：每个原始标签都对应一个输出位。
    - 命中映射 -> 中文；未命中 / 映射为空(应删除标签) -> 保留原文。
    - 末尾统一繁->简字形兜底（纯英文/数字/假名不受影响）。
    """
    _load_once()
    if not raw_tags:
        return []
    out = []
    for t in raw_tags:
        if not isinstance(t, str):
            t = str(t)
        t = t.strip()
        if not t:
            out.append("")
            continue
        zh = _MAP.get(t, t)  # 未命中则保留原文
        if not zh:
            zh = t  # 标记为删除的标签：保留原文，维持对齐（避免数组变短错位）
        simp = zhconv.convert(zh, "zh-cn")
        if simp and simp != zh:
            zh = simp
        out.append(zh)
    return out


def normalize_tags(raw_tags):
    """把裸标签列表翻译、归一化为中文标签列表。

    - 命中映射 -> 替换为中文
    - 未命中 -> 原样保留（保证不丢信息）
    - 译文为空（标记为删除的标签）-> 丢弃
    - 保持顺序、去重
    """
    _load_once()
    if not raw_tags:
        return []
    out = []
    seen = set()
    for t in raw_tags:
        if not isinstance(t, str):
            t = str(t)
        t = t.strip()
        if not t:
            continue
        zh = _MAP.get(t, t)  # 未命中则保留原文
        if not zh:
            continue  # 被标记为删除
        # 兜底：无论命中与否，统一将繁体（中文繁体 / 日文旧字体汉字）规范为简体字形，
        # 杜绝中文视图出现「简体女优名 + 繁体标签」混排。纯英文 / 数字 / 假名不受影响。
        simp = zhconv.convert(zh, "zh-cn")
        if simp != zh:
            zh = simp
        if zh in seen:
            continue
        seen.add(zh)
        out.append(zh)
    return out


def coverage(raw_tags):
    """返回 (命中数, 总数)，用于评估映射表覆盖度。"""
    _load_once()
    if not raw_tags:
        return (0, 0)
    hit = sum(1 for t in raw_tags if isinstance(t, str) and t.strip() in _MAP)
    return (hit, len(raw_tags))


if __name__ == "__main__":
    import json
    import glob

    # 自检：统计当前 data/works 里 tags 的中文覆盖率
    _load_once()
    print("映射表规模: %d 条原始标签 -> 中文" % len(_MAP))
    files = glob.glob(os.path.join(_HERE, "..", "data", "works", "*.json"))
    total_tags = 0
    covered = 0
    for fp in files:
        try:
            w = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        ts = w.get("tags") or []
        if not ts:
            continue
        h, n = coverage(ts)
        covered += h
        total_tags += n
    if total_tags:
        print("现有作品 tags: %d 个，可中文映射 %d 个 (%.1f%%)"
              % (total_tags, covered, 100.0 * covered / total_tags))
    # 演示
    demo = ["中出し", "ハイビジョン", "4時間以上作品", "素人", "未知标签XYZ"]
    print("示例:", demo, "->", normalize_tags(demo))
