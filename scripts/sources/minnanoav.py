# -*- coding: utf-8 -*-
"""
minnano-av.com（みんなのAV）Fetcher —— 女优档案专用源
============================================================================
该站不支持作品级 lookup（社区共识），但女优档案数据全站最全：

  https://www.minnano-av.com/actress{id}.html
  搜索：/search_result.php?search_scope=actress&search_word={名}&search=Go

抓取方式：静态直连
----------------------------------------------------------------
2026-09-07 沙箱实测 urllib 直连 200（搜索页 35KB / 档案页 105KB），
无 Cloudflare，~1s/次；请求间隔 500ms（与 JavBoss 一致）防封。

档案页结构（div.act-profile > table > tr > td > span标签 + p值）：
  - h2 头部：`名 （かな / Roman Name）` → 日文名 / 读音 / 罗马名
  - 別名（多行）→ aliases（剔除与主名重复行、"(注)…"站务备注）
  - 生年月日：`1999年08月25日（現在 27歳）おとめ座` → birthdate/age/星座
  - サイズ：`T162 / B82(Dカップ) / W59 / H81` → height/bust/cup/waist/hips
  - 所属事務所 / 趣味・特技 / ブログ / 公式サイト → 直取
  - AV出演期間：`2018年 - 2022年、2023年 -` → career_periods（原文）
  - デビュー作品：`标题（2018年12月 13日）` → debut_work + debut_date
  - タグ → actress_tags（站点自有人气标签，区别于作品 genre）

不提供：出身地 / 血液型 / 引退具体日期 / bio —— 缺失即 None，不臆造。
"""
import re
import time
import urllib.parse
import urllib.request
import urllib.error

import lxml.html as LH

from .base import Fetcher, UA, clean

BASE = "https://www.minnano-av.com"
_REQUEST_INTERVAL = 0.5
_last_request_at = [0.0]

_ACTRESS_PATH = re.compile(r"actress(\d+)\.html")
_BIRTH_RE = re.compile(r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日")
_SIZE_RE = re.compile(r"T\s*(\d{2,3})", re.I)
_BUST_RE = re.compile(r"B\s*(\d{2,3})", re.I)
_WAIST_RE = re.compile(r"W\s*(\d{2,3})", re.I)
_HIPS_RE = re.compile(r"H\s*(\d{2,3})", re.I)
_CUP_RE = re.compile(r"B\s*\d{2,3}\s*\(\s*([A-Z])\s*カップ", re.I)
_DEBUT_DATE_RE = re.compile(r"（\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日\s*）")
# 別名行里的站务备注/括号限定词
_NOTE_RE = re.compile(r"^\(注\)|^【|^（注")


def _throttle():
    """500ms 间隔限速（模块级，串行抓取安全）。"""
    now = time.monotonic()
    wait = _last_request_at[0] + _REQUEST_INTERVAL - now
    if wait > 0:
        time.sleep(wait)
    _last_request_at[0] = time.monotonic()


def _get(url, referer=None, timeout=20):
    """静态 GET，返回 (status, html)；网络错误抛异常由调用方处理。"""
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.7",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    _throttle()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, ""


def _norm_name(s):
    return " ".join(clean(s).split())


def _strip_qualifier(s):
    """去掉名字后的括号限定词：`田中レモン(旧名)` → `田中レモン`。"""
    s = re.split(r"[(（]", s)[0]
    return _norm_name(s)


# ---------------------------------------------------------------- 搜索
def search_actress(name):
    """按名搜索，返回唯一匹配的档案页 URL；0 或多个匹配返回 None。

    站点两种行为（JavBoss 只处理了第一种）：
    1. 精确命中 → 直接跳档案页（页面自带 act-profile，
       页内与查询名同文本的 actressN.html 链接即档案 URL）
    2. 模糊命中 → 搜索结果页 h2.ttl 链接文本（去括号限定词）
       与查询名完全相等才算命中；多个不同 id 命中视为歧义，拒绝。
    """
    q = urllib.parse.quote(_norm_name(name))
    url = (BASE + "/search_result.php?search_scope=actress&search_word="
           + q + "&search=Go")
    status, html = _get(url)
    if status != 200 or not html:
        return None
    doc = LH.fromstring(html)
    want = _strip_qualifier(_norm_name(name))
    hits = {}

    # 分支 1：直接跳档案页（act-profile 已在页面里）
    if doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " act-profile ")]'):
        for a in doc.xpath('//a[@href]'):
            m = _ACTRESS_PATH.search(a.get("href") or "")
            if m and _strip_qualifier(a.text_content()) == want:
                hits["https://www.minnano-av.com/actress{}.html".format(m.group(1))] = m.group(1)
    else:
        # 分支 2：搜索结果页
        for a in doc.xpath('//h2[contains(@class,"ttl")]/a[@href]'):
            m = _ACTRESS_PATH.search(a.get("href") or "")
            if not m:
                continue
            label = _strip_qualifier(a.text_content())
            if label != want:
                continue
            hits["https://www.minnano-av.com/actress{}.html".format(m.group(1))] = m.group(1)
    if len(hits) != 1:
        return None
    return next(iter(hits))


