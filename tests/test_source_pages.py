from __future__ import annotations

import unittest

from backend.config import load_settings
from backend.rules import load_rules
from backend.source_pages import find_rule, render_rule_page


class SourcePageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rules = load_rules(load_settings(require_database=False))

    def test_rule_page_is_customer_readable(self) -> None:
        rule = find_rule(self.rules, "delivery_timeout_001")
        self.assertIsNotNone(rule)
        page = render_rule_page(rule)
        self.assertIn("配送超时处理规范", page)
        self.assertIn("模拟客服规则", page)
        self.assertIn('charset="utf-8"', page)

    def test_unknown_rule_is_not_found(self) -> None:
        self.assertIsNone(find_rule(self.rules, "missing_rule"))


if __name__ == "__main__":
    unittest.main()
