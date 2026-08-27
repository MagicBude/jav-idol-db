#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验 DMM 女优写真图床 avatar URL 是否可直连（200 + image/*）。
不写入任何文件，只打印每个女优命中的 slug，供人工/脚本回填。
"""
import json
import os
import urllib.request
import urllib.error

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(BASE, "data", "actresses")

# 女优名 -> 候选 romaji slug（按可能性排序，优先最可能命中的）
CANDIDATES = {
    "八木奈々": ["yagi_nana"],
    "宮西ひかる": ["miyanishi_hikaru"],
    "小野坂ゆいか": ["onosaka_yuika"],
    "村上悠華": ["murakami_yuka", "murakami_yuuka"],
    "楓ふうあ": ["kaede_fuua", "kaede_fua"],
    "楓カレン": ["kaede_karen"],
    "橘メアリー": ["tachibana_mary"],
    "白桃はな": ["hakutou_hana", "shiromomo_hana"],
    "石川澪": ["ishikawa_mio"],
    "凪ひかる": ["nagi_hikaru"],
    "本郷愛": ["hongo_ai"],
    "瀬戸環奈": ["seto_kanna"],
    "田野憂": ["tano_yui"],
}

TEMPLATE = "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/{slug}.jpg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.dmm.co.jp/",
}


def check(url, timeout=8):
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ct = r.headers.get("Content-Type", "")
            data = r.read(2048)
            return r.status == 200 and ct.startswith("image/") and len(data) > 200
    except Exception:
        return False


def main():
    results = {}
    for name, slugs in CANDIDATES.items():
        hit = None
        for s in slugs:
            url = TEMPLATE.format(slug=s)
            if check(url):
                hit = url
                break
        results[name] = hit
        status = "OK  " if hit else "MISS"
        print("[%s] %s -> %s" % (status, name, hit or "(no candidate hit)"))

    # 同时校验已存在的 3 个
    for name in ["桃乃木かな", "永野一夏", "河北彩花"]:
        p = os.path.join(PROFILES_DIR, name, "profile.json")
        try:
            d = json.load(open(p, encoding="utf-8"))
            a = d.get("avatar")
            if a:
                print("[%s] %s -> %s" % ("OK  " if check(a) else "DEAD", name, a))
        except Exception:
            pass

    print("\n=== 命中汇总 (JSON) ===")
    print(json.dumps({k: v for k, v in results.items() if v}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
