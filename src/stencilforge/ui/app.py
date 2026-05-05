from __future__ import annotations

import ctypes
import os
import sys
import warnings
from ctypes import Structure
from ctypes import wintypes
from pathlib import Path

warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"gerber(\.|$)")

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QCursor, QIcon
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)

try:
    from .bridge import BackendBridge
    from .support import (
        fit_to_screen,
        init_qt_env,
        resolve_icon_path,
        resolve_project_root,
        resolve_ui_dist,
        ui_dist_candidates,
    )
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from stencilforge.ui.bridge import BackendBridge
    from stencilforge.ui.support import (
        fit_to_screen,
        init_qt_env,
        resolve_icon_path,
        resolve_project_root,
        resolve_ui_dist,
        ui_dist_candidates,
    )

if sys.platform == "win32":
    WM_NCHITTEST = 0x0084
    WM_NCLBUTTONDBLCLK = 0x00A3
    HTCAPTION = 0x0002
    HTLEFT = 0x000A
    HTRIGHT = 0x000B
    HTTOP = 0x000C
    HTTOPLEFT = 0x000D
    HTTOPRIGHT = 0x000E
    HTBOTTOM = 0x000F
    HTBOTTOMLEFT = 0x0010
    HTBOTTOMRIGHT = 0x0011
    GWL_STYLE = -16
    WS_THICKFRAME = 0x00040000
    WS_MAXIMIZEBOX = 0x00010000
    WS_MINIMIZEBOX = 0x00020000
    WS_SYSMENU = 0x00080000
    SWP_NOMOVE = 0x0002
    SWP_NOSIZE = 0x0001
    SWP_NOZORDER = 0x0004
    SWP_FRAMECHANGED = 0x0020
    SM_CXSIZEFRAME = 32
    SM_CXPADDEDBORDER = 92

    class MSG(Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", wintypes.POINT),
        ]

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    def _resize_border() -> int:
        return (
            user32.GetSystemMetrics(SM_CXSIZEFRAME)
            + user32.GetSystemMetrics(SM_CXPADDEDBORDER)
        )


def _apply_snap_styles(hwnd: int) -> None:
    style = user32.GetWindowLongW(hwnd, GWL_STYLE)
    style |= WS_THICKFRAME | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_SYSMENU
    user32.SetWindowLongW(hwnd, GWL_STYLE, style)
    user32.SetWindowPos(
        hwnd,
        0,
        0,
        0,
        0,
        0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
    )


class WebView(QWebEngineView):
    def __init__(self, window: QMainWindow, drag_height: int, button_margin: int) -> None:
        super().__init__(window)
        self._window = window
        self._drag_height = drag_height
        self._button_margin = button_margin

    def nativeEvent(self, eventType, message):  # noqa: N802
        if sys.platform == "win32" and eventType in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            try:
                msg = MSG.from_address(int(message))
            except (ValueError, OSError):
                return super().nativeEvent(eventType, message)
            if msg.message == WM_NCHITTEST:
                pos = self.mapFromGlobal(QCursor.pos())
                if pos.y() <= self._drag_height:
                    if pos.x() < max(self.width() - self._button_margin, 0):
                        return True, HTCAPTION
            if msg.message == WM_NCLBUTTONDBLCLK:
                pos = self.mapFromGlobal(QCursor.pos())
                if pos.y() <= self._drag_height:
                    if pos.x() < max(self.width() - self._button_margin, 0):
                        if self._window.isMaximized():
                            self._window.showNormal()
                        else:
                            self._window.showMaximized()
                        return True, 0
        return super().nativeEvent(eventType, message)


class MainWindow(QMainWindow):
    def __init__(self, drag_height: int, button_margin: int) -> None:
        super().__init__()
        self._drag_height = drag_height
        self._button_margin = button_margin
        self._win_style_applied = False
        self._resize_border = _resize_border() if sys.platform == "win32" else 0
        self._top_resize_border = 1 if sys.platform == "win32" else 0

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        if sys.platform == "win32" and not self._win_style_applied:
            _apply_snap_styles(int(self.winId()))
            self._win_style_applied = True

    def nativeEvent(self, eventType, message):  # noqa: N802
        if sys.platform == "win32" and eventType in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            try:
                msg = MSG.from_address(int(message))
            except (ValueError, OSError):
                return super().nativeEvent(eventType, message)
            if msg.message == WM_NCHITTEST:
                pos = self.mapFromGlobal(QCursor.pos())
                if not self.isMaximized():
                    border = self._resize_border
                    top_border = self._top_resize_border
                    left = pos.x() <= border
                    right = pos.x() >= self.width() - border
                    top = pos.y() <= top_border
                    bottom = pos.y() >= self.height() - border
                    # Keep web content scrollbars interactive while preserving
                    # edge resize: reserve only the outermost 2px for right-edge resize.
                    if right and (self._drag_height < pos.y() < self.height() - border):
                        right_resize_strip = 2
                        if pos.x() < self.width() - right_resize_strip:
                            right = False
                    if top and left:
                        return True, HTTOPLEFT
                    if top and right:
                        return True, HTTOPRIGHT
                    if bottom and left:
                        return True, HTBOTTOMLEFT
                    if bottom and right:
                        return True, HTBOTTOMRIGHT
                    if left:
                        return True, HTLEFT
                    if right:
                        return True, HTRIGHT
                    if top:
                        return True, HTTOP
                    if bottom:
                        return True, HTBOTTOM
                if pos.y() <= self._drag_height:
                    if pos.x() < max(self.width() - self._button_margin, 0):
                        return True, HTCAPTION
        return super().nativeEvent(eventType, message)


def main() -> int:
    init_qt_env(webengine_flags="--ignore-gpu-blocklist --use-angle=d3d11")
    app = QApplication(sys.argv)
    project_root = resolve_project_root()
    icon_path = resolve_icon_path(project_root)
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)
    html_path = resolve_ui_dist(project_root)
    if html_path is None:
        candidates = ui_dist_candidates(project_root)
        joined = "\n".join(str(path) for path in candidates)
        raise FileNotFoundError(f"UI dist not found. Checked:\n{joined}")

    bridge = BackendBridge(project_root)
    window = MainWindow(drag_height=64, button_margin=190)
    if icon_path is not None:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.setWindowFlag(Qt.FramelessWindowHint, True)
    window.setWindowFlag(Qt.Window, True)
    window.setWindowFlag(Qt.WindowSystemMenuHint, True)
    window.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
    window.setMinimumSize(800, 400)
    view = WebView(window, drag_height=1, button_margin=190)
    view.setZoomFactor(0.8)
    settings = view.page().settings()
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)
    settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)

    channel = QWebChannel()
    channel.registerObject("backend", bridge)
    view.page().setWebChannel(channel)
    view.setUrl(QUrl.fromLocalFile(str(html_path)))
    window.setCentralWidget(view)
    bridge.attach_window(window)

    fit_to_screen(window, max_ratio=(0.80, 0.80), max_size=(1120, 760), min_size=(760, 540), edge_margin=20)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
