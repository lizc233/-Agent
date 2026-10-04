from __future__ import annotations

import unittest

from backend.generation import AnswerGenerator, FallbackAnswerGenerator, GeneratedAnswer, OfflineAnswerGenerator


RULE = {
    "title": "配送超时处理规则",
    "public_content": "订单配送超时时，可以协助进入售后处理。",
    "answer_strategy": "不承诺固定赔付金额。",
}


class SuccessfulGenerator(AnswerGenerator):
    def generate(self, question: str, order_status: str | None, rule: dict[str, object]) -> GeneratedAnswer:
        return GeneratedAnswer("在线可信回答", "deepseek")


class FailedGenerator(AnswerGenerator):
    def generate(self, question: str, order_status: str | None, rule: dict[str, object]) -> GeneratedAnswer:
        raise RuntimeError("simulated API failure")


class GenerationTest(unittest.TestCase):
    def test_online_answer_keeps_provider(self) -> None:
        generator = FallbackAnswerGenerator(SuccessfulGenerator(), OfflineAnswerGenerator())
        result = generator.generate("问题", "DELIVERY_TIMEOUT", RULE)
        self.assertEqual("deepseek", result.provider)
        self.assertIsNone(result.fallback_reason)

    def test_api_failure_uses_explicit_offline_provider(self) -> None:
        generator = FallbackAnswerGenerator(FailedGenerator(), OfflineAnswerGenerator())
        result = generator.generate("问题", "DELIVERY_TIMEOUT", RULE)
        self.assertEqual("offline-rule-template", result.provider)
        self.assertIn("simulated API failure", result.fallback_reason)
        self.assertIn("DELIVERY_TIMEOUT", result.answer)


if __name__ == "__main__":
    unittest.main()
