from __future__ import annotations

import base64
import os
import sys
import tempfile
import threading
import zipfile
from fnmatch import fnmatch
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtGui import QGuiApplication
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QToolBar, QVBoxLayout

from .config import StencilConfig
from .pipeline import generate_stencil
from .vtk_viewer import VtkStlViewer


def _config_to_dict(config: StencilConfig) -> dict:
    return {
        "paste_patterns": list(config.paste_patterns),
        "outline_patterns": list(config.outline_patterns),
        "thickness_mm": config.thickness_mm,
        "paste_offset_mm": config.paste_offset_mm,
        "outline_margin_mm": config.outline_margin_mm,
        "output_mode": config.output_mode,
        "arc_steps": config.arc_steps,
        "curve_resolution": config.curve_resolution,
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

    def __init__(self, project_root: Path):
        super().__init__()
        self._project_root = project_root
        self._config_path = StencilConfig.default_path(project_root)
        self._config = StencilConfig.from_json(self._config_path)
        self._job_lock = threading.Lock()
        self._job_running = False
        self._temp_dirs: list[Path] = []
        self._preview_dialog: QDialog | None = None
        self._preview_viewer: VtkStlViewer | None = None

    def attach_preview(self, dialog: QDialog, viewer: VtkStlViewer) -> None:
        self._preview_dialog = dialog
        self._preview_viewer = viewer

    def _show_preview(self) -> None:
        if self._preview_dialog is None:
            self.jobLog.emit("预览窗口未初始化。")
            return
        self._preview_dialog.show()
        self._preview_dialog.raise_()
        self._preview_dialog.activateWindow()

    @Slot(result=dict)
    def getConfig(self) -> dict:
        return _config_to_dict(self._config)

    @Slot(str)
    def loadConfig(self, path: str) -> None:
        path_obj = Path(path)
        if not path_obj.exists():
            self.jobLog.emit(f"未找到配置文件: {path}")
            return
        self._config_path = path_obj
        self._config = StencilConfig.from_json(path_obj)
        self.configChanged.emit(_config_to_dict(self._config))

    @Slot(dict)
    def setConfig(self, partial: dict) -> None:
        data = _config_to_dict(self._config)
        data.update(partial or {})
        self._config = StencilConfig.from_dict(data)
        self.configChanged.emit(_config_to_dict(self._config))

    @Slot(str)
    def scanFiles(self, input_dir: str) -> None:
        path = Path(input_dir)
        if not path.exists():
            self.filesScanned.emit({"files": []})
            return
        files = _find_files(path, self._config.paste_patterns + self._config.outline_patterns)
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
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "选择配置文件",
            str(self._project_root / "config"),
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
            self.jobLog.emit(f"文件不存在: {path}")
            return ""
        except OSError as exc:
            self.jobLog.emit(f"读取文件失败: {exc}")
            return ""
        return base64.b64encode(data).decode("ascii")

    @Slot()
    def openPreview(self) -> None:
        self._show_preview()

    @Slot(str)
    def loadPreviewStl(self, path: str) -> None:
        if not path:
            self.jobLog.emit("预览 STL 路径为空。")
            return
        if self._preview_viewer is None:
            self.jobLog.emit("预览视图未初始化。")
            return
        if not Path(path).exists():
            self.jobLog.emit(f"未找到 STL: {path}")
            return
        self._preview_viewer.load_stl(path)
        self._show_preview()

    @Slot(str, result=str)
    def importZip(self, zip_path: str) -> str:
        path = Path(zip_path)
        if not path.exists():
            self.jobLog.emit(f"未找到 ZIP: {zip_path}")
            return ""
        temp_dir = Path(tempfile.mkdtemp(prefix="stencilforge_"))
        try:
            with zipfile.ZipFile(path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            self._temp_dirs.append(temp_dir)
            return str(temp_dir)
        except zipfile.BadZipFile:
            self.jobLog.emit("无效的 ZIP 文件。")
            return ""

    @Slot(str, str, str)
    def runJob(self, input_dir: str, output_stl: str, config_path: str) -> None:
        with self._job_lock:
            if self._job_running:
                self.jobLog.emit("任务已在运行。")
                return
            self._job_running = True

        def worker():
            try:
                self.jobStatus.emit("running")
                self.jobProgress.emit(0)
                config = self._config
                if config_path:
                    config = StencilConfig.from_json(Path(config_path))
                generate_stencil(Path(input_dir), Path(output_stl), config)
                self.jobProgress.emit(100)
                self.jobStatus.emit("success")
                self.jobDone.emit({"output_stl": output_stl})
            except Exception as exc:
                self.jobStatus.emit("error")
                self.jobError.emit(str(exc))
            finally:
                with self._job_lock:
                    self._job_running = False

        threading.Thread(target=worker, daemon=True).start()

    @Slot()
    def stopJob(self) -> None:
        self.jobLog.emit("已请求停止，当前任务暂不支持取消。")


def main() -> int:
    flags = "--enable-webgl --ignore-gpu-blocklist --use-angle=d3d11 --disable-gpu-sandbox --disable-gpu-compositing"
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if flags not in existing:
        combined = f"{existing} {flags}".strip()
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = combined

    app = QApplication(sys.argv)
    project_root = Path(__file__).resolve().parents[2]
    html_path = project_root / "ui-vue" / "dist" / "index.html"
    if not html_path.exists():
        raise FileNotFoundError(
            f"未找到 UI 构建产物: {html_path}。请在 ui-vue 中执行 `npm install` 和 `npm run build`。"
        )

    view = QWebEngineView()
    settings = view.settings()
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
    settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)
    settings.setAttribute(QWebEngineSettings.Accelerated2dCanvasEnabled, False)

    channel = QWebChannel()
    backend = BackendBridge(project_root)
    preview_dialog, preview_viewer = _build_preview_dialog(view)
    backend.attach_preview(preview_dialog, preview_viewer)
    channel.registerObject("backend", backend)
    view.page().setWebChannel(channel)
    view.setUrl(QUrl.fromLocalFile(str(html_path)))

    _fit_to_screen(view, max_ratio=(0.9, 0.85), max_size=(1280, 820), min_size=(980, 680))
    view.setWindowTitle("StencilForge")
    view.show()
    return app.exec()


def _build_preview_dialog(parent: QWebEngineView) -> tuple[QDialog, VtkStlViewer]:
    dialog = QDialog(parent)
    dialog.setWindowTitle("钢网预览")
    _fit_to_screen(dialog, max_ratio=(0.8, 0.8), max_size=(980, 760), min_size=(720, 540))
    dialog.setStyleSheet(
        "QDialog { background-color: #f3e6d8; }"
        "QToolBar { background-color: rgba(246, 232, 214, 0.95); "
        "border: 1px solid #e2c7a6; color: #5b3a1e; }"
        "QToolButton { color: #5b3a1e; padding: 4px 10px; }"
        "QToolButton:checked { background-color: #e7c8a4; }"
    )
    viewer = VtkStlViewer(dialog)
    toolbar = QToolBar(dialog)
    toolbar.setMovable(False)
    fit_action = toolbar.addAction("适配")
    reset_action = toolbar.addAction("重置")
    wire_action = toolbar.addAction("线框")
    axes_action = toolbar.addAction("坐标轴")
    wire_action.setCheckable(True)
    axes_action.setCheckable(True)
    axes_action.setChecked(True)

    fit_action.triggered.connect(viewer.fit_view)
    reset_action.triggered.connect(viewer.reset_view)
    wire_action.toggled.connect(viewer.set_wireframe)
    axes_action.toggled.connect(viewer.toggle_axes)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(0)
    layout.addWidget(toolbar)
    layout.addWidget(viewer)
    return dialog, viewer


def _fit_to_screen(
    widget: QDialog | QWebEngineView,
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


if __name__ == "__main__":
    raise SystemExit(main())
