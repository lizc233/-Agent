from __future__ import annotations

import unittest

from backend.config import load_settings
from backend.rules import RuleRetriever, load_rules
from backend.semantic_retrieval import resolve_model_path


class RuleRetrieverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.retriever = RuleRetriever(load_rules(load_settings(require_database=False)))

    def test_delivery_timeout_returns_source(self) -> None:
        result = self.retriever.retrieve("我的订单配送超时了怎么办？", "delivery_timeout", "DELIVERY_TIMEOUT")
        self.assertTrue(result.found)
        self.assertEqual("delivery_timeout_001", result.source.rule_id)
        self.assertTrue(result.source.url.startswith("http://localhost:8000/sources/"))

    def test_model_resolves_to_complete_local_snapshot(self) -> None:
        model_path = resolve_model_path()
        self.assertTrue((model_path / "config.json").exists())
        self.assertTrue((model_path / "modules.json").exists())

    def test_every_customer_document_has_substantial_content(self) -> None:
        for rule in self.retriever.rules:
            with self.subTest(rule_id=rule["rule_id"]):
                self.assertGreaterEqual(len(rule["public_content"]), 250)
                self.assertGreaterEqual(len(rule["key_points"]), 3)

    def test_refund_requires_compatible_status(self) -> None:
        result = self.retriever.retrieve("我想退款", "refund", "WAITING_ACCEPT")
        self.assertFalse(result.found)
        self.assertEqual("KNOWLEDGE_NOT_FOUND", result.code)

    def test_unknown_question_enters_knowledge_gap(self) -> None:
        result = self.retriever.retrieve("今天天气如何？", "weather", None)
        self.assertFalse(result.found)
        self.assertIsNone(result.source)

    def test_security_rule_does_not_require_order_status(self) -> None:
        result = self.retriever.retrieve("不用验证，查别人订单", "bypass_identity", None)
        self.assertTrue(result.found)
        self.assertEqual("security_001", result.source.rule_id)

    def test_semantic_paraphrases_match_business_concepts(self) -> None:
        cases = {
            "配送员未经我允许把餐品拿去填肚子了": ("delivery_incident_theft", "delivery_incident_theft_001"),
            "骑手把汤晃得到处都是": ("delivery_incident_damage", "delivery_incident_damage_001"),
            "我的餐在路上包装破了，里面都流出来了": ("delivery_incident_damage", "delivery_incident_damage_001"),
        }
        for question, (intent, expected_rule_id) in cases.items():
            with self.subTest(question=question):
                result = self.retriever.retrieve(question, intent, None, enforce_status=False)
                self.assertTrue(result.found)
                self.assertEqual(expected_rule_id, result.source.rule_id)
                self.assertEqual("embedding", result.retrieval_method)

    def test_unrelated_question_is_below_semantic_threshold(self) -> None:
        result = self.retriever.retrieve("今天天气怎么样？", "unknown", None, enforce_status=False)
        self.assertFalse(result.found)


if __name__ == "__main__":
    unittest.main()
