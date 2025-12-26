from __future__ import annotations

import sys
import threading
import base64
import os
import tempfile
import zipfile
from fnmatch import fnmatch
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWidgets import QApplication, QDialog, QFileDialog, QToolBar, QVBoxLayout

from .vtk_viewer import VtkStlViewer

from .config import StencilConfig
from .pipeline import generate_stencil


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
            self.jobLog.emit("Preview window not initialized.")
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
            self.jobLog.emit(f"Config not found: {path}")
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
            "Save STL",
            str(self._project_root / default_name),
            "STL Files (*.stl)",
        )
        return filename

    @Slot(result=str)
    def pickDirectory(self) -> str:
        directory = QFileDialog.getExistingDirectory(None, "Select Gerber Folder", str(self._project_root))
        return directory

    @Slot(result=str)
    def pickConfigFile(self) -> str:
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "Select Config",
            str(self._project_root / "config"),
            "Config (*.json)",
        )
        return filename

    @Slot(result=str)
    def pickZipFile(self) -> str:
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "Select Gerber ZIP",
            str(self._project_root),
            "ZIP Files (*.zip)",
        )
        return filename

    @Slot(result=str)
    def pickStlFile(self) -> str:
        filename, _ = QFileDialog.getOpenFileName(
            None,
            "Select STL",
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
            self.jobLog.emit(f"File not found: {path}")
            return ""
        except OSError as exc:
            self.jobLog.emit(f"Failed to read file: {exc}")
            return ""
        return base64.b64encode(data).decode("ascii")

    @Slot()
    def openPreview(self) -> None:
        self._show_preview()

    @Slot(str)
    def loadPreviewStl(self, path: str) -> None:
        if not path:
            self.jobLog.emit("Preview STL path is empty.")
            return
        if self._preview_viewer is None:
            self.jobLog.emit("Preview viewer not initialized.")
            return
        if not Path(path).exists():
            self.jobLog.emit(f"STL not found: {path}")
            return
        self._preview_viewer.load_stl(path)
        self._show_preview()

    @Slot(str, result=str)
    def importZip(self, zip_path: str) -> str:
        path = Path(zip_path)
        if not path.exists():
            self.jobLog.emit(f"ZIP not found: {zip_path}")
            return ""
        temp_dir = Path(tempfile.mkdtemp(prefix="stencilforge_"))
        try:
            with zipfile.ZipFile(path, "r") as zip_ref:
                zip_ref.extractall(temp_dir)
            self._temp_dirs.append(temp_dir)
            return str(temp_dir)
        except zipfile.BadZipFile:
            self.jobLog.emit("Invalid ZIP file.")
            return ""

    @Slot(str, str, str)
    def runJob(self, input_dir: str, output_stl: str, config_path: str) -> None:
        with self._job_lock:
            if self._job_running:
                self.jobLog.emit("Job already running.")
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
        self.jobLog.emit("Stop requested. Current job cannot be cancelled yet.")


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
            f"UI build not found: {html_path}. Run `npm install` and `npm run build` in ui-vue."
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

    view.resize(1280, 820)
    view.setWindowTitle("StencilForge")
    view.show()
    return app.exec()


def _build_preview_dialog(parent: QWebEngineView) -> tuple[QDialog, VtkStlViewer]:
    dialog = QDialog(parent)
    dialog.setWindowTitle("Stencil Preview")
    dialog.resize(980, 760)
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
    fit_action = toolbar.addAction("Fit")
    reset_action = toolbar.addAction("Reset")
    wire_action = toolbar.addAction("Wireframe")
    axes_action = toolbar.addAction("Axes")
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


if __name__ == "__main__":
    raise SystemExit(main())
