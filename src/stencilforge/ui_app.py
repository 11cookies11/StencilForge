from __future__ import annotations

import base64
import ctypes
import logging
import os
import subprocess
import sys
import tempfile
import threading
import zipfile
from datetime import datetime
from ctypes import Structure
from ctypes import wintypes
from fnmatch import fnmatch
from pathlib import Path

from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot, QCoreApplication
from PySide6.QtGui import QCursor, QGuiApplication, QSurfaceFormat, QIcon, QDesktopServices
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

try:
    from .config import StencilConfig
    from .pipeline import generate_stencil
    from .title_bar import TitleBar
except ImportError:
    # Allow running as a script when package context is missing.
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from stencilforge.config import StencilConfig
    from stencilforge.pipeline import generate_stencil
    from stencilforge.title_bar import TitleBar
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stencilforge.vtk_viewer import VtkStlViewer

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
    SM_CYSIZEFRAME = 33
    SM_CXPADDEDBORDER = 92

    user32 = ctypes.WinDLL("user32", use_last_error=True)


    class MSG(Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", wintypes.POINT),
        ]

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


def _config_to_dict(config: StencilConfig) -> dict:
    return {
        "paste_patterns": list(config.paste_patterns),
        "outline_patterns": list(config.outline_patterns),
        "thickness_mm": config.thickness_mm,
        "paste_offset_mm": config.paste_offset_mm,
        "outline_margin_mm": config.outline_margin_mm,
        "locator_enabled": config.locator_enabled,
        "locator_height_mm": config.locator_height_mm,
        "locator_width_mm": config.locator_width_mm,
        "locator_clearance_mm": config.locator_clearance_mm,
        "locator_step_height_mm": config.locator_step_height_mm,
        "locator_step_width_mm": config.locator_step_width_mm,
        "locator_mode": config.locator_mode,
        "locator_open_side": config.locator_open_side,
        "locator_open_width_mm": config.locator_open_width_mm,
        "output_mode": config.output_mode,
        "model_backend": config.model_backend,
        "stl_linear_deflection": config.stl_linear_deflection,
        "stl_angular_deflection": config.stl_angular_deflection,
        "arc_steps": config.arc_steps,
        "curve_resolution": config.curve_resolution,
        "qfn_regen_enabled": config.qfn_regen_enabled,
        "qfn_min_feature_mm": config.qfn_min_feature_mm,
        "qfn_confidence_threshold": config.qfn_confidence_threshold,
        "qfn_max_pad_width_mm": config.qfn_max_pad_width_mm,
        "debug_log_detail": config.debug_log_detail,
        "debug_dump_dir": config.debug_dump_dir,
    }


_PREVIEW_I18N = {
    "zh-CN": {
        "title": "钢网预览",
        "fit": "适配",
        "reset": "重置",
        "wireframe": "线框",
        "axes": "坐标轴",
        "no_preview_path": "预览 STL 路径为空。",
        "preview_unavailable": "预览窗口未初始化。",
    },
    "en": {
        "title": "Stencil preview",
        "fit": "Fit",
        "reset": "Reset",
        "wireframe": "Wireframe",
        "axes": "Axes",
        "no_preview_path": "Preview STL path is empty.",
        "preview_unavailable": "Preview window is not initialized.",
    },
}
_DIALOG_I18N = {
    "zh-CN": {
        "error_title": "运行失败",
        "error_body": "发生错误，任务已停止。",
        "error_detail": "错误原因: {message}",
        "error_log": "日志已保存到: {path}",
        "error_open_log": "查看日志",
    },
    "en": {
        "error_title": "Job Failed",
        "error_body": "An error occurred and the job was stopped.",
        "error_detail": "Error: {message}",
        "error_log": "Log saved to: {path}",
        "error_open_log": "Open Log",
    },
}


def _normalize_locale(locale: str | None) -> str:
    if not locale:
        return "zh-CN"
    lowered = locale.lower()
    if lowered.startswith("en"):
        return "en"
    return "zh-CN"


