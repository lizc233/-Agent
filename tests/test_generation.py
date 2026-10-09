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

    def explain_refusal(self, question: str, reason: str) -> GeneratedAnswer:
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

    def test_refusal_explanation_uses_second_online_generation(self) -> None:
        class RefusalGenerator(SuccessfulGenerator):
            def explain_refusal(self, question: str, reason: str) -> GeneratedAnswer:
                return GeneratedAnswer("因为订单状态与规则范围不一致，请确认实际情况。", "deepseek-refusal-explanation")

        result = FallbackAnswerGenerator(RefusalGenerator(), OfflineAnswerGenerator()).explain_refusal("问题", "订单状态不一致")
        self.assertEqual("deepseek-refusal-explanation", result.provider)
        self.assertNotIn("无法回答", result.answer)

    def test_refusal_explanation_falls_back_when_api_fails(self) -> None:
        result = FallbackAnswerGenerator(FailedGenerator(), OfflineAnswerGenerator()).explain_refusal("问题", "规则证据不足")
        self.assertEqual("offline-refusal-explanation", result.provider)
        self.assertIn("规则证据不足", result.answer)
        self.assertNotIn("无法回答", result.answer)


if __name__ == "__main__":
    unittest.main()
