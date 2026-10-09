from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import re

import httpx

from .config import Settings


@dataclass(frozen=True)
class TaskPlan:
    intent: str
    needs_order: bool
    order_code: str | None
    order_date: str | None
    risk: str
    provider: str
    fallback_reason: str | None = None


class TaskPlanner:
    def set_context(self, context: dict[str, object]) -> None:
        pass

    def plan(self, question: str) -> TaskPlan:
        raise NotImplementedError


class OfflineTaskPlanner(TaskPlanner):
    ORDER_PATTERN = re.compile(r"(?<![A-Z0-9])OD[A-Z0-9-]{6,}(?![A-Z0-9])", re.IGNORECASE)

    def plan(self, question: str) -> TaskPlan:
        text = question.strip()
        order_match = self.ORDER_PATTERN.search(text)
        date_match = re.search(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})[日号]", text)
        order_date = None
        if date_match:
            year = int(date_match.group(1) or date.today().year)
            order_date = date(year, int(date_match.group(2)), int(date_match.group(3))).isoformat()
        if any(value in text for value in ("别人订单", "他人订单", "绕过验证", "不用验证")):
            return TaskPlan("bypass_identity", False, None, order_date, "unauthorized", "offline-planner")
        if any(value in text for value in ("食物中毒", "吃坏肚子", "食品安全")):
            return TaskPlan("high_risk_complaint", False, None, order_date, "high", "offline-planner")
        if any(value in text for value in ("异物", "头发", "虫子", "塑料", "金属碎屑", "玻璃")):
            return TaskPlan("food_foreign_object", True, order_match.group(0).upper() if order_match else None, order_date, "none", "offline-planner")
        return TaskPlan("unknown", True, order_match.group(0).upper() if order_match else None, order_date, "none", "offline-planner")


class DeepSeekTaskPlanner(TaskPlanner):
    ALLOWED_INTENTS = {"refund", "cancel_order", "delivery_timeout", "delivery_incident_theft", "delivery_incident_damage", "food_foreign_object", "food_safety", "food_quality", "missing_items", "wrong_order", "wrong_items", "payment_issue", "refund_status", "after_sales", "order_lookup", "unknown", "bypass_identity", "high_risk_complaint"}
    ALLOWED_RISKS = {"none", "unauthorized", "high"}
    def __init__(self, settings: Settings, timeout_seconds: float = 20.0) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds
        self.context: dict[str, object] = {}

    def set_context(self, context: dict[str, object]) -> None:
        self.context = context

    def plan(self, question: str) -> TaskPlan:
        today = date.today().isoformat()
        payload = {
            "model": self.settings.deepseek_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": f"你是外卖客服Agent规划器，只提取任务，不回答。系统当前日期是{today}。返回JSON字段：intent、needs_order、order_code、order_date、risk。order_date必须为YYYY-MM-DD；未提及则null；用户只说月日时，选择最近且不晚于当前日期的对应日期。intent从外卖客服业务中选择，包括refund、cancel_order、delivery_timeout、delivery_incident_theft、delivery_incident_damage、food_foreign_object、food_safety、food_quality、missing_items、wrong_order、wrong_items、payment_issue、refund_status、after_sales、order_lookup、unknown、bypass_identity、high_risk_complaint。risk只能为none、unauthorized、high。不得生成SQL或用户ID。"},
                {"role": "user", "content": json.dumps({"current_message": question, "conversation_context": self.context, "instruction": "上下文中的问题类型只是参考，不得限制当前问题的开放式判断；当前表达与旧标签冲突时以当前表达为准。"}, ensure_ascii=False, default=str)},
            ],
        }
        response = httpx.post(f"{self.settings.deepseek_base_url}/chat/completions", headers={"Authorization": f"Bearer {self.settings.deepseek_api_key}"}, json=payload, timeout=self.timeout_seconds)
        response.raise_for_status()
        data = json.loads(response.json()["choices"][0]["message"]["content"])
        intent = str(data.get("intent", "unknown"))
        risk = str(data.get("risk", "none"))
        order_code = str(data["order_code"]).upper() if data.get("order_code") else None
        order_date = data.get("order_date")
        if intent not in self.ALLOWED_INTENTS or risk not in self.ALLOWED_RISKS:
            raise ValueError("DeepSeek planner returned an unsupported intent or risk")
        if order_code and not OfflineTaskPlanner.ORDER_PATTERN.fullmatch(order_code):
            raise ValueError("DeepSeek planner returned an invalid order code")
        if order_date:
            date.fromisoformat(str(order_date))
        return TaskPlan(intent, bool(data.get("needs_order", True)), order_code, order_date, risk, "deepseek-planner")


class FallbackTaskPlanner(TaskPlanner):
    def __init__(self, online: TaskPlanner, offline: TaskPlanner) -> None:
        self.online = online
        self.offline = offline

    def set_context(self, context: dict[str, object]) -> None:
        self.online.set_context(context)
        self.offline.set_context(context)

    def plan(self, question: str) -> TaskPlan:
        try:
            return self.online.plan(question)
        except Exception as error:
            plan = self.offline.plan(question)
            return TaskPlan(plan.intent, plan.needs_order, plan.order_code, plan.order_date, plan.risk, plan.provider, str(error))


def build_task_planner(settings: Settings) -> TaskPlanner:
    return FallbackTaskPlanner(DeepSeekTaskPlanner(settings), OfflineTaskPlanner())