def _preview_labels(locale: str) -> dict:
    key = _normalize_locale(locale)
    return _PREVIEW_I18N.get(key, _PREVIEW_I18N["zh-CN"])


def _dialog_labels(locale: str) -> dict:
    key = _normalize_locale(locale)
    return _DIALOG_I18N.get(key, _DIALOG_I18N["zh-CN"])


def _find_files(input_dir: Path, patterns: list[str]) -> list[Path]:
    matches = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        if any(fnmatch(name, pattern.lower()) for pattern in patterns):
            matches.append(path)
    return sorted(matches)


class BackendBridge(QObject):
    configChanged = Signal(dict)
    filesScanned = Signal(dict)
    jobStatus = Signal(str)
    jobProgress = Signal(int)
    jobLog = Signal(str)
    jobDone = Signal(dict)
    jobError = Signal(str)

    def __init__(self, project_root: Path):
        super().__init__()
        self._project_root = project_root
        self._config_path = StencilConfig.default_path(project_root)
        self._config = StencilConfig.load_default(project_root)
        self._job_lock = threading.Lock()
        self._job_running = False
        self._temp_dirs: list[Path] = []
        self._preview_dialog: QDialog | None = None
        self._preview_viewer: "VtkStlViewer" | None = None
        self._preview_ui: dict | None = None
        self._window: QMainWindow | None = None
        self._last_preview_path: str | None = None
        self._external_preview = sys.platform == "win32" and not getattr(sys, "frozen", False)
        self._locale = "zh-CN"
        self._log_path = _resolve_log_path(project_root)
        self._ensure_log_handler()
        self.jobError.connect(self._on_job_error)
        self._log_line("Backend initialized.")

    def attach_preview(self, dialog: QDialog, viewer: "VtkStlViewer", ui: dict | None = None) -> None:
        if self._external_preview:
            return
        self._preview_dialog = dialog
        self._preview_viewer = viewer
        self._preview_ui = ui
        self._apply_preview_locale()

    def attach_window(self, window: QMainWindow) -> None:
        self._window = window

    def _apply_preview_locale(self) -> None:
        if self._external_preview:
            return
        if self._preview_dialog is None or self._preview_ui is None:
            return
        labels = _preview_labels(self._locale)
        self._preview_dialog.setWindowTitle(labels["title"])
        title_bar = self._preview_ui.get("title_bar")
        if title_bar is not None and hasattr(title_bar, "_title"):
            title_bar._title.setText(labels["title"])
        for key, action_name in (
            ("fit_action", "fit"),
            ("reset_action", "reset"),
            ("wire_action", "wireframe"),
            ("axes_action", "axes"),
        ):
            action = self._preview_ui.get(key)
            if action is not None:
                action.setText(labels[action_name])

    def _log_line(self, message: str) -> None:
        if not self._log_path:
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_path.open("a", encoding="utf-8").write(f"[{timestamp}] {message}\n")
        except OSError:
            pass

    def _ensure_log_handler(self) -> None:
        if not self._log_path:
            return
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, logging.FileHandler):
                try:
                    if Path(handler.baseFilename) == self._log_path:
                        return
                except Exception:
                    continue
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        handler = logging.FileHandler(self._log_path, encoding="utf-8")
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)

    def _emit_log(self, message: str) -> None:
        self._log_line(message)

    def _on_job_error(self, message: str) -> None:
        labels = _dialog_labels(self._locale)
        details = [labels["error_detail"].format(message=message)]
        open_button = None
        if self._log_path:
            details.append(labels["error_log"].format(path=self._log_path))
        dialog = QMessageBox(self._window)
        dialog.setIcon(QMessageBox.Critical)
        dialog.setWindowTitle(labels["error_title"])
        dialog.setText(labels["error_body"])
        dialog.setInformativeText("\n".join(details))
        dialog.setStandardButtons(QMessageBox.Ok)
        if self._log_path:
            open_button = dialog.addButton(labels["error_open_log"], QMessageBox.ActionRole)
        dialog.exec()
        if open_button is not None and dialog.clickedButton() == open_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_path)))

    def _show_preview(self) -> None:
        if self._external_preview:
            if self._last_preview_path:
                self._launch_external_preview(self._last_preview_path)
            else:
                self._emit_log(_preview_labels(self._locale)["no_preview_path"])
            return
        self._ensure_preview_ready()
        if self._preview_dialog is None:
            self._emit_log(_preview_labels(self._locale)["preview_unavailable"])
            return
        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()
        if self._preview_viewer is not None:
            self._preview_viewer.show()
            self._preview_viewer.fit_view()
            self._preview_viewer.refresh_view()

    @Slot(result=dict)
    def getConfig(self) -> dict:
        return _config_to_dict(self._config)

    @Slot(str)
    def loadConfig(self, path: str) -> None:
        path_obj = Path(path)
        if not path_obj.exists():
            self._emit_log(f"未找到配置文件: {path}")
            self._log_line(f"Config not found: {path}")
            return
        self._config_path = path_obj
        self._config = StencilConfig.from_json(path_obj)
        self._log_line(f"Config loaded: {path_obj}")
        self.configChanged.emit(_config_to_dict(self._config))

    @Slot(dict)
    def setConfig(self, partial: dict) -> None:
        data = _config_to_dict(self._config)
        data.update(partial or {})
        self._config = StencilConfig.from_dict(data)
        self.configChanged.emit(_config_to_dict(self._config))

    @Slot(str)
    def setLocale(self, locale: str) -> None:
        self._locale = _normalize_locale(locale)
        self._apply_preview_locale()

    @Slot(str)
    def scanFiles(self, input_dir: str) -> None:
        resolved = self._resolve_input_dir(input_dir)
        if not resolved:
            self._log_line("Scan files: input empty or invalid.")
            self.filesScanned.emit({"files": []})
            return
        path = Path(resolved)
        if not path.exists():
            self._log_line(f"Scan files: input path not found: {resolved}")
            self.filesScanned.emit({"files": []})
            return
        files = _find_files(path, self._config.paste_patterns + self._config.outline_patterns)
        self._log_line(f"Scan files: {len(files)} matched in {resolved}")
        for file_path in files:
            self._log_line(f"  - {file_path.name}")
        self.filesScanned.emit({"files": [p.name for p in files]})

    @Slot(str, result=str)
    def pickSaveFile(self, default_name: str) -> str:
        filename, _ = QFileDialog.getSaveFileName(
            None,
            "保存 STL",
            str(self._project_root / default_name),
            "STL Files (*.stl)",
        )
        return filename

    @Slot(result=str)
    def pickDirectory(self) -> str:
        directory = QFileDialog.getExistingDirectory(
            None, "选择 Gerber 文件夹", str(self._project_root)
        )
        return directory

    @Slot(result=str)
    def pickConfigFile(self) -> str:
        user_dir = StencilConfig.default_path(self._project_root).parent
        fallback_dir = self._project_root / "config"
        start_dir = user_dir if user_dir.exists() else fallback_dir
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "选择配置文件",
            str(start_dir),
            "Config (*.json)",
        )
        return filename

    @Slot(result=str)
    def pickZipFile(self) -> str:
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "选择 Gerber ZIP",
            str(self._project_root),
            "ZIP Files (*.zip)",
        )
        return filename

    @Slot(result=str)
    def pickStlFile(self) -> str:
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "选择 STL",
            str(self._project_root),
            "STL Files (*.stl)",
        )
        return filename

    @Slot(str, result=str)
    def fileUrl(self, path: str) -> str:
        return QUrl.fromLocalFile(path).toString()

    @Slot(str, result=str)
    def readFileBase64(self, path: str) -> str:
        try:
            data = Path(path).read_bytes()
        except FileNotFoundError:
            self._emit_log(f"文件不存在: {path}")
            return ""
        except OSError as exc:
            self._emit_log(f"读取文件失败: {exc}")
            return ""
        return base64.b64encode(data).decode("ascii")

    @Slot()
    def openPreview(self) -> None:
        self._show_preview()

    @Slot(str)
    def loadPreviewStl(self, path: str) -> None:
        if not path:
            self._emit_log("预览 STL 路径为空。")
            return
        self._last_preview_path = path
        if self._external_preview:
            self._launch_external_preview(path)
            return
        self._ensure_preview_ready()
        if self._preview_viewer is None:
            self._emit_log("预览视图未初始化。")
            return
        if not Path(path).exists():
            self._emit_log(f"未找到 STL: {path}")
            return
        self._preview_viewer.load_stl(path)
        self._show_preview()

    def _launch_external_preview(self, path: str) -> None:
        if not Path(path).exists():
            self._emit_log(f"未找到 STL: {path}")
            return
        try:
            env = os.environ.copy()
            env["STENCILFORGE_LOCALE"] = self._locale
            subprocess.Popen([sys.executable, "-m", "stencilforge.preview_app", path], env=env)
        except Exception as exc:
            self._emit_log(f"启动预览失败: {exc}")

    def _ensure_preview_ready(self) -> None:
        if self._external_preview or self._preview_dialog is not None:
            return
        try:
            preview_dialog, preview_viewer, preview_ui = _build_preview_dialog()
        except Exception as exc:
            self._log_line(f"Preview init failed: {exc}")
            return
        self.attach_preview(preview_dialog, preview_viewer, preview_ui)

    @Slot(str, result=str)
    def importZip(self, zip_path: str) -> str:
        path = Path(zip_path)
        if not path.exists():
            self._emit_log(f"未找到 ZIP: {zip_path}")
            return ""
        temp_dir = Path(tempfile.mkdtemp(prefix="stencilforge_"))
        try:
            with zipfile.ZipFile(path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            self._temp_dirs.append(temp_dir)
            return str(temp_dir)
        except zipfile.BadZipFile:
            self._emit_log("无效的 ZIP 文件。")
            return ""

    @Slot(str, str, str)
    def runJob(self, input_dir: str, output_stl: str, config_path: str) -> None:
        with self._job_lock:
            if self._job_running:
                self._emit_log("任务已在运行。")
                return
            self._job_running = True

        def worker():
            try:
                self._log_line(
                    f"Run job: input={input_dir} output={output_stl} config={config_path or '(default)'}"
                )
                self.jobStatus.emit("running")
                self._log_line("Job status: running")
                self.jobProgress.emit(0)
                resolved_input = self._resolve_input_dir(input_dir)
                if not resolved_input:
                    raise ValueError("无法解压 ZIP 输入。")
                config = self._config
                if config_path:
                    config = StencilConfig.from_json(Path(config_path))
                self._log_line(f"Resolved input: {resolved_input}")
                generate_stencil(Path(resolved_input), Path(output_stl), config)
                self.jobProgress.emit(100)
                self.jobStatus.emit("success")
                self._log_line("Job status: success")
                self.jobDone.emit({"output_stl": output_stl})
            except Exception as exc:
                import traceback

                traceback.print_exc()
                self._log_line(f"Job error: {exc}")
                self._log_line(traceback.format_exc().strip())
                self.jobStatus.emit("error")
                self._log_line("Job status: error")
                self.jobError.emit(str(exc))
            finally:
                with self._job_lock:
                    self._job_running = False

        threading.Thread(target=worker, daemon=True).start()

    def _resolve_input_dir(self, input_dir: str) -> str:
        if not input_dir:
            return ""
        path = Path(input_dir)
        if path.is_file() and path.suffix.lower() == ".zip":
            extracted = self.importZip(str(path))
            if extracted:
                self._emit_log(f"已解压 ZIP: {path.name}")
            return extracted or ""
        return str(path)

    @Slot()
    def stopJob(self) -> None:
        self._emit_log("已请求停止，当前任务暂不支持取消。")

    @Slot()
    def windowMinimize(self) -> None:
        if self._window is not None:
            self._window.showMinimized()

    @Slot()
    def windowMaximizeRestore(self) -> None:
        if self._window is None:
            return
        if self._window.isMaximized():
            self._window.showNormal()
        else:
            self._window.showMaximized()

    @Slot()
    def windowClose(self) -> None:
        if self._window is not None:
            self._window.close()

    @Slot()
    def windowStartDrag(self) -> None:
        if self._window is None:
            return
        handle = self._window.windowHandle()
        if handle is not None:
            handle.startSystemMove()

    @Slot(result=bool)
    def windowUsesNativeHitTest(self) -> bool:
        return sys.platform == "win32"


class WebView(QWebEngineView):
    def __init__(self, window: QMainWindow, drag_height: int, button_margin: int) -> None:
        super().__init__(window)
        self._window = window
        self._drag_height = drag_height
        self._button_margin = button_margin

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if pos.y() <= self._drag_height:
                if pos.x() < max(self.width() - self._button_margin, 0):
                    handle = self._window.windowHandle()
                    if handle is not None:
                        handle.startSystemMove()
                        event.accept()
                        return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            pos = event.position().toPoint()
            if pos.y() <= self._drag_height:
                if pos.x() < max(self.width() - self._button_margin, 0):
                    if self._window.isMaximized():
                        self._window.showNormal()
                    else:
                        self._window.showMaximized()
                    event.accept()
                    return
        super().mouseDoubleClickEvent(event)

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
    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StencilForge")
        except Exception:
            pass
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    try:
        QCoreApplication.setAttribute(Qt.AA_UseDesktopOpenGL)
    except Exception:
        pass
    flags = "--ignore-gpu-blocklist --use-angle=d3d11"
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if flags not in existing:
        combined = f"{existing} {flags}".strip()
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = combined

    app = QApplication(sys.argv)
    project_root = _resolve_project_root()
    icon_path = _resolve_icon_path(project_root)
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)
    html_path = _resolve_ui_dist(project_root)
    if html_path is None:
        candidates = _ui_dist_candidates(project_root)
        joined = "\n".join(str(path) for path in candidates)
        raise FileNotFoundError(
            "未找到 UI 构建产物，请确认安装包包含前端资源。\n"
            f"已尝试路径:\n{joined}"
        )

    window = MainWindow(drag_height=64, button_margin=190)
    window.setWindowTitle("StencilForge")
    if icon_path is not None:
        window.setWindowIcon(QIcon(str(icon_path)))
    window.setWindowFlag(Qt.FramelessWindowHint, True)
    window.setWindowFlag(Qt.Window, True)
    window.setWindowFlag(Qt.WindowSystemMenuHint, True)
    window.setWindowFlag(Qt.WindowMinMaxButtonsHint, True)
    view = WebView(window, drag_height=1, button_margin=190)
    settings = view.settings()
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)
    settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, True)

    channel = QWebChannel()
    backend = BackendBridge(project_root)
    channel.registerObject("backend", backend)
    view.page().setWebChannel(channel)
    view.setUrl(QUrl.fromLocalFile(str(html_path)))
    window.setCentralWidget(view)
    backend.attach_window(window)

    _fit_to_screen(window, max_ratio=(0.9, 0.85), max_size=(1280, 820), min_size=(980, 680))
    window.show()
    return app.exec()


