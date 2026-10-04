from __future__ import annotations

import unittest

from backend.config import load_settings
from backend.tools import AgentSession, OrderTools


class OrderToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_settings(require_database=False)
        self.audit_rows: list[tuple[object, ...]] = []

    def audit(self, *values: object) -> None:
        self.audit_rows.append(values)

    def test_list_orders_uses_session_user_only(self) -> None:
        queried_users: list[int] = []

        def list_orders(settings: object, user_id: int) -> list[dict[str, str]]:
            queried_users.append(user_id)
            return [{"order_code": "OD1", "order_status": "DELIVERING"}]

        tools = OrderTools(
            self.settings,
            AgentSession(7),
            list_orders=list_orders,
            audit=self.audit,
        )
        result = tools.list_my_orders("查询我的订单")

        self.assertTrue(result.ok)
        self.assertEqual([7], queried_users)
        self.assertEqual("ORDERS_FOUND", result.code)

    def test_unavailable_order_does_not_disclose_ownership(self) -> None:
        def get_order(settings: object, user_id: int, order_code: str) -> None:
            self.assertEqual(7, user_id)
            self.assertEqual("OD-OTHER", order_code)
            return None

        tools = OrderTools(
            self.settings,
            AgentSession(7),
            get_order=get_order,
            audit=self.audit,
        )
        result = tools.get_my_order("od-other", "查询订单")

        self.assertFalse(result.ok)
        self.assertEqual("ORDER_NOT_AVAILABLE", result.code)
        self.assertNotIn("其他用户", result.message)

    def test_today_orders_use_session_user_only(self) -> None:
        queried_users: list[int] = []

        def list_today_orders(settings: object, user_id: int) -> list[dict[str, str]]:
            queried_users.append(user_id)
            return [{"order_code": "OD-TODAY", "order_status": "DELIVERING"}]

        tools = OrderTools(self.settings, AgentSession(7), list_today_orders=list_today_orders, audit=self.audit)
        result = tools.list_my_today_orders("查询今天订单")
        self.assertEqual([7], queried_users)
        self.assertEqual("TODAY_ORDERS_FOUND", result.code)

    def test_invalid_session_user_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OrderTools(self.settings, AgentSession(0))


if __name__ == "__main__":
    unittest.main()
