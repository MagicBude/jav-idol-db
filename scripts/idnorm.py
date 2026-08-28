"""番号（AV ID）归一化与类型识别（借鉴 JavSP avid.py 思路，独立实现）。

设计目标：不同写法指向同一部影片时，生成统一 key，用于匹配/去重。
  IPZ-380 / ipz380 / ipz00380 -> IPZ-380
  FC2-123456 / fc2123456      -> FC2-123456

同时识别番号类型：normal / fc2 / getchu / gyutto / cid（DMM content id）。

为什么不直接抄 JavSP：JavSP 是 GPL-3.0，本仓库 MIT，故仅借鉴其归一化
规则（关键洞察：前导零保留 3 位以内、去除多余前导零），自行实现。

用法：
    from idnorm import normalize_id, guess_av_type
    normalize_id("ipz00380")   -> "IPZ-380"
    guess_av_type("FC2-123456") -> "fc2"
"""

import re

# 普通番号：前缀(2-10 字母) + 分隔符 + 2-5 位数字
_RE_SEP = re.compile(r"^([A-Z]{2,10})[-_](\d{2,5})$")
_RE_NOSEP = re.compile(r"^([A-Z]{2,})(\d{2,5})$")
_RE_FC2 = re.compile(r"^FC2[-_]?(\d{5,7})$", re.I)
_RE_GETCHU = re.compile(r"^GETCHU[-_]?(\d+)$", re.I)
_RE_GYUTTO = re.compile(r"^GYUTTO[-_]?(\d+)$", re.I)


def normalize_id(avid: str) -> str:
    """将番号归一化为统一格式（大写、规范分隔符、规范前导零）。

    规则：
      - 统一大写
      - 带分隔符的标准格式：去除数字部分多余前导零，但保留 <=3 位的前导零
        （如 XVSR060 -> XVSR-060，060 中的 0 是番号一部分；ipz00380 -> IPZ-380）
      - 无分隔符格式：按上述规则补分隔符
    """
    if not avid:
        return ""
    d = avid.strip().upper()
    m = _RE_SEP.match(d)
    if m:
        return "%s-%s" % (m.group(1), _trim_zero(m.group(2)))
    m = _RE_NOSEP.match(d)
    if m:
        return "%s-%s" % (m.group(1), _trim_zero(m.group(2)))
    # FC2 / GETCHU / GYUTTO 等已带前缀的特殊格式，直接返回（正则已归一）
    m = _RE_FC2.match(d)
    if m:
        return "FC2-" + m.group(1)
    m = _RE_GETCHU.match(d)
    if m:
        return "GETCHU-" + m.group(1)
    m = _RE_GYUTTO.match(d)
    if m:
        return "GYUTTO-" + m.group(1)
    return d


def _trim_zero(num: str) -> str:
    """去除多余前导零：数字 >3 位且以 0 开头时去前导零；<=3 位保留。"""
    if len(num) > 3 and num.startswith("0"):
        return num.lstrip("0") or "0"
    return num


def guess_av_type(avid: str) -> str:
    """识别番号类型：normal / fc2 / getchu / gyutto / cid。"""
    d = normalize_id(avid)
    if _RE_FC2.match(d):
        return "fc2"
    if _RE_GETCHU.match(d):
        return "getchu"
    if _RE_GYUTTO.match(d):
        return "gyutto"
    # CID（DMM content id）：纯小写字母数字+下划线，长度 7-19
    # 注意 normalize_id 已转大写，这里用 .lower() 还原后匹配
    if re.match(r"^[a-z\d_]{7,19}$", d.lower()):
        return "cid"
    return "normal"


if __name__ == "__main__":
    tests = ["IPZ-380", "ipz380", "ipz00380", "FC2-123456", "fc2123456",
             "XVSR060", "GETCHU-123", "gyutto-456", "300NTK-784", "abc00177"]
    for t in tests:
        print("%-12s -> id=%-12s type=%s" % (t, normalize_id(t), guess_av_type(t)))
