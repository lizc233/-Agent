from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .rules import RuleMatch
from .tools import ToolResult


ACTIONABLE_INTENTS = {
    "refund", "after_sales", "delivery_timeout", "delivery_incident_theft",
    "delivery_incident_damage", "food_foreign_object", "food_quality",
    "missing_items", "wrong_order", "wrong_items",
}


@dataclass(frozen=True)
class EvidenceReview:
    approved: bool
    decision: str
    reasons: tuple[str, ...]
    case_action: str | None = None
    required_evidence: str | None = None


class EvidenceReviewer:
    def review(self, *, intent: str, risk: str, needs_order: bool, order_result: ToolResult | None, order_status: str | None, rule_match: RuleMatch, memory_hits: list[Any], user_confirmed_actual_state: bool = False) -> EvidenceReview:
        if risk == "high":
            return EvidenceReview(False, "handoff", ("风险 Agent 判定需要人工介入",))
        if needs_order and (order_result is None or not order_result.ok or not isinstance(order_result.data, dict)):
            return EvidenceReview(False, "reject", ("缺少当前用户可核验的订单事实",))
        if not rule_match.found or rule_match.rule is None or rule_match.source is None:
            return EvidenceReview(False, "abstain", ("没有达到阈值且具有来源的客服规则",))
        statuses = {str(value).upper() for value in rule_match.rule.get("order_statuses", [])}
        reasons = ["订单事实已由当前用户工具核验" if needs_order else "该规则不要求订单事实", "客服规则具有可访问来源"]
        status_conflict = needs_order and statuses and (not order_status or order_status.upper() not in statuses)
        if status_conflict:
            reasons.append("数据库订单状态仅作为参考；本次按用户描述和规则证据处理，不修改订单状态")
        if memory_hits:
            reasons.append("历史记忆仅作为上下文，未覆盖实时订单与规则")
        if intent in ACTIONABLE_INTENTS and needs_order:
            evidence = self._required_evidence(intent)
            return EvidenceReview(True, "answer", tuple(reasons), "CREATE_OR_REUSE_CASE", evidence)
        return EvidenceReview(True, "answer", tuple(reasons))

    @staticmethod
    def _required_evidence(intent: str) -> str | None:
        if intent in {"delivery_incident_damage", "food_foreign_object", "food_quality"}:
            return "请保留餐品、包装，并补充清晰照片。"
        if intent == "delivery_incident_theft":
            return "请保留订单页面、包装状态和与配送人员的沟通记录。"
        if intent in {"missing_items", "wrong_order", "wrong_items"}:
            return "请补充餐品与包装照片，并说明缺少或错送的商品。"
        if intent in {"refund", "after_sales"}:
            return "请说明退款原因，并保留订单页面及相关问题凭证。"
        return None