def _build_preview_dialog() -> tuple[QDialog, "VtkStlViewer", dict]:
    from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
    try:
        from .vtk_viewer import VtkStlViewer
    except ImportError:
        from stencilforge.vtk_viewer import VtkStlViewer

    try:
        QSurfaceFormat.setDefaultFormat(QVTKRenderWindowInteractor.defaultFormat())
    except Exception:
        pass
    dialog = QDialog()
    dialog.setWindowTitle(_PREVIEW_I18N["zh-CN"]["title"])
    dialog.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
    _fit_to_screen(dialog, max_ratio=(0.8, 0.8), max_size=(980, 760), min_size=(720, 540))
    dialog.setStyleSheet(
        "QDialog { background-color: #f8fafc; }"
        "QToolBar { background-color: #ffffff; border-bottom: 1px solid #e5e7eb; }"
        "QToolButton { color: #0f172a; padding: 6px 12px; border-radius: 6px; }"
        "QToolButton:hover { background-color: #f1f5f9; }"
        "QToolButton:checked { background-color: #e2e8f0; }"
    )
    viewer = VtkStlViewer(dialog)
    title_bar = TitleBar(dialog, _PREVIEW_I18N["zh-CN"]["title"])
    toolbar = QToolBar(dialog)
    toolbar.setMovable(False)
    fit_action = toolbar.addAction(_PREVIEW_I18N["zh-CN"]["fit"])
    reset_action = toolbar.addAction(_PREVIEW_I18N["zh-CN"]["reset"])
    wire_action = toolbar.addAction(_PREVIEW_I18N["zh-CN"]["wireframe"])
    axes_action = toolbar.addAction(_PREVIEW_I18N["zh-CN"]["axes"])
    wire_action.setCheckable(True)
    axes_action.setCheckable(True)
    axes_action.setChecked(True)

    fit_action.triggered.connect(viewer.fit_view)
    reset_action.triggered.connect(viewer.reset_view)
    wire_action.toggled.connect(viewer.set_wireframe)
    axes_action.toggled.connect(viewer.toggle_axes)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(title_bar)
    layout.addWidget(toolbar)
    layout.addWidget(viewer)
    return dialog, viewer, {
        "title_bar": title_bar,
        "fit_action": fit_action,
        "reset_action": reset_action,
        "wire_action": wire_action,
        "axes_action": axes_action,
    }


