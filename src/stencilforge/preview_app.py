from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QGuiApplication, QSurfaceFormat
from PySide6.QtWidgets import QApplication, QMainWindow, QToolBar, QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from .title_bar import TitleBar
from .vtk_viewer import VtkStlViewer


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
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    try:
        QCoreApplication.setAttribute(Qt.AA_UseDesktopOpenGL)
    except Exception:
        pass
    try:
        QSurfaceFormat.setDefaultFormat(QVTKRenderWindowInteractor.defaultFormat())
    except Exception:
        pass

    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("钢网预览")
    window.setWindowFlag(Qt.FramelessWindowHint, True)
    window.setWindowFlag(Qt.Window, True)
    _center_window(window, target_size=(980, 760))

    container = QWidget(window)
    container.setStyleSheet(
        "QWidget { background-color: #f3e6d8; }"
        "QToolBar { background-color: rgba(246, 232, 214, 0.95); "
        "border: 1px solid #e2c7a6; color: #5b3a1e; }"
        "QToolButton { color: #5b3a1e; padding: 4px 10px; }"
        "QToolButton:checked { background-color: #e7c8a4; }"
    )
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)

    title_bar = TitleBar(container, "钢网预览")
    toolbar = QToolBar(container)
    toolbar.setMovable(False)
    fit_action = toolbar.addAction("适配")
    reset_action = toolbar.addAction("重置")
    wire_action = toolbar.addAction("线框")
    axes_action = toolbar.addAction("坐标轴")
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


if __name__ == "__main__":
    raise SystemExit(main())
