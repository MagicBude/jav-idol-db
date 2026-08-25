# -*- coding: utf-8 -*-
"""
jav —— 通用 JAV 信息查询工具（CLI）
==================================================================
定位：不做网站，做一个随时可跑的命令行工具，直接查 codeav（及其他源）的元数据。
输出标准化 JSON（番号→标题/标准女优名/日期/封面/厂商/标签…），任何下游都能消费：
文件改名、女优/作品文件夹整理、表格或索引导出、喂给别的脚本……都是它的应用，而非它自己。

复用 scripts/sources 里已有的抓取内核（codeav 用 urllib 直连，沙箱可达，无需浏览器）。

子命令
------
  jav code    <番号>           查单部作品详情
  jav actress <女优名|slug>    查女优：标准名 + 头像 + 全部作品(番号→标题)
  jav search  <关键词>         codeav 搜索：作品 + 女优
  jav normalize <名字>         把女优名/番号归一化（仅本地，不联网）

通用选项
  --json        输出机器可读 JSON（便于管道 / 115 改名脚本消费）
  --source S    数据源（默认 codeav；架构预留 javbus/javdb/fanza，需本机宽网络）
  --no-cache    不使用/不写入本地缓存
  -h            帮助

示例
  python tools/jav.py code STARS-145
  python tools/jav.py actress 白桃はな --json
  python tools/jav.py search 桃乃木かな
"""
import os
import re
import sys
import json
import argparse
import urllib.request
import urllib.parse
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
from sources.base import UA, canon_code, normalize_name, clean  # noqa: E402

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".cache")
ZH_PATH = os.path.join(ROOT, "data", "zh.json")

# --------------------------------------------------------------------------
# 缓存（避免重复请求触发 429；codeav 有 per-IP 频限）
# --------------------------------------------------------------------------
def _cache_get(url):
    p = os.path.join(CACHE_DIR, re.sub(r"[^\w]", "_", url) + ".html")
    if os.path.isfile(p):
        try:
            return open(p, encoding="utf-8").read()
        except Exception:
            return None
    return None

def _cache_put(url, html):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        p = os.path.join(CACHE_DIR, re.sub(r"[^\w]", "_", url) + ".html")
        open(p, "w", encoding="utf-8").write(html)
    except Exception:
        pass

def http_get(url, use_cache=True, retries=2):
    if use_cache:
        c = _cache_get(url)
        if c:
            return c
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            html = urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "ignore")
            if use_cache:
                _cache_put(url, html)
            return html
        except urllib.error.HTTPError as e:
            last = e
            if e.code == 429:
                # 限流：退避后重试
                time.sleep(3 + i * 4)
                continue
            break
        except Exception as e:
            last = e
            time.sleep(1.5)
    raise last or RuntimeError("http_get failed: " + url)


# --------------------------------------------------------------------------
# 中文名映射（可选；data/zh.json 存在则启用）
# --------------------------------------------------------------------------
_ZH = None
def load_zh():
    global _ZH
    if _ZH is not None:
        return _ZH
    _ZH = {"actress_zh": {}, "tag_zh": {}}
    if os.path.isfile(ZH_PATH):
        try:
            d = json.load(open(ZH_PATH, encoding="utf-8"))
            _ZH["actress_zh"] = d.get("actress_zh", {}) or {}
            _ZH["tag_zh"] = d.get("tag_zh", {}) or {}
        except Exception:
            pass
    return _ZH

def zh_actress(name):
    z = load_zh()
    return z["actress_zh"].get(name) or z["actress_zh"].get(normalize_name(name))


# --------------------------------------------------------------------------
# 数据源：codeav（直接复用现有 Fetcher）
# --------------------------------------------------------------------------
def codeav_product(code):
    """查单部作品，返回标准化 dict（含 zh 女优名）。"""
    from sources.codeav import CodeavFetcher
    r = CodeavFetcher().fetch(code)
    if not r:
        return None
    a = r.get("actress")
    if a:
        z = zh_actress(a)
        if z:
            r["actress_zh"] = z
    return r


