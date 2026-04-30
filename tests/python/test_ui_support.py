from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QGuiApplication

from stencilforge.ui.support import fit_to_screen, resolve_project_root, ui_dist_candidates


def test_resolve_project_root_points_to_repo_root() -> None:
    expected = Path(__file__).resolve().parents[2]
    assert resolve_project_root() == expected


def test_ui_dist_candidates_include_vite_dist() -> None:
    project_root = Path(__file__).resolve().parents[2]
    candidates = ui_dist_candidates(project_root)
    assert project_root / "ui-vue" / "dist" / "index.html" in candidates


def test_fit_to_screen_uses_active_screen(monkeypatch) -> None:
    class DummyGeometry:
        def __init__(self, x: int, y: int, width: int, height: int) -> None:
            self._x = x
            self._y = y
            self._width = width
            self._height = height

        def x(self) -> int:
            return self._x

        def y(self) -> int:
            return self._y

        def width(self) -> int:
            return self._width

        def height(self) -> int:
            return self._height

    class DummyScreen:
        def __init__(self) -> None:
            self._geometry = DummyGeometry(100, 50, 1200, 800)

        def availableGeometry(self) -> DummyGeometry:
            return self._geometry

    class DummyWidget:
        def __init__(self) -> None:
            self.size = None
            self.pos = None

        def resize(self, width: int, height: int) -> None:
            self.size = (width, height)

        def move(self, x: int, y: int) -> None:
            self.pos = (x, y)

    active_screen = DummyScreen()
    monkeypatch.setattr(QGuiApplication, "screenAt", lambda pos: active_screen)
    monkeypatch.setattr(QGuiApplication, "primaryScreen", lambda: None)

    widget = DummyWidget()
    fit_to_screen(widget, max_ratio=(0.8, 0.85), max_size=(1280, 820), min_size=(980, 680), edge_margin=20)

    assert widget.size == (980, 680)
    assert widget.pos == (210, 110)
