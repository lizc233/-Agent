from __future__ import annotations

import sys
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from backend.agent import CustomerServiceAgent
from backend.auth import ensure_auth_schema
from backend.config import PROJECT_ROOT, load_settings
from backend.database import check_connection
from backend.generation import build_answer_generator
from backend.planning import build_task_planner
from backend.rules import RuleRetriever, load_rules
from backend.source_server import start_source_server
from backend.tools import AgentSession, OrderTools
from .chat_window import ChatWindow
from .controller import AgentController
from .login_dialog import LoginDialog
from .pet_window import PetWindow
from .theme import APP_STYLESHEET


def _startup_logger() -> logging.Logger:
    log_root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_ROOT
    logger = logging.getLogger("kangaroo.startup")
    if not logger.handlers:
        handler = logging.FileHandler(log_root / "startup.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def main() -> int:
    logger = _startup_logger()
    logger.info("main entered")
    application = QApplication(sys.argv)
    logger.info("QApplication created")
    application.setApplicationName("袋鼠可信客服")
    application.setQuitOnLastWindowClosed(False)
    application.setStyleSheet(APP_STYLESHEET)
    try:
        settings = load_settings()
        rules = load_rules(settings)
        logger.info("settings and rules loaded")
    except Exception as error:
        QMessageBox.critical(None, "启动失败", f"配置或客服规则加载失败：{error}")
        return 1

    login_dialog = LoginDialog(settings)
    login_dialog.show()
    login_dialog.raise_()
    login_dialog.activateWindow()
    application.processEvents()
    logger.info("login dialog shown")
    try:
        ensure_auth_schema(settings)
        logger.info("database schema checked")
    except Exception as error:
        QMessageBox.critical(login_dialog, "数据库连接失败", f"无法连接 MySQL：{error}")
        return 1
    if login_dialog.exec() != LoginDialog.DialogCode.Accepted or login_dialog.authenticated_user is None:
        logger.info("login dialog closed without authentication")
        return 0
    authenticated_user = login_dialog.authenticated_user
    database_ok, database_message = check_connection(settings)
    startup_message = "MySQL 已连接，Agent 可以查询当前用户订单。" if database_ok else f"MySQL 暂不可用：{database_message}"
    loading = QProgressDialog("正在从 E 盘加载 bge-m3 语义模型，首次启动可能需要几十秒……", "", 0, 0)
    loading.setWindowTitle("袋鼠客服正在启动")
    loading.setCancelButton(None)
    loading.setMinimumDuration(0)
    loading.show()
    application.processEvents()
    logger.info("embedding loading dialog shown")
    try:
        agent = CustomerServiceAgent(
            OrderTools(settings, AgentSession(authenticated_user.id)),
            RuleRetriever(rules),
            build_answer_generator(settings),
            build_task_planner(settings),
        )
        logger.info("agent initialized")
    except Exception as error:
        loading.close()
        QMessageBox.critical(None, "语义模型加载失败", str(error))
        return 1
    loading.close()
    controller = AgentController(agent)
    user_label = f"{authenticated_user.display_name}（{authenticated_user.user_code}）"
    chat_window = ChatWindow(controller, user_label, startup_message)
    pet = PetWindow(PROJECT_ROOT / "desktop" / "assets", chat_window)
    source_server, source_thread = start_source_server()
    if source_server is None:
        chat_window.messages.append("<p><em>规则来源端口 8000 已被占用；若已有规则服务运行，来源链接仍可访问。</em></p>")
    application.aboutToQuit.connect(lambda: source_server.shutdown() if source_server else None)
    pet.show()
    logger.info("desktop pet shown")
    application._agent_references = (agent, controller, chat_window, pet, source_server, source_thread)
    return application.exec()


if __name__ == "__main__":
    sys.exit(main())