# --------------------------------------------------------------------------
# 女优页解析
# --------------------------------------------------------------------------
def _parse_mcards(html):
    """从 HTML 提取所有 m-card：返回 [{code,title,cover,rating}]。"""
    cards = []
    for block in re.findall(r'<a class="m-card[^"]*"[^>]*>.*?</a>', html, re.S):
        m = re.search(r'href="[^"]*movie/([a-z0-9\-]+)"', block, re.I)
        if not m:
            continue
        code = canon_code(m.group(1))
        t = re.search(r'<span class="t">(.*?)</span>', block, re.S)
        title = clean(re.sub(r"<[^>]+>", "", t.group(1))) if t else ""
        c = re.search(r'<img[^>]*src="([^"]+)"', block)
        cover = c.group(1) if c else None
        s = re.search(r'<span class="s">(.*?)</span>', block, re.S)
        rating = None
        if s:
            rm = re.search(r"★\s*([\d.]+)", s.group(1))
            if rm:
                rating = float(rm.group(1))
        cards.append({"code": code, "title": title, "cover": cover, "rating": rating})
    # 去重（按 code 保留首次）
    seen, out = set(), []
    for c in cards:
        if c["code"] in seen:
            continue
        seen.add(c["code"])
        out.append(c)
    return out


def codeav_actress(name_or_slug):
    """解析女优页：标准名 + 头像 + 全量作品列表（自动翻页 ?page=2..N）。
    name_or_slug 若为 n- 开头 slug 直接用；否则先搜索页取 slug。"""
    slug = name_or_slug if name_or_slug.startswith("n-") else None
    if not slug:
        shtml = http_get("https://www.codeav.net/search?q=" + urllib.parse.quote(name_or_slug))
        m = re.search(r'/actress/([a-z0-9\-]+)', shtml)
        if not m:
            return None
        slug = m.group(1)

    canonical = name_or_slug
    avatar = None
    works, seen = [], set()
    for page in range(1, 21):
        url = "https://www.codeav.net/actress/" + slug + (f"?page={page}" if page > 1 else "")
        html = http_get(url)
        if page == 1:
            h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.S)
            canonical = clean(re.sub(r"<[^>]+>", "", h1.group(1))) if h1 else name_or_slug
            og = re.search(r'property="og:image"\s+content="([^"]+)"', html, re.I)
            avatar = og.group(1) if og else None
        cards = _parse_mcards(html)
        if not cards:
            break
        added = 0
        for c in cards:
            if c["code"] in seen:
                continue
            seen.add(c["code"])
            works.append(c)
            added += 1
        if added == 0:
            break
        time.sleep(0.3)
    zh = zh_actress(canonical)
    return {
        "source": "codeav",
        "slug": slug,
        "name": canonical,
        "name_zh": zh,
        "avatar": avatar,
        "url": "https://www.codeav.net/actress/" + slug,
        "work_count": len(works),
        "works": works,
    }


# --------------------------------------------------------------------------
# 搜索页解析（hit-row：女优 / 作品 两种）
# --------------------------------------------------------------------------
def codeav_search(query):
    html = http_get("https://www.codeav.net/search?q=" + urllib.parse.quote(query))
    movies, actresses = [], []
    for block in re.findall(r'<a class="hit-row"[^>]*>.*?</a>', html, re.S):
        if "/actress/" in block:
            m = re.search(r'/actress/([a-z0-9\-]+)', block)
            if not m:
                continue
            t = re.search(r'<span class="t"[^>]*>(.*?)</span>', block, re.S)
            name = ""
            if t:
                name = re.split(r"<span", t.group(1))[0]  # 去掉读音嵌套 span
                name = clean(re.sub(r"<[^>]+>", "", name))
            c = re.search(r'<span class="s">\s*(\d+)\s*作品', block)
            av = re.search(r'<img[^>]*src="([^"]+)"', block)
            actresses.append({
                "slug": m.group(1), "name": name,
                "work_count": int(c.group(1)) if c else None,
                "avatar": av.group(1) if av else None,
            })
        elif "/movie/" in block:
            m = re.search(r'/movie/([a-z0-9\-]+)', block, re.I)
            if not m:
                continue
            t = re.search(r'<span class="t"[^>]*>(.*?)</span>', block, re.S)
            title = clean(re.sub(r"<[^>]+>", "", t.group(1))) if t else ""
            cov = re.search(r'<img[^>]*src="([^"]+)"', block)
            movies.append({"code": canon_code(m.group(1)), "title": title,
                           "cover": cov.group(1) if cov else None, "rating": None})
    # 去重
    seen, uniq_m = set(), []
    for w in movies:
        if w["code"] in seen:
            continue
        seen.add(w["code"]); uniq_m.append(w)
    seen, uniq_a = set(), []
    for a in actresses:
        if a["slug"] in seen:
            continue
        seen.add(a["slug"]); uniq_a.append(a)
    return {"query": query, "source": "codeav", "movies": uniq_m, "actresses": uniq_a}


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def out(obj, as_json):
    if as_json:
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        _pretty(obj)


