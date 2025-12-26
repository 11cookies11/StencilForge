from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget


class TitleBar(QWidget):
    def __init__(self, parent: QWidget, title: str) -> None:
        super().__init__(parent)
        self._title = QLabel(title)
        self._title.setObjectName("TitleLabel")
        self._title.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)

        self._min_button = QToolButton(self)
        self._min_button.setText("-")
        self._min_button.clicked.connect(self._on_minimize)

        self._max_button = QToolButton(self)
        self._max_button.setText("[]")
        self._max_button.clicked.connect(self._on_max_restore)

        self._close_button = QToolButton(self)
        self._close_button.setText("X")
        self._close_button.clicked.connect(self._on_close)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(6)
        layout.addWidget(self._title)
        layout.addStretch(1)
        layout.addWidget(self._min_button)
        layout.addWidget(self._max_button)
        layout.addWidget(self._close_button)

        self.setFixedHeight(40)
        self.setObjectName("TitleBar")
        self.setStyleSheet(
            "QWidget#TitleBar { background: #ffffff; border-bottom: 1px solid #e5e7eb; }"
            "QLabel#TitleLabel { color: #0f172a; font-weight: 600; }"
            "QToolButton { width: 32px; height: 28px; border-radius: 6px; }"
            "QToolButton:hover { background: #f1f5f9; }"
            "QToolButton#CloseButton:hover { background: #fee2e2; color: #b91c1c; }"
        )
        self._close_button.setObjectName("CloseButton")

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._on_max_restore()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        if self._is_on_button(event.pos()):
            return
        window = self.window().windowHandle()
        if window is not None:
            window.startSystemMove()

    def _is_on_button(self, pos) -> bool:
        for button in (self._min_button, self._max_button, self._close_button):
            if button.geometry().contains(pos):
                return True
        return False

    def _on_minimize(self) -> None:
        self.window().showMinimized()

    def _on_max_restore(self) -> None:
        window = self.window()
        if window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()

    def _on_close(self) -> None:
        self.window().close()
