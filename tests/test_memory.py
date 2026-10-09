from __future__ import annotations

import unittest

import numpy as np

from backend.config import load_settings
from backend.memory import ConversationMemory
from backend.tools import AgentSession


class FakeEncoder:
    def encode(self, texts: list[str], **kwargs: object) -> np.ndarray:
        vectors = {"上次餐品里有异物": [1.0, 0.0], "用户上次反馈餐品中发现异物，仍等待照片": [0.98, 0.02], "用户咨询配送超时，问题已经关闭": [0.0, 1.0]}
        return np.asarray([vectors[text] for text in texts], dtype=np.float32)


class ConversationMemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = load_settings(require_database=False)

    def test_recall_queries_current_user_only(self) -> None:
        users: list[int] = []

        def list_memories(settings: object, user_id: int, limit: int) -> list[dict[str, object]]:
            users.append(user_id)
            return [{"id": 1, "summary": "用户上次反馈餐品中发现异物，仍等待照片", "order_code": "OD1", "issue_type": "FOREIGN_OBJECT", "pending_information": "异物照片"}, {"id": 2, "summary": "用户咨询配送超时，问题已经关闭", "order_code": "OD2", "issue_type": "DELIVERY_TIMEOUT", "pending_information": None}]

        memory = ConversationMemory(self.settings, AgentSession(12), list_memory_records=list_memories, encoder=FakeEncoder())
        hits = memory.recall("上次餐品里有异物", threshold=0.8)
        self.assertEqual([12], users)
        self.assertEqual([1], [hit.memory_id for hit in hits])

    def test_remember_binds_current_user_and_session(self) -> None:
        calls: list[tuple[object, ...]] = []

        def insert(*values: object) -> int:
            calls.append(values)
            return 33

        memory = ConversationMemory(self.settings, AgentSession(12), insert_memory_record=insert)
        self.assertEqual(33, memory.remember(8, "等待用户补充图片"))
        self.assertEqual((12, 8), calls[0][1:3])

    def test_start_session_binds_current_user(self) -> None:
        calls: list[tuple[object, ...]] = []

        def start(*values: object) -> int:
            calls.append(values)
            return 18

        memory = ConversationMemory(self.settings, AgentSession(12), start_session_record=start)
        session_id, session_code = memory.start_session()
        self.assertEqual(18, session_id)
        self.assertEqual(12, calls[0][1])
        self.assertTrue(session_code.startswith("CS"))


if __name__ == "__main__":
    unittest.main()
