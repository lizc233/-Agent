from __future__ import annotations

from html import escape

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QScrollArea, QTextBrowser, QToolButton, QVBoxLayout, QWidget

from .controller import AgentController


class ResponseCard(QFrame):
    choice_selected = Signal(str, str, str)

    def __init__(self, result: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("responseCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        answer = QLabel(str(result.get("answer", "未生成回答")), self)
        answer.setWordWrap(True)
        answer.setObjectName("answerText")
        layout.addWidget(answer)
        sources = result.get("sources", [])
        if sources:
            links = "；".join(
                f'<a href="{escape(str(item.get("url", "")), quote=True)}">{escape(str(item.get("title", "规则文档")))}</a>'
                for item in sources
            )
            source = QLabel(f"依据：{links}", self)
            source.setWordWrap(True)
            source.setObjectName("sourceText")
            source.setTextFormat(Qt.TextFormat.RichText)
            source.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            source.setOpenExternalLinks(True)
            layout.addWidget(source)
        detail_button = QToolButton(self)
        detail_button.setText("查看可信依据与 Agent 执行详情")
        detail_button.setCheckable(True)
        detail_button.setArrowType(Qt.ArrowType.RightArrow)
        detail_button.setObjectName("detailToggle")
        layout.addWidget(detail_button, 0, Qt.AlignmentFlag.AlignLeft)
        detail_browser = QTextBrowser(self)
        detail_browser.setOpenExternalLinks(True)
        detail_browser.setVisible(False)
        detail_browser.setMaximumHeight(150)
        detail_browser.setHtml(self._detail_html(result))
        detail_button.toggled.connect(lambda checked: self._toggle_details(detail_button, detail_browser, checked))
        layout.addWidget(detail_browser)
        choices = result.get("choices", [])
        self.choice_buttons: list[QPushButton] = []
        if choices:
            title = QLabel("请选择要继续处理的订单：", self)
            title.setObjectName("choiceTitle")
            layout.addWidget(title)
            for choice in choices:
                button = QPushButton(str(choice.get("label", choice.get("value", "选择"))), self)
                button.setObjectName("orderChoice")
                self.choice_buttons.append(button)
                button.clicked.connect(lambda checked=False, item=choice, selected=button: self._select_choice(selected, item))
                layout.addWidget(button)

    def _select_choice(self, selected: QPushButton, choice: dict) -> None:
        if not selected.isEnabled():
            return
        for button in self.choice_buttons:
            button.setEnabled(False)
            button.setProperty("selected", button is selected)
            button.style().unpolish(button)
            button.style().polish(button)
        self.choice_selected.emit(str(choice.get("question", "")), str(choice.get("value", "")), str(choice.get("label", "选择")))

    @staticmethod
    def _toggle_details(button: QToolButton, browser: QTextBrowser, checked: bool) -> None:
        browser.setVisible(checked)
        button.setArrowType(Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow)

    @staticmethod
    def _detail_html(result: dict) -> str:
        runs = result.get("agent_runs", [])
        run_text = "；".join(f"{escape(str(item.get('agent', 'Agent')))}：{'完成' if item.get('ok') else '失败'} {float(item.get('duration_ms', 0)):.1f}ms" for item in runs)
        trace = " → ".join(escape(str(item)) for item in result.get("trace", []))
        return f"<p><b>并行委派：</b>{run_text or '无'}</p><p><b>执行链路：</b>{trace or '无'}</p><p><b>任务规划：</b>{escape(str(result.get('planner_provider', 'local-policy')))}</p><p><b>决策：</b>{escape(str(result.get('decision', 'unknown')))}　<b>回答方式：</b>{escape(str(result.get('provider', 'unknown')))}</p>"


class ChatWindow(QMainWindow):
    response_displayed = Signal(str)

    def __init__(self, controller: AgentController, user_label: str, startup_message: str) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("袋鼠可信客服")
        self.resize(620, 680)
        container = QWidget(self)
        root = QVBoxLayout(container)
        identity = QLabel(f"当前账户 · {user_label}", container)
        identity.setObjectName("identityLabel")
        root.addWidget(identity)
        self.scroll = QScrollArea(container)
        self.messages = QTextBrowser(container)
        self.messages.hide()
        self.scroll.setWidgetResizable(True)
        self.scroll.setObjectName("messageScroll")
        self.message_host = QWidget(self.scroll)
        self.message_layout = QVBoxLayout(self.message_host)
        self.message_layout.setContentsMargins(6, 6, 6, 6)
        self.message_layout.setSpacing(10)
        self.message_layout.addStretch()
        self.scroll.setWidget(self.message_host)
        root.addWidget(self.scroll)
        self._add_system_message(startup_message)
        input_layout = QHBoxLayout()
        self.question_input = QLineEdit(container)
        self.question_input.setPlaceholderText("例如：我的订单配送超时了怎么办？")
        self.send_button = QPushButton("发送", container)
        input_layout.addWidget(self.question_input)
        input_layout.addWidget(self.send_button)
        root.addLayout(input_layout)
        self.setCentralWidget(container)
        self.send_button.clicked.connect(self._submit)
        self.question_input.returnPressed.connect(self._submit)
        self.controller.response_ready.connect(self._show_response)
        self.controller.response_failed.connect(self._show_error)

    def _add_widget(self, widget: QWidget) -> None:
        self.message_layout.insertWidget(self.message_layout.count() - 1, widget)
        self.scroll.verticalScrollBar().setValue(self.scroll.verticalScrollBar().maximum())

    def _add_system_message(self, message: str) -> None:
        label = QLabel(message, self.message_host)
        label.setWordWrap(True)
        label.setObjectName("systemMessage")
        self._add_widget(label)

    def _submit(self) -> None:
        question = self.question_input.text().strip()
        if not question or not self.send_button.isEnabled():
            return
        self._add_user_message(question)
        self._add_system_message("正在识别问题 → 查询当前用户订单 → 检索客服规则 → 校验证据……")
        self.question_input.clear()
        self._set_busy(True)
        self.controller.submit(question)

    def _submit_choice(self, original_question: str, order_code: str, label: str) -> None:
        self._add_user_message(f"选择订单：{label}")
        self._add_system_message("正在核验所选订单并继续处理……")
        self._set_busy(True)
        self.controller.submit(f"{original_question}，订单号 {order_code}")

    def _show_response(self, result: dict) -> None:
        source_links = " ".join(f"<a href='{escape(str(item.get('url', '')))}'>{escape(str(item.get('title', '规则文档')))}</a>" for item in result.get("sources", []))
        self.messages.setHtml(f"<p>{escape(str(result.get('answer', '')))}</p><p>{escape(str(result.get('provider', '')))} DeepSeek API {source_links}</p>")
        card = ResponseCard(result, self.message_host)
        card.choice_selected.connect(self._submit_choice)
        self._add_widget(card)
        self._set_busy(False)
        self.response_displayed.emit(str(result.get("decision", "unknown")))

    def _show_error(self, message: str) -> None:
        self._add_system_message(f"运行错误：{message}")
        self._set_busy(False)
        self.response_displayed.emit("error")

    def _add_user_message(self, message: str) -> None:
        label = QLabel(f"你：{message}", self.message_host)
        label.setWordWrap(True)
        label.setObjectName("userMessage")
        self._add_widget(label)

    def _set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.question_input.setEnabled(not busy)
        if not busy:
            self.question_input.setFocus()
