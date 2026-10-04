from __future__ import annotations

from html import escape

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPushButton, QTextBrowser, QVBoxLayout, QWidget

from .controller import AgentController


class ChatWindow(QMainWindow):
    response_displayed = Signal(str)

    def __init__(self, controller: AgentController, user_label: str, startup_message: str) -> None:
        super().__init__()
        self.controller = controller
        self.setWindowTitle("袋鼠可信客服")
        self.resize(620, 680)
        container = QWidget(self)
        layout = QVBoxLayout(container)
        self.identity_label = QLabel(f"当前账户：{user_label}", container)
        self.messages = QTextBrowser(container)
        self.choice_container = QWidget(container)
        self.choice_layout = QVBoxLayout(self.choice_container)
        self.choice_layout.setContentsMargins(0, 4, 0, 4)
        self.choice_container.hide()
        self.messages.setOpenExternalLinks(True)
        self.messages.setHtml(
            "<div style='padding:8px 4px'>"
            "<h2 style='color:#ef8b00;margin-bottom:4px'>袋鼠可信客服</h2>"
            "<p style='color:#77664c'>订单问题会先查询 MySQL，再根据客服规则回答。</p>"
            f"<p style='background:#edf8ef;padding:9px;border-radius:8px'>{escape(startup_message)}</p></div>"
        )
        input_layout = QHBoxLayout()
        self.question_input = QLineEdit(container)
        self.question_input.setPlaceholderText("例如：订单 OD202610010002 配送超时了怎么办？")
        self.send_button = QPushButton("发送", container)
        input_layout.addWidget(self.question_input)
        input_layout.addWidget(self.send_button)
        layout.addWidget(self.identity_label)
        layout.addWidget(self.messages)
        layout.addWidget(self.choice_container)
        layout.addLayout(input_layout)
        self.setCentralWidget(container)
        container.setStyleSheet("QLabel { color:#665335; } QLineEdit { min-height:24px; }")
        self.send_button.clicked.connect(self._submit)
        self.question_input.returnPressed.connect(self._submit)
        self.controller.response_ready.connect(self._show_response)
        self.controller.response_failed.connect(self._show_error)

    def _submit(self) -> None:
        question = self.question_input.text().strip()
        if not question or not self.send_button.isEnabled():
            return
        self.append_user_message(question)
        self.messages.append(
            "<div style='color:#7b6849;padding:8px 12px'>"
            "⏳ 正在识别问题 → 查询当前用户订单 → 检索客服规则 → 校验证据……</div>"
        )
        self.question_input.clear()
        self._set_busy(True)
        self.controller.submit(question)

    def _submit_choice(self, original_question: str, order_code: str, label: str) -> None:
        self._clear_choices()
        self.append_user_message(f"选择订单：{label}")
        self.messages.append("<div style='color:#7b6849;padding:8px 12px'>⏳ 正在核验所选订单并继续处理……</div>")
        self._set_busy(True)
        self.controller.submit(f"{original_question}，订单号 {order_code}")

    def _clear_choices(self) -> None:
        while self.choice_layout.count():
            item = self.choice_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.choice_container.hide()

    def _show_choices(self, choices: list[dict]) -> None:
        self._clear_choices()
        for choice in choices:
            label = str(choice.get("label", choice.get("value", "选择")))
            order_code = str(choice.get("value", ""))
            original_question = str(choice.get("question", ""))
            button = QPushButton(label, self.choice_container)
            button.setStyleSheet("text-align:left;padding:10px;border:1px solid #efb34d;border-radius:8px;background:#fff8e8;")
            button.clicked.connect(lambda checked=False, q=original_question, code=order_code, text=label: self._submit_choice(q, code, text))
            self.choice_layout.addWidget(button)
        self.choice_container.setVisible(bool(choices))

    def _show_response(self, result: dict) -> None:
        answer = escape(str(result.get("answer", "未生成回答。")))
        decision = escape(str(result.get("decision", "unknown")))
        provider = escape(str(result.get("provider", "unknown")))
        planner_provider = escape(str(result.get("planner_provider", "local-router")))
        planner_fallback = result.get("planner_fallback_reason")
        planner_status = "DeepSeek 已完成结构化任务规划" if planner_provider == "deepseek-planner" else "DeepSeek 规划不可用，已使用离线规划"
        if planner_fallback:
            planner_status += f"（{escape(str(planner_fallback))}）"
        sources = result.get("sources", [])
        source_html = ""
        if sources:
            links = [f'<a href="{escape(source["url"], quote=True)}">{escape(source["title"])}</a>（相似度 {float(source.get("score", 0)):.3f}）' for source in sources]
            source_html = "<p><strong>规则依据：</strong>" + "、".join(links) + "</p>"
        retrieval = result.get("retrieval", {})
        retrieval_html = ""
        if retrieval.get("method") == "embedding":
            retrieval_html = f"<p style='color:#665335'><strong>语义检索：</strong>{escape(str(retrieval.get('model', 'BAAI/bge-m3')))} · 余弦相似度 {float(retrieval.get('score', 0)):.3f}</p>"
        trace_names = {
            "classify": "识别问题意图",
            "query_order": "查询 MySQL 当前用户订单",
            "retrieve_rule": "检索客服规则文档",
            "validate_evidence": "校验回答依据",
            "answer": "生成可信回答",
            "clarify": "请求补充订单信息",
            "reject": "执行权限拒绝",
            "abstain": "执行知识不足拒答",
            "handoff": "建议转人工",
        }
        trace = " → ".join(trace_names.get(step, escape(step)) for step in result.get("trace", []))
        api_status = "DeepSeek API 调用成功" if provider == "deepseek" else "未调用 DeepSeek（本地策略）"
        if provider == "offline-rule-template":
            api_status = "DeepSeek 不可用，已离线降级"
        fallback_reason = result.get("fallback_reason")
        fallback_html = f"<p style='color:#8a5b00'>降级原因：{escape(str(fallback_reason))}</p>" if fallback_reason else ""
        self.messages.append(
            f"<div style='background:#fff3d6;padding:12px;margin:8px 0;border-left:4px solid #f4a51c;'>"
            f"<p><strong>袋鼠：</strong>{answer}</p>{source_html}{retrieval_html}"
            f"<p style='color:#665335'><strong>Agent 执行：</strong>{trace}</p>"
            f"<p style='color:#665335'><strong>任务规划：</strong>{planner_status}</p>"
            f"<p style='color:#666'>决策：{decision}｜回答方式：{provider}｜{api_status}</p>{fallback_html}</div>"
        )
        self._show_choices(result.get("choices", []))
        self._set_busy(False)
        self.response_displayed.emit(decision)

    def _show_error(self, message: str) -> None:
        self.messages.append(f"<p style='color:#b00020'><strong>运行错误：</strong>{escape(message)}</p>")
        self._set_busy(False)
        self.response_displayed.emit("error")

    def _set_busy(self, busy: bool) -> None:
        self.send_button.setEnabled(not busy)
        self.question_input.setEnabled(not busy)
        if not busy:
            self.question_input.setFocus()

    def append_user_message(self, message: str) -> None:
        self.messages.append(f"<p><strong>你：</strong>{escape(message)}</p>")