# ---------------------------------------------------------------- 档案解析
def _parse_header(h2_text):
    """`楓カレン （かえでかれん / Kaede Karen）` → (名, かな, 罗马名)。"""
    text = clean(h2_text)
    m = re.match(r"^(.*?)\s*[（(]\s*(.*?)\s*[）)]\s*$", text)
    if not m:
        return text, None, None
    name = _norm_name(m.group(1))
    inside = m.group(2)
    parts = [p.strip() for p in inside.split("/", 1)]
    kana = parts[0] if parts and parts[0] else None
    roman = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
    return name, kana, roman


def parse_actress_profile(html):
    """解析档案页 HTML → 女优档案 dict；非档案页返回 None。"""
    if not html:
        return None
    doc = LH.fromstring(html)
    prof = doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " act-profile ")]')
    if not prof:
        return None
    prof = prof[0]

    rows = []  # (label, value_text, cell_element)
    for tr in prof.xpath(".//tr"):
        tds = tr.xpath("./td")
        if not tds:
            continue
        cell = tds[0]
        spans = cell.xpath("./span")
        if not spans:
            # h2 头部行（名字）
            h2 = cell.xpath(".//h2")
            if h2:
                rows.append(("__header__", h2[0]))
            continue
        rows.append((clean(spans[0].text_content()), cell))

    out = {}
    aliases = []
    tags = []
    for label, cell in rows:
        if label == "__header__":
            name, kana, roman = _parse_header(cell.text_content())
            out["name"] = name
            out["reading"] = kana
            out["roman_name"] = roman
            continue
        p = cell.xpath("./p")
        value = clean(p[0].text_content()) if p else ""
        if label == "別名":
            alias_raw = clean(p[0].text_content()) if p else ""
            alias = _strip_qualifier(alias_raw)
            if (alias and alias != out.get("name")
                    and not _NOTE_RE.search(alias_raw)
                    and alias not in aliases):
                aliases.append(alias)
        elif label == "生年月日":
            m = _BIRTH_RE.search(value)
            if m:
                out["birthdate"] = "{:04d}-{:02d}-{:02d}".format(
                    int(m.group(1)), int(m.group(2)), int(m.group(3)))
            age = re.search(r"現在\s*(\d{1,2})歳", value)
            if age:
                out["age"] = int(age.group(1))
        elif label == "サイズ":
            for key, rx in (("height", _SIZE_RE), ("bust", _BUST_RE),
                            ("waist", _WAIST_RE), ("hips", _HIPS_RE)):
                m = rx.search(value)
                if m:
                    out[key] = int(m.group(1))
            cm = _CUP_RE.search(value)
            if cm:
                out["cup"] = cm.group(1).upper()
        elif label == "所属事務所":
            # 值在链接文本里
            a = cell.xpath(".//a")
            agency = clean(a[0].text_content()) if a else value
            if agency:
                out["agency"] = agency
        elif label == "趣味・特技":
            if value:
                out["hobby"] = value
        elif label == "AV出演期間":
            if value:
                out["career_periods"] = value
        elif label == "デビュー作品":
            if value:
                out["debut_work"] = value
                dm = _DEBUT_DATE_RE.search(value)
                if dm:
                    out["debut_date"] = "{:04d}-{:02d}-{:02d}".format(
                        int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
        elif label == "ブログ":
            a = cell.xpath(".//a[@href]")
            if a:
                out["blog"] = clean(a[0].get("href"))
        elif label == "公式サイト":
            a = cell.xpath(".//a[@href]")
            if a:
                out["official_site"] = clean(a[0].get("href"))
        elif label == "タグ":
            for ta in cell.xpath(".//a"):
                t = clean(ta.text_content())
                if t:
                    tags.append(t)

    if aliases:
        out["aliases"] = aliases
    if tags:
        out["actress_tags"] = tags

    # 档案页头图（不在 act-profile 内，页面级找主图）
    img = doc.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " act-profile ")]'
                    '/preceding-sibling::*//img/@src')
    if not img:
        img = doc.xpath('//img[contains(@src, "actjpgs")]/@src')
    if img:
        src = clean(img[0])
        if src.startswith("//"):
            src = "https:" + src
        elif src.startswith("/"):
            src = BASE + src
        out["photo_url"] = src

    if not out.get("name"):
        return None
    return out


class MinnanoavActressFetcher:
    """女优档案 lookup（独立类，不进作品 CHAIN——该站无作品级 lookup）。"""

    name = "minnanoav"

    def lookup_actress(self, name):
        """按名取完整档案：搜索 → 档案页解析。未命中返回 None。"""
        url = search_actress(name)
        if not url:
            return None
        status, html = _get(url, referer=BASE + "/")
        if status != 200:
            return None
        info = parse_actress_profile(html)
        if info:
            info["minnano_url"] = url
        return info