def _fit_to_screen(
    widget: QDialog | QMainWindow,
    max_ratio: tuple[float, float],
    max_size: tuple[int, int],
    min_size: tuple[int, int],
) -> None:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        widget.resize(*max_size)
        return
    available = screen.availableGeometry()
    width = min(int(available.width() * max_ratio[0]), max_size[0])
    height = min(int(available.height() * max_ratio[1]), max_size[1])
    width = max(width, min_size[0])
    height = max(height, min_size[1])
    widget.resize(width, height)
    x = available.x() + max((available.width() - width) // 2, 0)
    y = available.y() + max((available.height() - height) // 2, 0)
    widget.move(x, y)


def _resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        return exe_dir
    return Path(__file__).resolve().parents[2]


def _ui_dist_candidates(project_root: Path) -> list[Path]:
    base = Path(getattr(sys, "_MEIPASS", project_root))
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else project_root
    return [
        base / "ui-vue" / "dist" / "index.html",
        exe_dir / "ui-vue" / "dist" / "index.html",
        project_root / "ui-vue" / "dist" / "index.html",
        project_root / "dist" / "index.html",
    ]


def _resolve_ui_dist(project_root: Path) -> Path | None:
    for candidate in _ui_dist_candidates(project_root):
        if candidate.exists():
            return candidate
    return None


def _resolve_log_path(project_root: Path) -> Path | None:
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidate = exe_dir / "stencilforge.log"
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            candidate.touch(exist_ok=True)
            return candidate
        except OSError:
            pass
    user_dir = StencilConfig.default_path(project_root).parent
    if user_dir:
        return user_dir / "stencilforge.log"
    return None


def _resolve_icon_path(project_root: Path) -> Path | None:
    icon_name = "icon.ico" if sys.platform == "win32" else "icon.svg"
    candidates = [
        project_root / "assets" / icon_name,
        project_root / "assets" / "icon.svg",
    ]
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", project_root))
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                base / "assets" / icon_name,
                base / "assets" / "icon.svg",
                exe_dir / "assets" / icon_name,
                exe_dir / "assets" / "icon.svg",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


if __name__ == "__main__":
    raise SystemExit(main())
