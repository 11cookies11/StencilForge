from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QMainWindow,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from .vtk_viewer import VtkStlViewer
from .web_bridge import WebBridge


class MainWindow(QMainWindow):
    """Main window: WebEngine UI on the left, VTK STL viewer on the right."""

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.setWindowTitle("StencilForge")
        self.resize(1400, 900)

        self._web = QWebEngineView()
        self._preview_dialog: QDialog | None = None
        self._preview_viewer: VtkStlViewer | None = None
        self.setCentralWidget(self._web)

        settings = self._web.settings()
        settings.setAttribute(QWebEngineSettings.WebGLEnabled, False)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        ui_path = project_root / "ui" / "vtk_index.html"
        if not ui_path.exists():
            raise FileNotFoundError(f"UI HTML not found: {ui_path}")

        self._channel = QWebChannel()
        self._bridge = WebBridge(project_root / "output")
        self._bridge.stlGenerated.connect(self._on_stl_generated)
        self._bridge.previewRequested.connect(self._open_preview_dialog)
        self._bridge.pickStlRequested.connect(self._pick_stl_file)
        self._channel.registerObject("backend", self._bridge)
        self._web.page().setWebChannel(self._channel)
        self._web.setUrl(QUrl.fromLocalFile(str(ui_path)))

    def _ensure_preview_dialog(self) -> None:
        if self._preview_dialog is not None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Stencil Preview")
        dialog.resize(900, 700)
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
        self._preview_dialog = dialog
        self._preview_viewer = viewer

    def _open_preview_dialog(self) -> None:
        self._ensure_preview_dialog()
        if self._preview_dialog is not None:
            self._preview_dialog.show()
            self._preview_dialog.raise_()

    def _pick_stl_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Select STL",
            str(Path.home()),
            "STL Files (*.stl)",
        )
        if filename:
            self._load_stl_into_preview(filename)

    def _on_stl_generated(self, path: str) -> None:
        self._load_stl_into_preview(path)

    def _load_stl_into_preview(self, path: str) -> None:
        self._ensure_preview_dialog()
        if self._preview_viewer is not None:
            self._preview_viewer.load_stl(path)
        if self._preview_dialog is not None:
            self._preview_dialog.show()
            self._preview_dialog.raise_()


def main() -> int:
    app = QApplication(sys.argv)
    project_root = Path(__file__).resolve().parents[2]
    window = MainWindow(project_root)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
