from __future__ import annotations

import unittest

from backend.evidence import EvidenceReviewer
from backend.rules import RuleMatch, RuleSource
from backend.tools import ToolResult


def rule_match(statuses: list[str]) -> RuleMatch:
    rule = {"rule_id": "R1", "order_statuses": statuses}
    return RuleMatch(True, "RULE_FOUND", "found", rule, RuleSource("R1", "规则", "http://localhost/r1", "content"), 0.9, "embedding", "BAAI/bge-m3")


class EvidenceReviewerTest(unittest.TestCase):
    def test_approved_incident_requests_case_action(self) -> None:
        review = EvidenceReviewer().review(
            intent="delivery_incident_damage",
            risk="none",
            needs_order=True,
            order_result=ToolResult(True, "ORDER_FOUND", "found", {"order_code": "OD1", "order_status": "DELIVERING"}),
            order_status="DELIVERING",
            rule_match=rule_match(["DELIVERING"]),
            memory_hits=[],
        )
        self.assertTrue(review.approved)
        self.assertEqual("CREATE_OR_REUSE_CASE", review.case_action)
        self.assertIn("照片", review.required_evidence or "")

    def test_status_conflict_is_reference_only(self) -> None:
        review = EvidenceReviewer().review(
            intent="refund",
            risk="none",
            needs_order=True,
            order_result=ToolResult(True, "ORDER_FOUND", "found", {"order_code": "OD1", "order_status": "WAITING_ACCEPT"}),
            order_status="WAITING_ACCEPT",
            rule_match=rule_match(["COMPLETED"]),
            memory_hits=[{"summary": "上次允许退款"}],
        )
        self.assertTrue(review.approved)
        self.assertEqual("answer", review.decision)
        self.assertIn("仅作为参考", "；".join(review.reasons))

    def test_confirmed_actual_state_overrides_conflict_without_writing_status(self) -> None:
        review = EvidenceReviewer().review(
            intent="food_foreign_object",
            risk="none",
            needs_order=True,
            order_result=ToolResult(True, "ORDER_FOUND", "found", {"order_code": "OD1", "order_status": "DELIVERING"}),
            order_status="DELIVERING",
            rule_match=rule_match(["COMPLETED"]),
            memory_hits=[],
            user_confirmed_actual_state=True,
        )
        self.assertTrue(review.approved)
        self.assertEqual("CREATE_OR_REUSE_CASE", review.case_action)
        self.assertIn("仅作为参考", "；".join(review.reasons))

    def test_high_risk_requires_handoff(self) -> None:
        review = EvidenceReviewer().review(
            intent="food_safety", risk="high", needs_order=False,
            order_result=None, order_status=None, rule_match=rule_match([]), memory_hits=[],
        )
        self.assertEqual("handoff", review.decision)


if __name__ == "__main__":
    unittest.main()
