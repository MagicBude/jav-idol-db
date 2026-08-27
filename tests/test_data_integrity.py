#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""数据完整性冒烟测试。

校验单布局真相源（data/works）与构建产物（data/index.json）的一致性：
  - 每部作品都有 code / title / date（不静默丢数据）
  - build_index 聚合的 work_count 之和 == 有效作品数
  - data/index.json 与脚本实时构建结果一致
  - 真人女优（非聚合项）都有 avatar（封面/头像补全的回归护栏）

运行：
  python -m unittest tests.test_data_integrity -v
  python tests/test_data_integrity.py
"""

import os
import sys
import json
import glob
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import build_index  # noqa: E402


def _count_valid_works():
    """按 code 计数有效作品（与 build_index.load_works 口径一致）。"""
    valid = 0
    for fp in glob.glob(os.path.join(ROOT, "data", "works", "*.json")):
        try:
            with open(fp, encoding="utf-8") as fh:
                w = json.load(fh)
        except Exception:
            continue
        if w.get("code"):
            valid += 1
    return valid


class DataIntegrityTest(unittest.TestCase):

    def test_no_dropped_works(self):
        """单布局下不应有缺 code 的孤儿文件（build_index 会跳过并告警）。"""
        works, dropped = build_index.load_works()
        if dropped:
            msg = "; ".join("%s [%s]" % (fn, r) for fn, r in dropped[:10])
            self.fail("%d 个作品缺字段被跳过：%s" % (len(dropped), msg))
        self.assertGreater(len(works), 1000, "作品数异常偏少，疑似数据丢失")

    def test_work_count_consistency(self):
        """聚合的 work_count 之和 == 有效作品数（无重复计数、无遗漏）。"""
        actresses = build_index.build()
        total = sum(a["work_count"] for a in actresses)
        valid = _count_valid_works()
        self.assertEqual(total, valid,
                         "聚合作品数 %d != 有效作品数 %d" % (total, valid))

    def test_every_actress_has_name(self):
        actresses = build_index.build()
        nameless = [a for a in actresses if not a.get("name")]
        self.assertEqual(nameless, [], "存在缺 name 的女优聚合项")

    def test_real_actresses_have_avatar(self):
        """回归护栏：真人女优（非聚合项）都应已补全 avatar。"""
        aggregate = {"S1オールスター", "其他作品"}
        actresses = build_index.build()
        missing = [a["name"] for a in actresses
                   if a["name"] not in aggregate and not a.get("avatar")]
        self.assertEqual(missing, [], "以下真人女优缺头像：%s" % missing)

    def test_index_json_matches_build(self):
        """已提交的 data/index.json 应与实时构建一致（防止漏跑 build）。"""
        idx_path = os.path.join(ROOT, "data", "index.json")
        self.assertTrue(os.path.isfile(idx_path), "data/index.json 缺失，请先跑 make build")
        with open(idx_path, encoding="utf-8") as fh:
            idx = json.load(fh)
        actresses = build_index.build()
        total = sum(a["work_count"] for a in actresses)
        self.assertEqual(idx["counts"]["works"], total,
                         "index.json 的 works 数与实时构建不一致")
        self.assertEqual(idx["counts"]["actresses"], len(actresses),
                         "index.json 的女优数与实时构建不一致")


if __name__ == "__main__":
    unittest.main(verbosity=2)
