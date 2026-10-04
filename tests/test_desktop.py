from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from backend.config import PROJECT_ROOT
from desktop.chat_window import ChatWindow
from desktop.controller import AgentController
from desktop.pet_window import PetWindow, choose_idle_behavior, clamp_target


class UnusedAgent:
    def invoke(self, question: str) -> dict:
        return {"answer": "unused"}


class DesktopPetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.application = QApplication.instance() or QApplication([])

    def test_idle_probability_boundary(self) -> None:
        self.assertEqual("idle", choose_idle_behavior(0.0))
        self.assertEqual("idle", choose_idle_behavior(0.5999))
        self.assertEqual("move", choose_idle_behavior(0.60))
        self.assertEqual("move", choose_idle_behavior(0.9999))

    def test_target_stays_inside_screen(self) -> None:
        target = clamp_target(QPoint(1000, -50), 0, 0, 800, 600, 220, 220)
        self.assertEqual(QPoint(580, 0), target)

    def test_pet_loads_three_movies(self) -> None:
        controller = AgentController(UnusedAgent())
        chat_window = ChatWindow(controller, 1, "测试启动成功")
        pet = PetWindow(PROJECT_ROOT / "desktop" / "assets", chat_window)
        self.assertEqual({"idle", "gesture", "move"}, set(pet.movies))
        self.assertEqual("idle", pet.current_state)
        pet.tray.hide()
        pet.close()
        chat_window.close()

    def test_chat_renders_source_link_and_provider(self) -> None:
        controller = AgentController(UnusedAgent())
        chat_window = ChatWindow(controller, 1, "测试启动成功")
        chat_window._show_response(
            {
                "answer": "测试回答",
                "decision": "answer",
                "provider": "deepseek",
                "sources": [{"title": "配送规则", "url": "http://localhost:8000/sources/test"}],
            }
        )
        html = chat_window.messages.toHtml()
        self.assertIn("测试回答", html)
        self.assertIn("deepseek", html)
        self.assertIn("DeepSeek API", html)
        self.assertIn("http://localhost:8000/sources/test", html)
        chat_window.close()


if __name__ == "__main__":
    unittest.main()
