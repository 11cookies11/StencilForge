from __future__ import annotations

import ctypes
import os
import sys
from ctypes import Structure
from ctypes import wintypes
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QIcon, QSurfaceFormat
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
)

try:
    from ..title_bar import TitleBar
    from .bridge import BackendBridge
    from .support import (
        center_window,
        fit_to_screen,
        init_qt_env,
        resolve_icon_path,
        resolve_project_root,
        resolve_ui_dist,
        ui_dist_candidates,
    )
except ImportError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from stencilforge.title_bar import TitleBar
    from stencilforge.ui.bridge import BackendBridge
    from stencilforge.ui.support import (
        center_window,
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

    class RECT(Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]

    class POINT(Structure):
        _fields_ = [
            ("x", ctypes.c_long),
            ("y", ctypes.c_long),
        ]

    class WINDOWPOS(Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("hwndInsertAfter", wintypes.HWND),
            ("x", ctypes.c_int),
            ("y", ctypes.c_int),
            ("cx", ctypes.c_int),
            ("cy", ctypes.c_int),
            ("flags", wintypes.UINT),
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

    def mousePressEvent(self, event) -> None:  # noqa: N802
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(event)

    def nativeEvent(self, eventType, message):  # noqa: N802
        if sys.platform == "win32" and eventType in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            msg = ctypes.cast(
                ctypes.c_void_p(int(message)),
                ctypes.POINTER(ctypes.c_ulong),
            )
            if msg[0] == WM_NCHITTEST:
                x = ctypes.c_short(msg[2] & 0xFFFF).value
                y = ctypes.c_short((msg[2] >> 16) & 0xFFFF).value
                pos = self.mapToGlobal(self.mapFrom(self._window, self._window.mapFromGlobal(self.mapTo(None, self.pos()))))
                x += pos.x()
                y += pos.y()
                width = self._window.width()
                height = self._window.height()
                margin = self._button_margin
                border = _resize_border()
                drag = self._drag_height
                left = x - self._window.x() <= border
                right = self._window.x() + width - x <= border
                top = y - self._window.y() <= drag
                bottom = self._window.y() + height - y <= border
                if top and left and not self._window.isMaximized():
                    msg[1] = HTTOPLEFT
                    return True
                if top and right and not self._window.isMaximized():
                    msg[1] = HTTOPRIGHT
                    return True
                if bottom and left and not self._window.isMaximized():
                    msg[1] = HTBOTTOMLEFT
                    return True
                if bottom and right and not self._window.isMaximized():
                    msg[1] = HTBOTTOMRIGHT
                    return True
                if left and not self._window.isMaximized():
                    msg[1] = HTLEFT
                    return True
                if right and not self._window.isMaximized():
                    msg[1] = HTRIGHT
                    return True
                if bottom and not self._window.isMaximized():
                    msg[1] = HTBOTTOM
                    return True
                if top:
                    msg[1] = HTCAPTION
                    return True
        return super().nativeEvent(eventType, message)


class MainWindow(QMainWindow):
    def __init__(self, bridge: BackendBridge, project_root: Path) -> None:
        super().__init__()
        self._bridge = bridge
        self.setWindowTitle("StencilForge")
        self.setWindowFlags(Qt.Window)
        if sys.platform == "win32" and dialog is None:
            _apply_snap_styles(int(self.winId()))
        drag_height = 64
        button_margin = 190
        web = WebView(self, drag_height, button_margin)
        channel = QWebChannel(self)
        channel.registerObject("backend", bridge)
        web.page().setWebChannel(channel)
        web_settings = web.page().settings()
        web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)
        web_settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        self.setCentralWidget(web)
        self._web = web


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
    window = MainWindow(bridge, project_root)
    bridge.attach_window(window)
    try:
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
        QSurfaceFormat.setDefaultFormat(QVTKRenderWindowInteractor.defaultFormat())
    except Exception:
        pass
    center_window(window, (760, 540))
    window.show()
    window._web.load(QUrl.fromLocalFile(str(html_path)))
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
