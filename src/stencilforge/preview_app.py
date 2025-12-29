from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QGuiApplication, QSurfaceFormat, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

try:
    from .title_bar import TitleBar
    from .vtk_viewer import VtkStlViewer
except ImportError:
    # Allow running as a script when package context is missing.
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from stencilforge.title_bar import TitleBar
    from stencilforge.vtk_viewer import VtkStlViewer


_PREVIEW_I18N = {
    "zh-CN": {
        "title": "钢网预览",
        "fit": "适配",
        "reset": "重置",
        "wireframe": "线框",
        "axes": "坐标轴",
    },
    "en": {
        "title": "Stencil preview",
        "fit": "Fit",
        "reset": "Reset",
        "wireframe": "Wireframe",
        "axes": "Axes",
    },
}


def _normalize_locale(locale: str | None) -> str:
    if not locale:
        return "zh-CN"
    lowered = locale.lower()
    if lowered.startswith("en"):
        return "en"
    return "zh-CN"


def _preview_labels(locale: str | None) -> dict:
    key = _normalize_locale(locale)
    return _PREVIEW_I18N.get(key, _PREVIEW_I18N["zh-CN"])


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m stencilforge.preview_app <stl_path>")
        return 1
    stl_path = Path(sys.argv[1])
    if not stl_path.exists():
        print(f"STL not found: {stl_path}")
        return 1

    os.environ.setdefault("QT_OPENGL", "software")
    os.environ.setdefault("LIBGL_ALWAYS_SOFTWARE", "1")
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("StencilForge")
        except Exception:
            pass
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    try:
        QCoreApplication.setAttribute(Qt.AA_UseDesktopOpenGL)
    except Exception:
        pass
    try:
        QSurfaceFormat.setDefaultFormat(QVTKRenderWindowInteractor.defaultFormat())
    except Exception:
        pass

    labels = _preview_labels(os.environ.get("STENCILFORGE_LOCALE"))
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle(labels["title"])
    window.setWindowFlag(Qt.FramelessWindowHint, True)
    window.setWindowFlag(Qt.Window, True)
    _center_window(window, target_size=(980, 760))
    project_root = Path(__file__).resolve().parents[2]
    icon_path = _resolve_icon_path(project_root)
    if icon_path is not None:
        icon = QIcon(str(icon_path))
        app.setWindowIcon(icon)
        window.setWindowIcon(icon)

    container = QWidget(window)
    container.setStyleSheet(
        "QWidget { background-color: #f8fafc; }"
        "QToolBar { background-color: rgba(255, 255, 255, 0.95); "
        "border: 1px solid #e2e8f0; color: #334155; }"
        "QToolButton { color: #334155; padding: 4px 10px; }"
        "QToolButton:checked { background-color: #e2e8f0; }"
    )
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    title_bar = TitleBar(container, labels["title"])
    toolbar = QToolBar(container)
    toolbar.setMovable(False)
    fit_action = toolbar.addAction(labels["fit"])
    reset_action = toolbar.addAction(labels["reset"])
    wire_action = toolbar.addAction(labels["wireframe"])
    axes_action = toolbar.addAction(labels["axes"])
    wire_action.setCheckable(True)
    axes_action.setCheckable(True)
    axes_action.setChecked(True)

    viewer = VtkStlViewer(container)
    fit_action.triggered.connect(viewer.fit_view)
    reset_action.triggered.connect(viewer.reset_view)
    wire_action.toggled.connect(viewer.set_wireframe)
    axes_action.toggled.connect(viewer.toggle_axes)

    layout.addWidget(title_bar)
    layout.addWidget(toolbar)
    layout.addWidget(viewer)

    window.setCentralWidget(container)
    window.show()
    viewer.load_stl(str(stl_path))
    return app.exec()


def _center_window(window: QMainWindow, target_size: tuple[int, int]) -> None:
    window.resize(*target_size)
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return
    geometry = screen.availableGeometry()
    x = geometry.x() + max((geometry.width() - target_size[0]) // 2, 0)
    y = geometry.y() + max((geometry.height() - target_size[1]) // 2, 0)
    window.move(x, y)


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
