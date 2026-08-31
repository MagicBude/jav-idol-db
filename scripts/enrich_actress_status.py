# -*- coding: utf-8 -*-
"""抓取女优「在役 / 引退」状态，写回 profile.json（日期用自有作品库，不靠单源猜）。

设计原则（对应「资料库底层要准」的诉求）
----------------------------------------
- 状态 status：优先取 wikipedia-ja 词条 lead 的「元AV女優」标记（高置信 = 引退）；
  否则用**我们自己的作品库**近期活跃度推断（最近 ~18 个月内有作品 -> 在役）。
  单源 wikipedia 对「已引退但未更新词条」会滞后，所以 active 仅作推断、不臆测。
- 出道日期 debut_date：**直接用自有作品库的首作日期**（data/works 实时统计，
  比 wikipedia 的生日/主演表年份可靠得多），标记来源 works-catalog。
- 引退日期 / 复出日期：wikipedia 对该垂直领域几乎不结构化暴露，宁可留 null
  （字段已预留，后续人工补），绝不编造。
- 幂等：仅填空缺字段，绝不覆盖 source=='researched' 的既有好数据；
  已存在 status 且非猜测来源的，跳过（除非 --force）。

年龄墙：wikipedia-ja 的确认墙由 sources.base.click_age_gate 自动点，无需人工。

用法
----
  python scripts/enrich_actress_status.py            # 抓取全部未填女优（浏览器+wiki）
  python scripts/enrich_actress_status.py --force    # 强制重抓全部
  python scripts/enrich_actress_status.py --dry-run  # 只打印，不落盘
"""
import datetime
import glob
import json
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from actress_status import status_label
from sources.base import launch_chrome, click_age_gate, clean

_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
_ACT = os.path.join(_BASE, "data", "actresses")
_WORKS = os.path.join(_BASE, "data", "works")

# 最近 N 个月内有作品 -> 视为在役（与 wikipedia 滞后对冲；放宽到 2 年以免漏判新晋女优）
ACTIVE_WINDOW_MONTHS = 24


def _load_work_stats():
    """扫描作品库，按目录名女优统计首作/最新作日期（复用与 merge_actress 一致的口径）。"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from alias_norm import normalize_actress
    except Exception:
        normalize_actress = lambda n: n
    first, last, cnt = {}, {}, {}
    for fp in glob.glob(os.path.join(_WORKS, "*.json")):
        try:
            w = json.load(open(fp, encoding="utf-8"))
        except Exception:
            continue
        raw = w.get("actress") or ((w.get("actresses") or [None])[0])
        if not raw:
            continue
        name = normalize_actress(raw)
        d = (w.get("date") or "").strip()
        if not d:
            continue
        cnt[name] = cnt.get(name, 0) + 1
        if name not in first or d < first[name]:
            first[name] = d
        if name not in last or d > last[name]:
            last[name] = d
    return {n: {"first_work": first.get(n, ""), "latest_work": last.get(n, ""),
                "work_count": cnt.get(n, 0)} for n in set(list(first) + list(last))}


def _is_former(lead):
    """从 lead 判断是否「元女優」（高置信引退标记）。"""
    if not lead:
        return False, None
    if re.search(r"元[^、，。\s]{0,4}AV女優", lead) or "元AV女優" in lead:
        return True, "wikipedia-ja(元女優)"
    if "引退" in lead:
        return True, "wikipedia-ja(引退記載)"
    return False, None


def _fetch_wikipedia_lead(name, page):
    """只取 lead 第一段（快且稳），避免主演表年份串味。返回 (lead_text, title_ok)。"""
    try:
        page.goto("https://ja.wikipedia.org/wiki/" + urllib.parse.quote(name),
                  wait_until="domcontentloaded", timeout=30000)
        click_age_gate(page)
        page.wait_for_timeout(1800)
        if "Wikipedia" not in (page.title() or ""):
            return "", False
        lead = clean(page.locator("#mw-content-text p").first.inner_text())[:400]
        return lead, True
    except Exception:
        return "", False


def enrich_one(name, page, stats, force=False, dry=False):
    fp = os.path.join(_ACT, name, "profile.json")
    try:
        with open(fp, encoding="utf-8") as f:
            p = json.load(f)
    except Exception:
        print("  - %s: 无 profile.json，跳过" % name)
        return False
    prev = p.get("status")
    prev_src = p.get("status_source")
    if prev and prev_src not in (None, "bio-guess", "unknown") and not force:
        print("  - %s: 已有 status=%s(%s)，跳过" % (name, prev, prev_src))
        return False

    lead, ok = _fetch_wikipedia_lead(name, page)
    former, src = _is_former(lead) if ok else (False, None)

    st = "unknown"
    if former:
        st = "retired"
    else:
        # 用自有作品库近期活跃度推断在役
        lw = (stats.get(name) or {}).get("latest_work", "")
        if lw:
            try:
                y, m = int(lw[:4]), int(lw[5:7] or 1)
                cutoff = datetime.date.today() - datetime.timedelta(
                    days=ACTIVE_WINDOW_MONTHS * 30)
                if datetime.date(y, m, 1) >= cutoff:
                    st = "active"
                    src = src or "works-recency"
            except Exception:
                pass

    # 出道日期：优先自有作品库首作（可靠），否则保留 researched 的 debut_year
    fw = (stats.get(name) or {}).get("first_work", "")
    debut_date = fw or p.get("debut_year")
    if debut_date and not str(debut_date).strip():
        debut_date = None

    # 合并写回
    new = dict(p)
    new["status"] = st
    new["status_source"] = src or ("unknown" if st == "unknown" else "inferred")
    if debut_date:
        new["debut_date"] = str(debut_date)
    # 保持 debut_year 与 debut_date 同步（站点/表兼容）
    if fw and not p.get("debut_year"):
        new["debut_year"] = int(fw[:4])

    if dry:
        print("  [dry] %s -> status=%s(%s) debut=%s src=%s  (wiki_ok=%s lead=%s)" % (
            name, st, status_label(st), debut_date, new["status_source"], ok,
            (lead[:30] + "…") if lead else ""))
        return False

    with open(fp, "w", encoding="utf-8") as f:
        json.dump(new, f, ensure_ascii=False, indent=2, sort_keys=False)
    print("  ✓ %s -> %s(%s) 出道=%s 来源=%s%s" % (
        name, st, status_label(st), debut_date, new["status_source"],
        ("  [wiki:%s]" % (lead[:24] + "…") if ok and lead else "")))
    return True


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="强制重抓全部")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不落盘")
    args = ap.parse_args()

    names = sorted(os.listdir(_ACT))
    names = [n for n in names if os.path.isfile(os.path.join(_ACT, n, "profile.json"))]
    stats = _load_work_stats()
    print("待处理女优 %d 位；作品库统计 %d 位" % (len(names), len(stats)))

    p_chrome, browser = launch_chrome()
    try:
        for name in names:
            enrich_one(name, browser.new_page(), stats, force=args.force, dry=args.dry_run)
            time.sleep(0.4)  # 礼貌节流
    finally:
        try:
            browser.close()
        except Exception:
            pass
        try:
            p_chrome.stop()
        except Exception:
            pass
    print("完成。")


if __name__ == "__main__":
    main()
