from __future__ import annotations

import unittest

from backend.planning import OfflineTaskPlanner


class TaskPlannerTest(unittest.TestCase):
    def test_extracts_date_and_order_code_without_requiring_spaces(self) -> None:
        plan = OfflineTaskPlanner().plan("我10月2号那天的订单OD202610010001其实是这个")
        self.assertEqual("2026-10-02", plan.order_date)
        self.assertEqual("OD202610010001", plan.order_code)

    def test_date_without_order_code_requests_order_tool(self) -> None:
        plan = OfflineTaskPlanner().plan("我10月2号那天的外卖被骑手吃了")
        self.assertTrue(plan.needs_order)
        self.assertEqual("2026-10-02", plan.order_date)


if __name__ == "__main__":
    unittest.main()