def _pretty(o):
    if "title" in o and "code" in o:  # product
        print(f"番号    : {o['code']}")
        print(f"标题    : {o.get('title')}")
        if o.get("actress_zh"):
            print(f"女优    : {o.get('actress')}（{o['actress_zh']}）")
        else:
            print(f"女优    : {o.get('actress')}")
        print(f"女优URL : {o.get('actress_url')}")
        print(f"日期    : {o.get('date')}")
        print(f"厂商    : {o.get('maker')}")
        print(f"厂牌    : {o.get('label')}")
        print(f"系列    : {o.get('series')}")
        print(f"时长    : {o.get('duration')} 分")
        print(f"评分    : {o.get('rating')}（{o.get('rating_count')} 票）")
        print(f"标签    : {', '.join(o.get('tags') or [])}")
        print(f"封面    : {o.get('cover')}")
        print(f"链接    : {o.get('source_url')}")
    elif "works" in o:  # actress
        zh = f"（{o['name_zh']}）" if o.get("name_zh") else ""
        print(f"女优    : {o['name']}{zh}")
        print(f"头像    : {o.get('avatar')}")
        print(f"链接    : {o.get('url')}")
        print(f"作品数  : 本页 {o['work_count']} 部")
        print("-" * 60)
        for w in o["works"]:
            r = f" ★{w['rating']}" if w.get("rating") else ""
            print(f"  {w['code']:14s} {w['title']}{r}")
    elif "movies" in o:  # search
        if o["actresses"]:
            print("女优匹配:")
            for a in o["actresses"]:
                wc = f"（{a['work_count']} 部）" if a.get("work_count") else ""
                print(f"  {a['name']:14s} {wc} slug={a['slug']}")
            print("-" * 60)
        print(f"作品匹配（{len(o['movies'])}）:")
        for w in o["movies"]:
            r = f" ★{w['rating']}" if w.get("rating") else ""
            print(f"  {w['code']:14s} {w['title']}{r}")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(prog="jav", description="JAV 信息查询工具（codeav 等）")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="输出 JSON")
    common.add_argument("--no-cache", action="store_true", help="不使用本地缓存")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_code = sub.add_parser("code", help="查单部作品", parents=[common])
    p_code.add_argument("code", help="番号，如 STARS-145")

    p_act = sub.add_parser("actress", help="查女优作品", parents=[common])
    p_act.add_argument("name", help="女优名或 slug(n-xxx)")

    p_srch = sub.add_parser("search", help="搜索", parents=[common])
    p_srch.add_argument("query", help="关键词")

    p_norm = sub.add_parser("normalize", help="仅本地归一化", parents=[common])
    p_norm.add_argument("text", help="女优名或番号")

    args = ap.parse_args()
    use_cache = not args.no_cache

    try:
        if args.cmd == "code":
            r = codeav_product(args.code)
            if not r:
                print(f"未找到：{args.code}", file=sys.stderr)
                sys.exit(1)
            out(r, args.json)
        elif args.cmd == "actress":
            r = codeav_actress(args.name)
            if not r:
                print(f"未找到女优：{args.name}", file=sys.stderr)
                sys.exit(1)
            out(r, args.json)
        elif args.cmd == "search":
            r = codeav_search(args.query)
            out(r, args.json)
        elif args.cmd == "normalize":
            if re.match(r"^[A-Za-z]", args.text):
                print(canon_code(args.text))
            else:
                print(normalize_name(args.text))
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
