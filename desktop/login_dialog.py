from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from backend.auth import AuthenticatedUser, authenticate, register
from backend.config import Settings


class LoginDialog(QDialog):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings
        self.authenticated_user: AuthenticatedUser | None = None
        self.registration_mode = False
        self.setWindowTitle("登录袋鼠客服")
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
        self.setFixedSize(430, 480)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(34, 28, 34, 28)
        title = QLabel("袋鼠可信客服", self)
        title.setObjectName("brandTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("登录后，Agent 只查询当前账户名下的订单", self)
        subtitle.setObjectName("subTitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame(self)
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        form = QFormLayout()
        form.setSpacing(14)
        self.user_code_input = QLineEdit(card)
        self.user_code_input.setPlaceholderText("例如 U10001")
        self.display_name_input = QLineEdit(card)
        self.display_name_input.setPlaceholderText("首次注册时填写")
        self.password_input = QLineEdit(card)
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("至少 6 位")
        form.addRow("用户编号", self.user_code_input)
        form.addRow("昵称", self.display_name_input)
        self.display_name_label = form.labelForField(self.display_name_input)
        form.addRow("密码", self.password_input)
        card_layout.addLayout(form)
        button_layout = QHBoxLayout()
        self.submit_button = QPushButton("登录", card)
        self.switch_button = QPushButton("切换到注册", card)
        self.switch_button.setObjectName("secondaryButton")
        button_layout.addWidget(self.submit_button)
        button_layout.addWidget(self.switch_button)
        card_layout.addLayout(button_layout)
        hint = QLabel("已有测试订单的用户可使用原用户编号完成首次注册。", card)
        hint.setWordWrap(True)
        hint.setObjectName("subTitle")
        card_layout.addWidget(hint)
        outer.addWidget(title)
        outer.addWidget(subtitle)
        outer.addSpacing(12)
        outer.addWidget(card)
        self.submit_button.clicked.connect(self._submit)
        self.switch_button.clicked.connect(self._toggle_mode)
        self.password_input.returnPressed.connect(self._submit)
        self._refresh_mode()

    def _toggle_mode(self) -> None:
        self.registration_mode = not self.registration_mode
        self._refresh_mode()

    def _refresh_mode(self) -> None:
        self.display_name_input.setVisible(self.registration_mode)
        self.display_name_label.setVisible(self.registration_mode)
        self.submit_button.setText("注册并登录" if self.registration_mode else "登录")
        self.switch_button.setText("返回登录" if self.registration_mode else "切换到注册")

    def _submit(self) -> None:
        try:
            if self.registration_mode:
                user = register(self.settings, self.user_code_input.text(), self.display_name_input.text(), self.password_input.text())
            else:
                user = authenticate(self.settings, self.user_code_input.text(), self.password_input.text())
                if user is None:
                    raise ValueError("用户编号或密码错误；首次使用测试用户请先注册。")
        except Exception as error:
            QMessageBox.warning(self, "无法登录", str(error))
            return
        self.authenticated_user = user
        self.accept()
