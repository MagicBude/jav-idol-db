#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""为各女优 profile.json 填入已校验的 DMM 头像链接。
- 已有 profile：保留其余字段，仅补 avatar（原 null 的填真实值）。
- 无 profile：按既有 schema 新建。
聚合项（S1オールスター / 其他作品）跳过。
"""
import json
import os
from datetime import date

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROFILES_DIR = os.path.join(BASE, "data", "actresses")
TODAY = date.today().isoformat()

AVATARS = {
    "八木奈々": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/yagi_nana.jpg",
    "宮西ひかる": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/miyanishi_hikaru.jpg",
    "小野坂ゆいか": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/onosaka_yuika.jpg",
    "村上悠華": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/murakami_yuka.jpg",
    "楓ふうあ": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/kaede_fuua.jpg",
    "楓カレン": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/kaede_karen.jpg",
    "橘メアリー": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/tachibana_mary.jpg",
    "白桃はな": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/hakutou_hana.jpg",
    "石川澪": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/ishikawa_mio.jpg",
    "凪ひかる": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/nagi_hikaru.jpg",
    "本郷愛": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/hongo_ai.jpg",
    "瀬戸環奈": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/seto_kanna.jpg",
    "田野憂": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/tano_yui.jpg",
    "桃乃木かな": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/momonogi_kana.jpg",
    "永野一夏": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/nagano_ichika.jpg",
    "河北彩花": "https://awsimgsrc.dmm.co.jp/pics_dig/mono/actjpgs/kawakita_saika.jpg",
}


def main():
    created, updated, skipped = [], [], []
    for name, url in AVATARS.items():
        adir = os.path.join(PROFILES_DIR, name)
        p = os.path.join(adir, "profile.json")
        os.makedirs(adir, exist_ok=True)
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            if d.get("avatar") == url:
                skipped.append(name)
                continue
            d["avatar"] = url
            d["updated_at"] = TODAY
            updated.append(name)
        else:
            d = {
                "name": name,
                "aliases": [],
                "birthdate": None,
                "height": None,
                "measurements": None,
                "agency": None,
                "avatar": url,
                "bio": "",
                "source": "dmm-avatar-backfill",
                "updated_at": TODAY,
            }
            created.append(name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
            f.write("\n")
    print("新建 profile:", created)
    print("更新 avatar:", updated)
    print("已是最新(跳过):", skipped)


if __name__ == "__main__":
    main()
