from __future__ import annotations

import base64
import ctypes
import json
import logging
import os
import multiprocessing as mp
import subprocess
import sys
import tempfile
import threading
import zipfile
from datetime import datetime
from dataclasses import asdict
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
    from .i18n import dialog_labels, normalize_locale, preview_labels, text
    from .pipeline import generate_stencil
    from .title_bar import TitleBar
except ImportError:
    # Allow running as a script when package context is missing.
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from stencilforge.config import StencilConfig
    from stencilforge.i18n import dialog_labels, normalize_locale, preview_labels, text
    from stencilforge.pipeline import generate_stencil
    from stencilforge.title_bar import TitleBar


def _run_generate_stencil_subprocess(
    input_dir: str,
    output_stl: str,
    config_data: dict,
    result_queue: "mp.Queue[dict]",
) -> None:
    try:
        config = StencilConfig.from_dict(config_data)
        outline_debug = generate_stencil(Path(input_dir), Path(output_stl), config)
        result_queue.put({"ok": True, "outline_debug": outline_debug})
    except Exception as exc:
        import traceback

        result_queue.put(
            {
                "ok": False,
                "error": str(exc),
                "trace": traceback.format_exc().strip(),
            }
        )
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


class _JobCanceledError(RuntimeError):
    pass


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
        "outline_fill_rule": config.outline_fill_rule,
        "outline_close_strategy": config.outline_close_strategy,
        "outline_merge_tol_mm": config.outline_merge_tol_mm,
        "outline_snap_eps_mm": config.outline_snap_eps_mm,
        "outline_arc_max_chord_error_mm": config.outline_arc_max_chord_error_mm,
        "ui_debug_plot_outline": config.ui_debug_plot_outline,
        "ui_debug_plot_max_segments": config.ui_debug_plot_max_segments,
        "ui_debug_plot_max_offset_vectors": config.ui_debug_plot_max_offset_vectors,
        "ui_debug_plot_offset_min_mm": config.ui_debug_plot_offset_min_mm,
    }


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
    showOutlineDebug = Signal(dict)

    def __init__(self, project_root: Path):
        super().__init__()
        self._project_root = project_root
        self._config_path = StencilConfig.default_path(project_root)
        self._config = StencilConfig.load_default(project_root)
        self._ui_state_path = _resolve_ui_state_path(project_root)
        self._ui_state = _load_ui_state(self._ui_state_path)
        self._job_lock = threading.Lock()
        self._job_running = False
        self._temp_dirs: list[Path] = []
        self._preview_dialog: QDialog | None = None
        self._preview_viewer: "VtkStlViewer" | None = None
        self._preview_ui: dict | None = None
        self._window: QMainWindow | None = None
        self._last_preview_path: str | None = None
        self._job_cancel_requested = False
        self._job_process: mp.Process | None = None
        self._external_preview = sys.platform == "win32" and not getattr(sys, "frozen", False)
        self._locale = "zh-CN"
        self._log_path = _resolve_log_path(project_root)
        self._ensure_log_handler()
        self.jobError.connect(self._on_job_error)
        self.showOutlineDebug.connect(self._on_show_outline_debug)
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
        labels = preview_labels(self._locale)
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
        root_logger = logging.getLogger()
        formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        if self._log_path:
            has_file_handler = False
            for handler in root_logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    try:
                        if Path(handler.baseFilename) == self._log_path:
                            has_file_handler = True
                            break
                    except Exception:
                        continue
            if not has_file_handler:
                handler = logging.FileHandler(self._log_path, encoding="utf-8")
                handler.setFormatter(formatter)
                root_logger.addHandler(handler)

        has_stream_handler = any(
            isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler)
            for handler in root_logger.handlers
        )
        if not has_stream_handler:
            stream_handler = logging.StreamHandler(stream=sys.stdout)
            stream_handler.setFormatter(formatter)
            root_logger.addHandler(stream_handler)
        root_logger.setLevel(logging.INFO)

    def _emit_log(self, message: str) -> None:
        self.jobLog.emit(message)
        self._log_line(message)

    def _tr(self, key: str, **kwargs) -> str:
        return text(self._locale, key, **kwargs)

    def _on_job_error(self, message: str) -> None:
        labels = dialog_labels(self._locale)
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

    def _on_show_outline_debug(self, payload: dict) -> None:
        if not payload:
            return
        try:
            from .geometry.outline_plot import show_outline_debug_plot
        except Exception as exc:
            self._emit_log(self._tr("ui.debug_plot_load_failed", error=exc))
            return
        debug = payload.get("debug")
        plot_cfg = payload.get("plot_cfg")
        if not debug or not plot_cfg:
            return
        try:
            show_outline_debug_plot(debug, plot_cfg)
        except Exception as exc:
            self._emit_log(self._tr("ui.debug_plot_failed", error=exc))

    def _show_preview(self) -> None:
        if self._external_preview:
            if self._last_preview_path:
                self._launch_external_preview(self._last_preview_path)
            else:
                self._emit_log(preview_labels(self._locale)["no_preview_path"])
            return
        self._ensure_preview_ready()
        if self._preview_dialog is None:
            self._emit_log(preview_labels(self._locale)["preview_unavailable"])
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
            self._emit_log(self._tr("ui.config_not_found", path=path))
            self._log_line(f"Config not found: {path}")
            return
        self._config_path = path_obj
        self._remember_path("config_dir", path)
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
        self._locale = normalize_locale(locale)
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
        start_dir = self._remembered_dir("output_dir") or _default_export_dir()
        start_dir.mkdir(parents=True, exist_ok=True)
        initial = start_dir / default_name
        filename, _ = QFileDialog.getSaveFileName(
            None,
            self._tr("ui.pick_save_stl_title"),
            str(initial),
            "STL Files (*.stl)",
        )
        self._remember_path("output_dir", filename)
        return filename

    @Slot(str, result=str)
    def defaultOutputPath(self, default_name: str) -> str:
        start_dir = self._remembered_dir("output_dir") or _default_export_dir()
        start_dir.mkdir(parents=True, exist_ok=True)
        return str(start_dir / default_name)

    @Slot(result=str)
    def pickDirectory(self) -> str:
        start_dir = self._remembered_dir("input_dir") or self._project_root
        directory = QFileDialog.getExistingDirectory(
            None, self._tr("ui.pick_directory_title"), str(start_dir)
        )
        self._remember_path("input_dir", directory)
        return directory

    @Slot(result=str)
    def pickConfigFile(self) -> str:
        user_dir = StencilConfig.default_path(self._project_root).parent
        fallback_dir = self._project_root / "config"
        start_dir = self._remembered_dir("config_dir")
        if start_dir is None:
            start_dir = user_dir if user_dir.exists() else fallback_dir
        filename, _ = QFileDialog.getOpenFileName(
            None,
            self._tr("ui.pick_config_title"),
            str(start_dir),
            "Config (*.json)",
        )
        self._remember_path("config_dir", filename)
        return filename

    @Slot(result=str)
    def pickZipFile(self) -> str:
        start_dir = self._remembered_dir("zip_dir") or self._remembered_dir("input_dir") or self._project_root
        filename, _ = QFileDialog.getOpenFileName(
            None,
            self._tr("ui.pick_zip_title"),
            str(start_dir),
            "ZIP Files (*.zip)",
        )
        self._remember_path("zip_dir", filename)
        return filename

    @Slot(result=str)
    def pickStlFile(self) -> str:
        start_dir = self._remembered_dir("preview_dir") or self._remembered_dir("output_dir") or _default_export_dir()
        filename, _ = QFileDialog.getOpenFileName(
            None,
            self._tr("ui.pick_stl_title"),
            str(start_dir),
            "STL Files (*.stl)",
        )
        self._remember_path("preview_dir", filename)
        return filename

    @Slot(str, result=str)
    def fileUrl(self, path: str) -> str:
        return QUrl.fromLocalFile(path).toString()

    @Slot(str, result=str)
    def readFileBase64(self, path: str) -> str:
        try:
            data = Path(path).read_bytes()
        except FileNotFoundError:
            self._emit_log(self._tr("ui.file_not_found", path=path))
            return ""
        except OSError as exc:
            self._emit_log(self._tr("ui.read_file_failed", error=exc))
            return ""
        return base64.b64encode(data).decode("ascii")

    @Slot()
    def openPreview(self) -> None:
        self._show_preview()

    @Slot(str)
    def loadPreviewStl(self, path: str) -> None:
        if not path:
            self._emit_log(self._tr("ui.preview_path_empty"))
            return
        self._last_preview_path = path
        self._remember_path("preview_dir", path)
        if self._external_preview:
            self._launch_external_preview(path)
            return
        self._ensure_preview_ready()
        if self._preview_viewer is None:
            self._emit_log(self._tr("ui.preview_viewer_uninitialized"))
            return
        if not Path(path).exists():
            self._emit_log(self._tr("ui.stl_not_found", path=path))
            return
        self._preview_viewer.load_stl(path)
        self._show_preview()

    def _launch_external_preview(self, path: str) -> None:
        if not Path(path).exists():
            self._emit_log(self._tr("ui.stl_not_found", path=path))
            return
        try:
            env = os.environ.copy()
            env["STENCILFORGE_LOCALE"] = self._locale
            # Local dev run uses src-layout; ensure child process can import stencilforge.
            if not getattr(sys, "frozen", False):
                project_root = _resolve_project_root()
                src_root = project_root / "src"
                existing = env.get("PYTHONPATH", "")
                prefix = str(src_root)
                env["PYTHONPATH"] = f"{prefix}{os.pathsep}{existing}" if existing else prefix
            subprocess.Popen([sys.executable, "-m", "stencilforge.preview_app", path], env=env)
        except Exception as exc:
            self._emit_log(self._tr("ui.preview_launch_failed", error=exc))

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
            self._emit_log(self._tr("ui.zip_not_found", path=zip_path))
            return ""
        temp_dir = Path(tempfile.mkdtemp(prefix="stencilforge_"))
        try:
            with zipfile.ZipFile(path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            self._temp_dirs.append(temp_dir)
            return str(temp_dir)
        except zipfile.BadZipFile:
            self._emit_log(self._tr("ui.zip_invalid"))
            return ""

    @Slot(str, str, str)
    def runJob(self, input_dir: str, output_stl: str, config_path: str) -> None:
        with self._job_lock:
            if self._job_running:
                self._emit_log(self._tr("ui.job_already_running"))
                return
            self._job_running = True
            self._job_cancel_requested = False

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
                    raise ValueError(self._tr("ui.zip_extract_failed"))
                self._remember_path("input_dir", resolved_input)
                self._remember_path("output_dir", output_stl)
                if config_path:
                    self._remember_path("config_dir", config_path)
                config = self._config
                if config_path:
                    file_config = StencilConfig.from_json(Path(config_path))
                    merged = _config_to_dict(file_config)
                    merged.update(_config_to_dict(self._config))
                    config = StencilConfig.from_dict(merged)
                    if file_config.model_backend != self._config.model_backend:
                        self._log_line(
                            "UI backend takes precedence over config path backend: "
                            f"{file_config.model_backend} -> {self._config.model_backend}"
                        )
                    self._log_line("Runtime config merged: file + UI (UI precedence).")
                self._log_line(f"Effective backend: {config.model_backend}")
                self._log_line(f"Resolved input: {resolved_input}")
                if config.model_backend == "cadquery":
                    ctx = mp.get_context("spawn")
                    result_queue: mp.Queue[dict] = ctx.Queue()
                    process = ctx.Process(
                        target=_run_generate_stencil_subprocess,
                        args=(resolved_input, output_stl, asdict(config), result_queue),
                    )
                    self._job_process = process
                    process.start()
                    while process.is_alive():
                        if self._job_cancel_requested:
                            self._log_line("Job cancel requested: terminating worker process.")
                            pid = process.pid
                            if pid:
                                try:
                                    proc = subprocess.run(
                                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                                        check=False,
                                        capture_output=True,
                                        text=True,
                                    )
                                    if proc.returncode != 0:
                                        detail = (
                                            proc.stderr.strip()
                                            or proc.stdout.strip()
                                            or f"exit={proc.returncode}"
                                        )
                                        self._log_line(f"Job cancel: taskkill failed: {detail}")
                                except Exception as exc:
                                    self._log_line(f"Job cancel: taskkill failed: {exc}")
                            else:
                                self._log_line("Job cancel: missing worker PID.")
                            process.join(5)
                            if process.is_alive() and hasattr(process, "kill"):
                                process.kill()
                                process.join(5)
                            raise _JobCanceledError(self._tr("ui.job_canceled"))
                        process.join(0.1)
                    result = None
                    try:
                        result = result_queue.get_nowait()
                    except Exception:
                        result = None
                    if process.exitcode not in (0, None) and not result:
                        raise ValueError(f"CadQuery worker exited with code {process.exitcode}")
                    if result and not result.get("ok"):
                        detail = result.get("trace") or result.get("error")
                        raise ValueError(f"CadQuery worker failed: {detail}")
                    outline_debug = result.get("outline_debug") if result else None
                else:
                    outline_debug = generate_stencil(Path(resolved_input), Path(output_stl), config)
                if (
                    outline_debug
                    and config.ui_debug_plot_outline
                    and config.outline_close_strategy == "robust_polygonize"
                ):
                    plot_cfg = {
                        "max_segments": config.ui_debug_plot_max_segments,
                        "max_offset_vectors": config.ui_debug_plot_max_offset_vectors,
                        "offset_min_mm": config.ui_debug_plot_offset_min_mm,
                    }
                    self.showOutlineDebug.emit({"debug": outline_debug, "plot_cfg": plot_cfg})
                self.jobProgress.emit(100)
                self.jobStatus.emit("success")
                self._log_line("Job status: success")
                self.jobDone.emit({"output_stl": output_stl})
            except _JobCanceledError as exc:
                self._log_line(f"Job canceled: {exc}")
                self.jobStatus.emit("error")
                self._log_line("Job status: canceled")
                self.jobError.emit(str(exc))
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
                    self._job_process = None
                    self._job_cancel_requested = False

        threading.Thread(target=worker, daemon=True).start()

    def _remembered_dir(self, key: str) -> Path | None:
        raw = self._ui_state.get(key)
        if not raw:
            return None
        path = Path(str(raw)).expanduser()
        if path.exists():
            return path
        parent = path.parent
        return parent if parent.exists() else None

    def _remember_path(self, key: str, selected_path: str) -> None:
        if not selected_path:
            return
        path = Path(selected_path).expanduser()
        directory = path if path.is_dir() else path.parent
        if not directory:
            return
        self._ui_state[key] = str(directory)
        _save_ui_state(self._ui_state_path, self._ui_state)

    def _resolve_input_dir(self, input_dir: str) -> str:
        if not input_dir:
            return ""
        path = Path(input_dir)
        if path.is_file() and path.suffix.lower() == ".zip":
            extracted = self.importZip(str(path))
            if extracted:
                self._emit_log(self._tr("ui.zip_extracted", name=path.name))
            return extracted or ""
        return str(path)

    @Slot()
    def stopJob(self) -> None:
        if not self._job_running:
            self._emit_log(self._tr("ui.no_running_job"))
            return
        self._job_cancel_requested = True
        if self._job_process is not None and self._job_process.is_alive():
            self._emit_log(self._tr("ui.stop_requested_terminating"))
            pid = self._job_process.pid
            if pid:
                try:
                    proc = subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    if proc.returncode != 0:
                        detail = proc.stderr.strip() or proc.stdout.strip() or f"exit={proc.returncode}"
                        self._emit_log(self._tr("ui.terminate_failed", detail=detail))
                except Exception as exc:
                    self._emit_log(self._tr("ui.terminate_failed", detail=exc))
            else:
                self._emit_log(self._tr("ui.terminate_pid_missing"))
        else:
            self._emit_log(self._tr("ui.stop_requested_waiting"))

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
        startup_locale = normalize_locale(os.environ.get("STENCILFORGE_LOCALE"))
        raise FileNotFoundError(text(startup_locale, "ui.ui_dist_missing", paths=joined))

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
    labels = preview_labels("zh-CN")
    dialog = QDialog()
    dialog.setWindowTitle(labels["title"])
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
    title_bar = TitleBar(dialog, labels["title"])
    toolbar = QToolBar(dialog)
    toolbar.setMovable(False)
    fit_action = toolbar.addAction(labels["fit"])
    reset_action = toolbar.addAction(labels["reset"])
    wire_action = toolbar.addAction(labels["wireframe"])
    axes_action = toolbar.addAction(labels["axes"])
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
    avail_w = max(available.width(), 1)
    avail_h = max(available.height(), 1)

    # Keep requested minimums practical on small displays.
    min_w = max(1, min(min_size[0], avail_w))
    min_h = max(1, min(min_size[1], avail_h))

    width = min(int(avail_w * max_ratio[0]), max_size[0], avail_w)
    height = min(int(avail_h * max_ratio[1]), max_size[1], avail_h)
    width = min(max(width, min_w), avail_w)
    height = min(max(height, min_h), avail_h)
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


def _resolve_ui_state_path(project_root: Path) -> Path:
    return StencilConfig.default_path(project_root).parent / "ui_state.json"


def _load_ui_state(path: Path) -> dict[str, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_ui_state(path: Path, state: dict[str, str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def _default_export_dir() -> Path:
    home = Path.home()
    documents = home / "Documents"
    base = documents if documents.exists() else home
    return base / "StencilForge" / "Exports"


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
