#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
enrich_posters.py —— 为已抓取的作品补全「多图」字段：poster / background / sample_images
（让站点三视图与详情页预览图真正出现不同图，而非都回退同一封面）。

为什么需要它：
    codeav（沙箱可直连）通常只给竖版封面 cover；而 javbus / javdb 详情页还带
    「预览图缩略图集」(sample images) 与（若有）横版背景。本脚本用这两个源补齐：
      · poster     = 竖版封面（= cover，海报墙视图用）
      · background  = 第一张预览图（横版感，封面视图用；无则回退 cover）
      · sample_images = 全部预览图缩略图（详情页预览图廊 + 未来悬停轮播用）

注意（重要）：
    javbus / javdb 在沙箱里被墙 / 过 CF，需在本机「宽网络 + 系统代理」下跑，
    必要时会自动降级到 Playwright 过 CF。沙箱内请勿执行本脚本。

用法：
    python scripts/enrich_posters.py                 # 补全全部缺 sample_images 的作品
    python scripts/enrich_posters.py --force         # 强制覆盖已存在的字段
    python scripts/enrich_posters.py --dry-run       # 只打印将要变更，不写文件
    python scripts/enrich_posters.py --limit 50      # 只处理前 50 部（调试）
    python scripts/enrich_posters.py --no-browser   # 关闭 Playwright 兜底（纯静态请求）
    python scripts/enrich_posters.py --codes SNIS-001 ABP-002   # 只处理指定番号

字段选择器参考 JavBoss（internal/jav/*）：
    javbus 封面：og:image → a.bigImage → img.cover/.bigImage → #cover
    javbus 预览图：#sample-waterfall a / .sample-waterfall a / .image-gallery-section a /
                  a.tile-item，缩略图取 data-src/data-original/data-lazy-src/src
    javdb 封面：og:image → img.video-cover
    javdb 预览图：同上 tile-item / image-gallery 选择器
"""

import argparse
import json
import os
import sys
import time
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sources import JavbusFetcher, JavdbFetcher  # noqa: E402
from sources.base import ensure_proxy            # noqa: E402

WORKS_DIR = os.path.join(HERE, "..", "data", "works")


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_json_atomic(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, path)


def merge_samples(existing, new):
    """合并预览图：保留原有顺序，追加新链接，去重。"""
    if not new:
        return existing or []
    seen = set(existing or [])
    out = list(existing or [])
    for u in new:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def enrich_one(w, fetchers, force):
    """返回 (changed, reason)。w 为作品 dict（原地修改）。"""
    has_imgs = w.get("sample_images")
    if not force and has_imgs:
        return False, "已有 sample_images，跳过"

    existing_cover = w.get("cover")
    cover = existing_cover          # 默认保留已有封面（可能是绝对 URL）
    samples = []
    for fetcher in fetchers:
        try:
            res = fetcher.fetch(w.get("code", ""))
        except Exception:
            res = None
        if not res:
            continue
        # 仅在本地尚无封面、且抓到的是完整 http(s) URL 时才补封面；
        # 绝不覆盖已有好数据（base.py 的幂等原则），避免 javbus 相对路径覆盖绝对封面。
        if not existing_cover and res.get("cover") and str(res["cover"]).lower().startswith("http"):
            cover = res["cover"]
        if res.get("sample_images"):
            samples = res["sample_images"]
            break  # 拿到预览图即停（javbus 优先）

    if not samples and not cover:
        return False, "两源均无封面/预览图"

    changed = False
    if cover and w.get("cover") != cover:
        w["cover"] = cover
        changed = True
    if not w.get("poster"):
        w["poster"] = cover
        changed = True
    first_sample = samples[0] if samples else None
    if not w.get("background") and first_sample:
        w["background"] = first_sample
        changed = True
    new_samples = merge_samples(w.get("sample_images"), samples)
    if new_samples and new_samples != (w.get("sample_images") or []):
        w["sample_images"] = new_samples
        changed = True

    if not changed:
        return False, "无新字段"
    return True, "poster=%s background=%s samples=%d" % (
        bool(w.get("poster")), bool(w.get("background")), len(w.get("sample_images") or []))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="覆盖已存在的 poster/background/sample_images")
    ap.add_argument("--dry-run", action="store_true", help="只打印变更，不写文件")
    ap.add_argument("--limit", type=int, default=0, help="最多处理 N 部（调试）")
    ap.add_argument("--no-browser", action="store_true", help="关闭 Playwright 兜底，纯静态请求")
    ap.add_argument("--codes", nargs="*", default=[], help="只处理指定番号（文件名为 <番号>.json）")
    args = ap.parse_args()

    ensure_proxy()  # 自动挂系统代理（与本机宽网络抓取一致）

    fetchers = [JavbusFetcher(allow_browser=not args.no_browser),
                JavdbFetcher(allow_browser=not args.no_browser)]

    if args.codes:
        paths = [os.path.join(WORKS_DIR, c + ".json") for c in args.codes]
    else:
        paths = sorted(glob.glob(os.path.join(WORKS_DIR, "*.json")))

    done = 0
    changed_n = 0
    for p in paths:
        if args.limit and done >= args.limit:
            break
        w = load_json(p)
        if not w or not w.get("code"):
            continue
        done += 1
        try:
            ok, reason = enrich_one(w, fetchers, args.force)
        except Exception as e:
            print("  [err] %s: %s" % (w.get("code"), e), file=sys.stderr)
            continue
        if ok:
            changed_n += 1
            print("  [+%s] %s — %s" % ("dry" if args.dry_run else "write", w.get("code"), reason))
            if not args.dry_run:
                save_json_atomic(p, w)
        else:
            print("  [=] %s — %s" % (w.get("code"), reason))
        time.sleep(0.4)  # 礼貌限速

    print("\n处理 %d 部，变更 %d 部%s。" % (done, changed_n, "（dry-run）" if args.dry_run else ""))


if __name__ == "__main__":
    main()
