# -*- coding: utf-8 -*-
"""
源探测脚本：用真实 Chrome 逐一实测各元数据源的可达性 / 年龄门 / CF 拦截 / 可抓字段。
仅作可行性巡检与留档，不改任何数据。

用法：
  python scripts/probe_sources.py
输出 probe_report.json（每个源：reachable / age_gate / cf_blocked / sample_fields / note）
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sources.base import launch_chrome, click_age_gate, wait_past_cf, clean

# 每个源配一个样例 URL（work 或 actress 向），以及“成功可抓”的正向标记
SOURCES = [
    {"name": "fanza", "kind": "work", "code": "IPX-005",
     "url": "https://www.fanza.co.jp/digital/videoa/-/search/=/searchword=IPX-005/",
     "success": ["IPX-005", "検索結果", "item-title", "作品"]},
    {"name": "r18dev", "kind": "work", "code": "IPX-005",
     "url": "https://r18.dev/videos/vod/movies/search/=/searchword=IPX-005/",
     "success": ["IPX-005", "movies", "title", "R18"]},
    {"name": "javdatabase", "kind": "work", "code": "ipx-005",
     "url": "https://javdatabase.com/movies/ipx-005/",
     "success": ["IPX-005", "IPX", "Movie", "movie"]},
    {"name": "wikipedia-ja", "kind": "actress", "actress": "波多野結衣",
     "url": "https://ja.wikipedia.org/wiki/%E6%B3%A2%E5%A4%9A%E9%87%8E%E7%B5%90%E8%A1%A3",
     "success": ["波多野", "結衣", "出演"]},
    {"name": "minnano", "kind": "actress", "actress": "波多野結衣",
     "url": "https://www.minnano-av.com/search/?q=%E6%B3%A2%E5%A4%9A%E9%87%8E%E7%B5%90%E8%A1%A3",
     "success": ["波多野", "女優", "minnano"]},
    {"name": "avjoho", "kind": "actress", "actress": "波多野結衣",
     "url": "https://avjoho.com/search/?q=%E6%B3%A2%E5%A4%9A%E9%87%8E%E7%B5%90%E8%A1%A3",
     "success": ["波多野", "女優", "avjoho"]},
    {"name": "mgstage", "kind": "work", "code": "ABP-988",
     "url": "https://www.mgstage.com/product/product_detail/ABP-988/",
     "success": ["ABP-988", "出演者", "商品"]},
    {"name": "ideapocket", "kind": "work", "code": "IPX-005",
     "url": "https://www.ideapocket.com/products/ipx-005/",
     "success": ["IPX-005", "IDEAPOCKET", "作品"]},
]


def probe_one(p, browser):
    name = p["name"]
    rec = {"name": name, "kind": p["kind"], "url": p["url"],
           "reachable": False, "age_gate": False, "cf_blocked": False,
           "title": None, "size": 0, "sample_text": "", "success_marker": None,
           "note": ""}
    ctx = browser.new_context(locale="ja-JP")
    # mgstage 年龄门是自定义 adc cookie，预注入绕过
    if name == "mgstage":
        ctx.add_cookies([{"name": "adc", "value": "1",
                          "domain": "mgstage.com", "path": "/"}])
    page = ctx.new_page()
    try:
        page.goto(p["url"], wait_until="domcontentloaded", timeout=30000)
        click_age_gate(page)
        # 等待内容稳定
        page.wait_for_timeout(2500)
        title = page.title()
        rec["title"] = clean(title)[:80]
        html = page.content() or ""
        rec["size"] = len(html)
        # 检测拦截
        low = html.lower()
        if ("just a moment" in low or "cloudflare" in low
                or "challenge-platform" in low or "attention required" in low):
            rec["cf_blocked"] = True
        if ("年齢認証" in html or "年齢確認" in html or "18歳" in html) and name != "mgstage":
            rec["age_gate"] = True
        # 正向标记
        for mk in p["success"]:
            if mk.lower() in low:
                rec["success_marker"] = mk
                rec["reachable"] = True
                break
        # 取样文本
        try:
            txt = clean(page.locator("body").inner_text())[:240]
            rec["sample_text"] = txt
        except Exception:
            pass
        if not rec["reachable"] and not rec["cf_blocked"]:
            rec["note"] = "页面打开但无可识别的作品/女优标记（可能需更精确 URL 或已改版）"
    except Exception as e:
        rec["note"] = "异常: %s" % str(e)[:120]
    finally:
        try:
            ctx.close()
        except Exception:
            pass
        try:
            page.close()
        except Exception:
            pass
    return rec


def main():
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
    report = []
    p, browser = launch_chrome()
    try:
        for cfg in SOURCES:
            print(">> probing %s ..." % cfg["name"], flush=True)
            rec = probe_one(cfg, browser)
            print("   reachable=%s cf=%s age_gate=%s marker=%s title=%s" % (
                rec["reachable"], rec["cf_blocked"], rec["age_gate"],
                rec["success_marker"], rec["title"]), flush=True)
            report.append(rec)
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            p.stop()
        except Exception:
            pass
    path = os.path.join(out_dir, "probe_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print("\n写入 %s" % path, flush=True)
    # 打印摘要
    print("\n=== 探测摘要 ===")
    for r in report:
        flag = "OK " if r["reachable"] else ("CF " if r["cf_blocked"] else "XX ")
        print("  [%s] %-12s 可达=%s CF=%s 年龄门=%s 标记=%s" % (
            flag, r["name"], r["reachable"], r["cf_blocked"], r["age_gate"], r["success_marker"]))


if __name__ == "__main__":
    main()
