#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_images.py —— 抓取女优头像 / 作品封面到 data/images/<女优名>/

用法：
    python scripts/fetch_images.py --actress 桃乃木かな --avatar <图片URL>
    python scripts/fetch_images.py --code IPX-005 --cover <图片URL>

说明（写给初学者）：
    - 图片**入库**到 data/images/，随仓库提交，站点用相对路径引用（如 data/images/桃乃木かな/avatar.jpg）。
    - 头像 / 封面务必只用「宣传 / 封面类肖像」，不含露骨内容，遵守 GitHub ToS。
    - DMM 新站是 JS 渲染，纯 urllib 抓不到真实封面图；要用 Playwright 无头浏览器渲染后取
      og:image / 海报图。下面 download() 是通用下载函数，渲染逻辑留作 TODO（见底部说明）。
"""

import argparse
import os
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 图片入库到 site/assets/img/，站点自包含，便于 GitHub Pages 部署与 file:// 双击打开
IMAGES_DIR = os.path.join(BASE, "site", "assets", "img")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def download(url, dest):
    """把 url 下载到 dest（dest 含文件名）。已存在则跳过。返回是否成功。"""
    if os.path.exists(dest):
        print(f"  [skip] 已存在 {dest}")
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": url})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read()
        with open(dest, "wb") as f:
            f.write(data)
        print(f"  [ok] {len(data)} bytes -> {dest}")
        return True
    except Exception as e:
        print(f"  [warn] 下载失败 {url}: {e}")
        return False


def main():
    ap = argparse.ArgumentParser(description="抓取头像 / 封面到 data/images")
    ap.add_argument("--actress", help="女优名（决定目录）")
    ap.add_argument("--code", help="番号（决定封面文件名）")
    ap.add_argument("--avatar", help="头像图片 URL")
    ap.add_argument("--cover", help="封面图片 URL")
    args = ap.parse_args()

    if args.actress and args.avatar:
        dest = os.path.join(IMAGES_DIR, args.actress, "avatar.jpg")
        download(args.avatar, dest)
    if args.code and args.cover:
        # code 需知道归属女优：简单起见要求同时给 --actress
        if not args.actress:
            ap.error("--code 需配合 --actress 指定归属目录")
        dest = os.path.join(IMAGES_DIR, args.actress, f"{args.code}.jpg")
        download(args.cover, dest)

    print("\n提示：DMM 封面需无头浏览器渲染后取图，参见文件底部 TODO。")


# ---------------------------------------------------------------------------
# TODO（后续增强）：
#   1. 用 Playwright 渲染 codeav/DMM 影片页，取 og:image 作为封面。
#   2. 批量模式：读 data/index.json，对每个缺 cover/avatar 的条目自动补抓。
#   3. 图片体积检查：超过 100MB 报警（GitHub 单文件限制）。
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    main()
