# -*- coding: utf-8 -*-
"""
fetch_avatars.py —— 为女优抓取 codeav 女优页头像，写回 profile.avatar（热链 DMM）

策略：
  - 优先：遍历该女优目录下作品（从新到旧），取第一部「主演==目录女优」且带
    actress_url 的作品 → 女优详情页 slug → og:image（DMM 头像，热链不防盗链）
  - 兜底：若目录遍历拿不到（如该女优作品在 codeav 上被系统性错归），改用
    codeav 搜索页 q=<女优名> 拿女优 slug
  - 写回 data/actresses/<名>/profile.json 的 avatar 字段

默认 dry-run，--apply 才写盘。
"""
import os
import sys
import re
import json
import argparse
import urllib.request
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACT = os.path.join(ROOT, "data", "actresses")
OUR_DIRS = ["桃乃木かな", "永野一夏", "河北彩花", "白桃はな", "石川澪"]

sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sources.base import UA, normalize_name  # noqa: E402


def get_codeav(code):
    try:
        from sources.codeav import CodeavFetcher
        return CodeavFetcher().fetch(code)
    except Exception:
        return None


def get_actress_url_from_search(name):
    """codeav 搜索页兜底：q=<女优名> 取第一个 /actress/ 链接"""
    try:
        import urllib.parse
        url = "https://www.codeav.net/search?q=" + urllib.parse.quote(name)
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
        m = re.search(r'/actress/([a-z0-9\-]+)', html)
        if m:
            return "https://www.codeav.net/actress/" + m.group(1)
    except Exception:
        return None
    return None


def get_avatar_from_actress_page(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
        m = re.search(r'property="og:image"\s+content="([^"]+)"', html, re.I)
        if m:
            return m.group(1)
        m = re.search(r'"image"\s*:\s*"(https?://[^"]+)"', html)
        if m:
            return m.group(1)
    except Exception:
        return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    apply = args.apply

    results = {}
    for d in OUR_DIRS:
        wd = os.path.join(ACT, d, "works")
        if not os.path.isdir(wd):
            results[d] = {"status": "no_works_dir"}
            continue
        files = sorted([f for f in os.listdir(wd) if f.endswith(".json")], reverse=True)
        actress_url = None
        tried = 0
        for f in files:
            code = f[:-5]
            r = get_codeav(code)
            tried += 1
            if not r:
                continue
            # 只接受「该作品主演 == 当前目录女优」的 actress_url，杜绝误用共演
            if normalize_name(r.get("actress") or "") == d and r.get("actress_url"):
                actress_url = r["actress_url"]
                break
            if tried >= 150:
                break
            time.sleep(0.2)
        # 兜底：搜索页
        if not actress_url:
            actress_url = get_actress_url_from_search(d)
            time.sleep(0.3)
        if not actress_url:
            results[d] = {"status": "no_actress_url", "tried": tried}
            continue
        avatar = get_avatar_from_actress_page(actress_url)
        time.sleep(0.3)
        results[d] = {
            "status": "ok" if avatar else "no_avatar",
            "actress_url": actress_url,
            "avatar": avatar,
        }
        if apply and avatar:
            p = os.path.join(ACT, d, "profile.json")
            w = json.load(open(p, encoding="utf-8"))
            w["avatar"] = avatar
            json.dump(w, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    print("==== 女优头像抓取 ====")
    for d, r in results.items():
        print(f"  {d:12s} {r.get('status'):12s} {r.get('avatar') or r.get('actress_url') or ''}")
    if not apply:
        print("\n(dry-run，未写盘。加 --apply 执行)")


if __name__ == "__main__":
    main()
