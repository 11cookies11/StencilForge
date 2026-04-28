from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QSurfaceFormat, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

try:
    from .i18n import preview_labels, text
    from .title_bar import TitleBar
    from .vtk_viewer import VtkStlViewer
    from .ui_support import center_window, resolve_icon_path, resolve_project_root
except ImportError:
    # Allow running as a script when package context is missing.
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from stencilforge.i18n import preview_labels, text
    from stencilforge.title_bar import TitleBar
    from stencilforge.vtk_viewer import VtkStlViewer
    from stencilforge.ui_support import center_window, resolve_icon_path, resolve_project_root


def main() -> int:
    locale = os.environ.get("STENCILFORGE_LOCALE")
    if len(sys.argv) < 2:
        print(text(locale, "cli.preview_usage"))
        return 1
    stl_path = Path(sys.argv[1])
    if not stl_path.exists():
        print(text(locale, "cli.stl_not_found", path=stl_path))
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

    labels = preview_labels(locale)
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle(labels["title"])
    window.setWindowFlag(Qt.FramelessWindowHint, True)
    window.setWindowFlag(Qt.Window, True)
    center_window(window, target_size=(980, 760))
    project_root = resolve_project_root()
    icon_path = resolve_icon_path(project_root)
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
if __name__ == "__main__":
    raise SystemExit(main())
