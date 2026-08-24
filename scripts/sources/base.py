# -*- coding: utf-8 -*-
"""
多源抓取框架 · 公共基类与工具
================================================================
每个数据源实现一个 Fetcher，统一接口：

    class XxxFetcher(Fetcher):
        name = "xxx"
        def fetch(self, code, hint=None) -> dict | None:
            ...
            return {
                "code": std,
                "title": str,
                "date": "YYYY-MM-DD" | None,
                "actress": str,            # 主女优（单人作品）
                "actresses": [str],        # 全部女优
                "maker": str | None,
                "label": str | None,
                "series": str | None,
                "duration": int | None,    # 分钟
                "tags": [str],
                "synopsis": str | None,
                "rating": float | None,
                "rating_count": int | None,
                "cover": str | None,       # 封面 URL
                "director": str | None,
                "source": "xxx",
                "source_url": str,
            }
            # 未取到任何关键信息返回 None（交给下一源）

设计原则（对应 jav-idol-db 的需求）：
- 幂等：update_metadata 合并时只填空缺字段，绝不覆盖已有好数据。
- 归属：fetch 得到的 actress 是权威，目录名若冲突说明文件放错了，
  由编排器决定是否搬移到正确女优目录。
"""
import os
import re
import json
from abc import ABC, abstractmethod

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def canon_code(code):
    """把各种写法归一为标准番号：大写、规范分隔符、保留数字原样（不补零/不去零）。
    例：ipx-005 -> IPX-005；IPX005 -> IPX-005；SNOS-3 -> SNOS-3；1stars00145 -> 1STARS-00145。"""
    code = code.strip().upper().replace(" ", "-").replace("_", "-").replace(".", "-")
    if "-" in code:
        return code
    m = re.match(r"^([A-Z]+)(\d+)$", code)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    return code


def clean(text):
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def launch_chrome(no_proxy=None):
    """启动系统 Chrome（channel='chrome'），返回 (playwright, browser)。
    不下载 chromium，直接用已安装的 Chrome。

    no_proxy 默认读环境变量 JAV_NO_PROXY：沙箱直连测试时置 1；
    用户本机默认走系统代理（CF 信任的出口），与 break_cf.py 一致。"""
    if no_proxy is None:
        no_proxy = os.environ.get("JAV_NO_PROXY") == "1"
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    args = ["--no-sandbox"]
    if no_proxy:
        args.append("--no-proxy-server")
    browser = p.chromium.launch(channel="chrome", headless=True, args=args)
    return p, browser


def run_with_browser(fn, locale="ja-JP", no_proxy=None):
    """用系统 Chrome 跑一段 Playwright 逻辑（context-manager 模式，最稳）。
    fn(page) 返回抓取结果或抛异常。自动关闭浏览器。"""
    if no_proxy is None:
        no_proxy = os.environ.get("JAV_NO_PROXY") == "1"
    from playwright.sync_api import sync_playwright
    args = ["--no-sandbox"]
    if no_proxy:
        args.append("--no-proxy-server")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True, args=args)
        ctx = browser.new_context(locale=locale)
        page = ctx.new_page()
        try:
            return fn(page)
        finally:
            try:
                ctx.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass


def click_age_gate(page):
    """点击各类年龄确认墙。返回是否点到了。"""
    for sel in [
        'text=はい、私は18歳以上です', 'text=18歳以上です',
        'a:has-text("はい")', 'text=YES, I AM 18', 'text=確認する',
    ]:
        try:
            b = page.locator(sel).first
            if b.count():
                b.click()
                page.wait_for_timeout(1500)
                return True
        except Exception:
            pass
    return False


def wait_past_cf(page, ready_locator, timeout=45000):
    """轮询等待 Cloudflare 放行 + 年龄墙点击，直到 ready_locator 出现。"""
    import time
    steps = max(1, int(timeout / 1500))
    for _ in range(steps):
        try:
            if ready_locator.count():
                return True
        except Exception:
            pass
        t = page.title()
        if "Just a moment" not in t and "Attention" not in t and "Checking" not in t:
            try:
                if ready_locator.count():
                    return True
            except Exception:
                pass
        click_age_gate(page)
        page.wait_for_timeout(1500)
    try:
        return ready_locator.count() > 0
    except Exception:
        return False


class Fetcher(ABC):
    name = "base"

    @abstractmethod
    def fetch(self, code, hint=None):
        """返回标准化 dict 或 None（未命中）。hint=目录名女优，供交叉校验。"""
        ...

    def close(self):
        """释放资源（Playwright 源重写）。"""
        pass


# ---------------------------------------------------------------------------
# 幂等合并：只填空缺字段，绝不覆盖已有好数据
# ---------------------------------------------------------------------------
_FILL_FIELDS = [
    "title", "date", "actress", "actresses", "maker", "label", "series",
    "duration", "tags", "synopsis", "rating", "rating_count", "cover",
    "director", "source_url",
]


def _is_empty(v):
    if v is None:
        return True
    if isinstance(v, str):
        return v.strip() == "" or v.strip().lower() in ("null", "none", "n/a", "不明")
    if isinstance(v, list):
        return len(v) == 0
    return False


def merge_work(existing, fetched):
    """把 fetched 的非空字段补进 existing（existing 优先）。返回是否发生变更。"""
    if not fetched:
        return False
    changed = False
    for f in _FILL_FIELDS:
        if f not in fetched:
            continue
        new = fetched.get(f)
        old = existing.get(f)
        if _is_empty(old) and not _is_empty(new):
            existing[f] = new
            changed = True
    # 首次拿到 source 标记（标记数据来源优先级最高的那个）
    if existing.get("source") in (None, "pending") and fetched.get("source"):
        existing["source"] = fetched["source"]
        changed = True
    # actresses 合并去重
    if fetched.get("actresses"):
        cur = list(existing.get("actresses") or [])
        for a in fetched["actresses"]:
            if a and a not in cur:
                cur.append(a)
        if cur != existing.get("actresses"):
            existing["actresses"] = cur
            changed = True
    if fetched.get("tags"):
        cur = list(existing.get("tags") or [])
        for t in fetched["tags"]:
            if t and t not in cur:
                cur.append(t)
        if cur != existing.get("tags"):
            existing["tags"] = cur
            changed = True
    if changed:
        existing["updated_at"] = __import__("datetime").date.today().isoformat()
    return changed


def attribution_conflict(dir_actress, fetched_actresses):
    """目录名女优 与 抓取到的女优列表 是否冲突。
    返回 (is_conflict, suggested_dir)。suggested_dir 取抓取主女优。"""
    if not dir_actress or not fetched_actresses:
        return False, None
    # 目录名在抓取列表里 -> 无冲突
    if dir_actress in fetched_actresses:
        return False, None
    # 单人作品且主女优不同 -> 冲突
    if len(fetched_actresses) == 1 and fetched_actresses[0] != dir_actress:
        return True, fetched_actresses[0]
    # 多人作品：目录名不在其中，可能是该女优缺席 -> 冲突（建议保留多人归属需人工）
    return True, None
