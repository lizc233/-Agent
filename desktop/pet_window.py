from __future__ import annotations

from pathlib import Path
import random

from PySide6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QSize, Qt, QTimer
from PySide6.QtGui import QAction, QCursor, QIcon, QMovie
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QSystemTrayIcon, QWidget

from .chat_window import ChatWindow


PET_SIZE = QSize(220, 220)


def choose_idle_behavior(random_value: float) -> str:
    return "idle" if random_value < 0.60 else "move"


def clamp_target(target: QPoint, left: int, top: int, right: int, bottom: int, width: int, height: int) -> QPoint:
    return QPoint(max(left, min(target.x(), right - width)), max(top, min(target.y(), bottom - height)))


class PetWindow(QWidget):
    def __init__(self, assets_dir: Path, chat_window: ChatWindow) -> None:
        super().__init__()
        self.assets_dir = assets_dir
        self.chat_window = chat_window
        self.move_mode = False
        self.hovered = False
        self.dragging = False
        self.drag_offset = QPoint()
        self.animation = QPropertyAnimation(self, b"pos", self)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self.animation.finished.connect(self._movement_finished)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(PET_SIZE)
        self.pet_label = QLabel(self)
        self.pet_label.setFixedSize(PET_SIZE)
        self.pet_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pet_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.movies = {
            "idle": self._load_movie("静坐.gif"),
            "gesture": self._load_movie("手势.gif"),
            "move": self._load_movie("移动.gif"),
        }
        self.current_state = ""
        self._set_state("idle")
        self.idle_timer = QTimer(self)
        self.idle_timer.setInterval(6000)
        self.idle_timer.timeout.connect(self._idle_tick)
        self.idle_timer.start()
        self.tray = self._create_tray()
        self.chat_window.response_displayed.connect(self._notify_response)
        self._place_near_bottom_right()

    def _load_movie(self, filename: str) -> QMovie:
        path = self.assets_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Desktop pet asset not found: {path}")
        movie = QMovie(str(path))
        if not movie.isValid():
            raise ValueError(f"Invalid GIF asset: {path}")
        movie.setScaledSize(PET_SIZE)
        movie.setCacheMode(QMovie.CacheMode.CacheAll)
        return movie

    def _set_state(self, state: str) -> None:
        if state == self.current_state:
            return
        if self.current_state:
            self.movies[self.current_state].stop()
        self.current_state = state
        self.pet_label.setMovie(self.movies[state])
        self.movies[state].start()

    def _create_tray(self) -> QSystemTrayIcon:
        icon = QIcon(str(self.assets_dir / "静坐.gif"))
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("袋鼠可信客服")
        menu = QMenu()
        open_action = QAction("打开客服", menu)
        self.move_action = QAction("开启移动模式", menu)
        exit_action = QAction("退出", menu)
        open_action.triggered.connect(self.open_chat)
        self.move_action.triggered.connect(self.toggle_move_mode)
        exit_action.triggered.connect(QApplication.instance().quit)
        menu.addAction(open_action)
        menu.addAction(self.move_action)
        menu.addSeparator()
        menu.addAction(exit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        return tray

    def _place_near_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(area.right() - self.width() - 24, area.bottom() - self.height() - 24)

    def enterEvent(self, event) -> None:
        self.hovered = True
        self.animation.stop()
        self._set_state("gesture")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered = False
        self._set_state("idle")
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = False
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton and self.tray.contextMenu():
            self.tray.contextMenu().popup(QCursor.pos())

    def mouseMoveEvent(self, event) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.dragging = True
            self.animation.stop()
            self.move(event.globalPosition().toPoint() - self.drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.dragging:
            self.open_chat()
        self.dragging = False

    def open_chat(self) -> None:
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()

    def toggle_move_mode(self) -> None:
        self.move_mode = not self.move_mode
        self.move_action.setText("关闭移动模式" if self.move_mode else "开启移动模式")
        if not self.move_mode:
            self.animation.stop()
            if not self.hovered:
                self._set_state("idle")

    def _idle_tick(self) -> None:
        if not self.move_mode or self.hovered or self.dragging or self.animation.state() == QPropertyAnimation.State.Running:
            return
        if choose_idle_behavior(random.random()) == "idle":
            self._set_state("idle")
            return
        self._start_random_movement()

    def _start_random_movement(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        direction_x, direction_y = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)])
        distance = random.randint(80, 180)
        target = self.pos() + QPoint(direction_x * distance, direction_y * distance)
        target = clamp_target(target, area.left(), area.top(), area.right() + 1, area.bottom() + 1, self.width(), self.height())
        self._set_state("move")
        self.animation.setDuration(4500)
        self.animation.setStartValue(self.pos())
        self.animation.setEndValue(target)
        self.animation.start()

    def _movement_finished(self) -> None:
        if not self.hovered:
            self._set_state("idle")

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.open_chat()

    def _notify_response(self, decision: str) -> None:
        title = "袋鼠客服已回复" if decision != "error" else "袋鼠客服运行错误"
        self.tray.showMessage(title, "点击袋鼠查看最新结果。", QSystemTrayIcon.MessageIcon.Information, 3500)
