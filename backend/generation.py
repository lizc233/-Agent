from __future__ import annotations

from dataclasses import dataclass
import json

import httpx

from .config import Settings


@dataclass(frozen=True)
class GeneratedAnswer:
    answer: str
    provider: str
    fallback_reason: str | None = None


class AnswerGenerator:
    def generate(self, question: str, order_status: str | None, rule: dict[str, object]) -> GeneratedAnswer:
        raise NotImplementedError


class OfflineAnswerGenerator(AnswerGenerator):
    def generate(self, question: str, order_status: str | None, rule: dict[str, object]) -> GeneratedAnswer:
        status_text = f"数据库显示该订单当前状态为 {order_status}。" if order_status else ""
        key_points = [str(value) for value in rule.get("key_points", [])][:3]
        summary = "；".join(key_points) + "。" if key_points else str(rule["public_content"])
        return GeneratedAnswer(f"{status_text}{summary}", "offline-rule-template")


class DeepSeekAnswerGenerator(AnswerGenerator):
    def __init__(self, settings: Settings, timeout_seconds: float = 20.0) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    def generate(self, question: str, order_status: str | None, rule: dict[str, object]) -> GeneratedAnswer:
        if not self.settings.deepseek_api_key or self.settings.deepseek_api_key.startswith("your_"):
            raise RuntimeError("DEEPSEEK_API_KEY is not configured")
        payload = {
            "model": self.settings.deepseek_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "你是外卖客服回答生成器。只能使用给定的数据库订单状态和客服规则，不得补充规则中没有的金额、时限、结果或平台政策。根据问题挑选最相关的2至3个关键点回答，不要复述整篇文档，控制在180字以内。只返回 JSON：{\"answer\":\"...\"}。",
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "question": question,
                            "order_status": order_status,
                            "rule_title": rule["title"],
                            "rule_content": rule["public_content"],
                            "key_points": rule.get("key_points", []),
                            "answer_strategy": rule["answer_strategy"],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        response = httpx.post(
            f"{self.settings.deepseek_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"},
            json=payload,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        answer = json.loads(content).get("answer", "").strip()
        if not answer:
            raise ValueError("DeepSeek response does not contain a non-empty answer")
        return GeneratedAnswer(answer, "deepseek")


class FallbackAnswerGenerator(AnswerGenerator):
    def __init__(self, online: AnswerGenerator, offline: AnswerGenerator, enabled: bool = True) -> None:
        self.online = online
        self.offline = offline
        self.enabled = enabled

    def generate(self, question: str, order_status: str | None, rule: dict[str, object]) -> GeneratedAnswer:
        try:
            return self.online.generate(question, order_status, rule)
        except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError, RuntimeError, json.JSONDecodeError) as error:
            if not self.enabled:
                raise
            fallback = self.offline.generate(question, order_status, rule)
            return GeneratedAnswer(fallback.answer, fallback.provider, str(error))


def build_answer_generator(settings: Settings) -> AnswerGenerator:
    return FallbackAnswerGenerator(
        DeepSeekAnswerGenerator(settings),
        OfflineAnswerGenerator(),
        enabled=settings.offline_fallback,
    )
