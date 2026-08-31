# -*- coding: utf-8 -*-
"""女优「在役 / 引退 / 休業」状态字段的规范词表与解析工具。

profile.json 中新增字段约定
---------------------------
  status        当前状态代码：active(在役) / retired(引退) / hiatus(休业·活动休止) / unknown(不明)
  debut_date    出道日期 "YYYY-MM-DD" 或 "YYYY-MM" 或 "YYYY"（精度不足时只留年）
  retire_date   引退日期（同格式）；在役则为 null
  comeback_date 复出日期（同格式）；无则 null
  status_source 状态信息来源（wikipedia-ja / avjoho / minnano / researched / bio-guess）

架构铁律（与 genre / actress 表一致）
-------------------------------------
profile.json 是手写 / 抓取的唯一真相源；actress.csv / actress.xlsx / 站点 data.js
均为派生视图。改状态请改 profile.json（或重跑本抓取器），勿手改进派生表。
"""
import re

# 规范代码 -> 显示名（站点 i18n 从这里取，保证前后端一致）
STATUS_LABELS = {
    "active":  {"ja": "現役",     "zh": "在役"},
    "retired": {"ja": "引退",     "zh": "引退"},
    "hiatus":  {"ja": "活動休止", "zh": "休业"},
    "unknown": {"ja": "不明",     "zh": "不明"},
}


def status_label(code, lang="zh"):
    """返回状态代码的中文/日文显示名；未知代码回退 不明。"""
    return STATUS_LABELS.get(code or "unknown", STATUS_LABELS["unknown"])[lang]


# 日文状态短语 -> 规范代码（按确定性排序：引退最确定，优先判定）
_STATUS_PHRASES = [
    ("引退", "retired"),
    ("活動休止", "hiatus"),
    ("休業", "hiatus"),
    ("休養", "hiatus"),
    ("現役", "active"),
    ("活動中", "active"),
]


def parse_status_from_text(text):
    """从一段日文文本启发式推断状态代码（仅供抓取兜底，非权威）。"""
    if not text:
        return "unknown"
    for phrase, code in _STATUS_PHRASES:
        if phrase in text:
            return code
    return "unknown"


def parse_debut_year(text):
    """从文本提取出道年份，如 '2020年デビュー' -> 2020。"""
    if not text:
        return None
    m = re.search(r"(\d{4})\s*年.*?デビュー", text)
    if m:
        return int(m.group(1))
    m = re.search(r"デビュー\s*[：:]\s*(\d{4})", text)
    if m:
        return int(m.group(1))
    return None


def parse_active_span(text):
    """从 lead 的 '（YYYY年 - 20XX年）' 提取 (start_year, end_year)。

    有结束年 -> 通常已引退；无结束年 -> 仍活跃。"""
    if not text:
        return None, None
    # 有结束年：全角/半角 dash 都兼容
    m = re.search(r"（\s*(\d{4})\s*年\s*(?:-|ー|–|—)\s*(\d{4})\s*年\s*）", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    # 仍活跃（无结束年）
    m = re.search(r"（\s*(\d{4})\s*年\s*(?:-|ー|–|—)\s*）", text)
    if m:
        return int(m.group(1)), None
    return None, None


def parse_comeback_year(text):
    """从文本提取复出年份，如 '2021年復帰' -> 2021。"""
    if not text:
        return None
    m = re.search(r"(\d{4})\s*年.*?復帰", text)
    if m:
        return int(m.group(1))
    return None
