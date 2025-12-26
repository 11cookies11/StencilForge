from __future__ import annotations

import sys
import threading
from fnmatch import fnmatch
from pathlib import Path

from PySide6.QtCore import QObject, QUrl, Signal, Slot
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWidgets import QApplication, QFileDialog

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
    app = QApplication(sys.argv)
    project_root = Path(__file__).resolve().parents[2]
    html_path = project_root / "ui" / "pages" / "upload.html"
    if not html_path.exists():
        raise FileNotFoundError(f"UI file not found: {html_path}")

    view = QWebEngineView()
    settings = view.settings()
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
    settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

    channel = QWebChannel()
    backend = BackendBridge(project_root)
    channel.registerObject("backend", backend)
    view.page().setWebChannel(channel)
    view.setUrl(QUrl.fromLocalFile(str(html_path)))

    view.resize(1280, 820)
    view.setWindowTitle("StencilForge")
    view.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
