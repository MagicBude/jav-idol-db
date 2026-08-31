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


def human_mode():
    """人工介入模式开关。置环境变量 JAV_HUMAN=1 开启。

    开启后：
    - 无头浏览器改为「有头」（可见窗口），方便用户手动操作；
    - 遇到 Cloudflare 等自动化过不去的验证码时，wait_past_cf 会暂停并提示
      用户在弹出的浏览器里完成验证，按 Enter 后继续抓取。
    年龄确认墙（はい、私は18歳以上です）不受影响——click_age_gate 本就自动点，
    无需人工。"""
    return os.environ.get("JAV_HUMAN") == "1"


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


def upgrade_cover_url(url):
    """把 DMM 降分辨率图床换成标准高清源。

    - awsimgsrc.dmm.co.jp/pics_dig/... 是 DMM 的「优化/降级」图床（常返回压缩图），
      标准高清源是 pics.dmm.co.jp/...（路径少了 pics_dig 一段）。
    - 顺带把小图 ps.jpg 升到高清 pl.jpg。
    其余域名原样返回。"""
    if not url:
        return url
    u = url.replace("awsimgsrc.dmm.co.jp/pics_dig/", "pics.dmm.co.jp/")
    u = re.sub(r"(\w+)ps\.jpg$", r"\1pl.jpg", u)
    return u


def launch_chrome(no_proxy=None, headless=None):
    """启动系统 Chrome（channel='chrome'），返回 (playwright, browser)。
    不下载 chromium，直接用已安装的 Chrome。

    no_proxy 默认读环境变量 JAV_NO_PROXY：沙箱直连测试时置 1；
    用户本机默认走系统代理（CF 信任的出口），与 break_cf.py 一致。
    headless 默认 True；JAV_HUMAN=1 时自动转有头（可见窗口供人工操作）。"""
    if no_proxy is None:
        no_proxy = os.environ.get("JAV_NO_PROXY") == "1"
    if headless is None:
        headless = not human_mode()
    from playwright.sync_api import sync_playwright
    p = sync_playwright().start()
    args = ["--no-sandbox"]
    if no_proxy:
        args.append("--no-proxy-server")
    browser = p.chromium.launch(channel="chrome", headless=headless, args=args)
    return p, browser


def run_with_browser(fn, locale="ja-JP", no_proxy=None, headless=None):
    """用系统 Chrome 跑一段 Playwright 逻辑（context-manager 模式，最稳）。
    fn(page) 返回抓取结果或抛异常。自动关闭浏览器。
    headless 默认 True；JAV_HUMAN=1 时自动转有头。"""
    if no_proxy is None:
        no_proxy = os.environ.get("JAV_NO_PROXY") == "1"
    if headless is None:
        headless = not human_mode()
    from playwright.sync_api import sync_playwright
    args = ["--no-sandbox"]
    if no_proxy:
        args.append("--no-proxy-server")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=headless, args=args)
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


def wait_past_cf(page, ready_locator, timeout=45000, human=None):
    """轮询等待 Cloudflare 放行 + 年龄墙点击，直到 ready_locator 出现。

    human：是否允许人工介入。默认 None 时跟随 human_mode()（JAV_HUMAN=1）。
    当轮询超时 CF 仍未放行：
      - human=False：直接返回 False（该源放弃，交给下一源/标记 pending）；
      - human=True ：暂停并提示用户在弹出的浏览器里手动完成验证，按 Enter
        后继续轮询一小段，仍失败才返回 False。"""
    import time
    if human is None:
        human = human_mode()
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
    # 轮询结束仍未放行
    if human:
        try:
            page_title = page.title()
        except Exception:
            page_title = "(无法读取标题)"
        input(
            "\n⏸ Cloudflare 验证尚未通过。请在已经打开的浏览器窗口中手动完成验证"
            f"（当前页面标题：{page_title}），\n   完成后回到此处按 Enter 键继续…"
        )
        # 用户手动操作后再次轮询一小段
        for _ in range(20):
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


# ---------------------------------------------------------------------------
# 女优名归一化（去括号别名、统一已知变体读法）
# 用于跨源/目录名一致性比对，避免因「河北彩花（河北彩伽）」「永野いち夏」等写法
# 差异导致的误判。
# ---------------------------------------------------------------------------
_NAME_VARIANTS = {
    "永野いち夏": "永野一夏",   # いち夏 = 一夏 假名读法
    "永野一夏": "永野一夏",
    "河北彩花": "河北彩花",
    "河北彩伽": "河北彩花",
    "白桃はな": "白桃はな",
    "桃乃木かな": "桃乃木かな",
    "石川澪": "石川澪",
}

def normalize_name(n):
    """女优名归一化：去括号别名 + 已知变体映射。"""
    if not n:
        return ""
    s = n.strip()
    for sep in ("（", "("):
        if sep in s:
            s = s.split(sep)[0].strip()
    return _NAME_VARIANTS.get(s, s)
