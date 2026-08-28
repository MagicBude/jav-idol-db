"""idnorm 单元测试：番号归一化与类型识别。

覆盖规则：
- 大小写/分隔符归一
- 前导零：>3 位去多余前导零，<=3 位保留（XVSR060 -> XVSR-060，不丢 0）
- 特殊前缀 FC2/GETCHU/GYUTTO
- 类型识别 normal/fc2/getchu/gyutto/cid
"""

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))

from idnorm import normalize_id, guess_av_type  # noqa: E402


class TestNormalizeId(unittest.TestCase):
    def test_case_and_sep(self):
        self.assertEqual(normalize_id("ipz380"), "IPZ-380")
        self.assertEqual(normalize_id("IPZ-380"), "IPZ-380")

    def test_leading_zero_over_three(self):
        # 数字 >3 位，去除多余前导零
        self.assertEqual(normalize_id("ipz00380"), "IPZ-380")

    def test_keep_leading_zero_three_or_less(self):
        # 数字 <=3 位，保留前导零（是番号的一部分）
        self.assertEqual(normalize_id("XVSR060"), "XVSR-060")
        self.assertEqual(normalize_id("xvsr060"), "XVSR-060")

    def test_fc2(self):
        self.assertEqual(normalize_id("fc2123456"), "FC2-123456")
        self.assertEqual(normalize_id("FC2-123456"), "FC2-123456")

    def test_getchu_gyutto(self):
        self.assertEqual(normalize_id("GETCHU-123"), "GETCHU-123")
        self.assertEqual(normalize_id("gyutto-456"), "GYUTTO-456")

    def test_empty(self):
        self.assertEqual(normalize_id(""), "")
        self.assertEqual(normalize_id(None), "")


class TestGuessType(unittest.TestCase):
    def test_fc2(self):
        self.assertEqual(guess_av_type("FC2-123456"), "fc2")
        self.assertEqual(guess_av_type("fc2123456"), "fc2")

    def test_getchu_gyutto(self):
        self.assertEqual(guess_av_type("GETCHU-123"), "getchu")
        self.assertEqual(guess_av_type("GYUTTO-456"), "gyutto")

    def test_cid(self):
        self.assertEqual(guess_av_type("abc00123def"), "cid")

    def test_normal(self):
        self.assertEqual(guess_av_type("IPZ-380"), "normal")
        self.assertEqual(guess_av_type("300NTK-784"), "normal")


if __name__ == "__main__":
    unittest.main()
