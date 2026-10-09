from __future__ import annotations

import unittest

from backend.case_tools import CaseTools
from backend.config import load_settings
from backend.tools import AgentSession


class CaseToolsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_settings(require_database=False)

    def test_create_case_uses_current_user(self) -> None:
        calls: list[tuple[object, ...]] = []

        def create(*values: object) -> dict[str, object]:
            calls.append(values)
            return {"case_code": "AS1", "case_status": "WAITING_EVIDENCE"}

        result = CaseTools(self.settings, AgentSession(7), create_case_record=create).create_case("od-1", "DELIVERY_DAMAGE", "餐品被洒")
        self.assertTrue(result.ok)
        self.assertEqual((7, "OD-1"), calls[0][1:3])

    def test_closed_case_cannot_be_reopened(self) -> None:
        def get_case(*values: object) -> dict[str, object]:
            return {"case_code": "AS1", "case_status": "CLOSED"}

        result = CaseTools(self.settings, AgentSession(7), get_case_record=get_case).transition_case("AS1", "WAITING_EVIDENCE", "再次处理")
        self.assertEqual("INVALID_CASE_TRANSITION", result.code)

    def test_missing_case_does_not_reveal_other_user(self) -> None:
        users: list[int] = []

        def get_case(settings: object, user_id: int, case_code: str) -> None:
            users.append(user_id)
            return None

        result = CaseTools(self.settings, AgentSession(9), get_case_record=get_case).get_case("AS-OTHER")
        self.assertEqual([9], users)
        self.assertEqual("CASE_NOT_AVAILABLE", result.code)
        self.assertNotIn("其他用户", result.message)


if __name__ == "__main__":
    unittest.main()
