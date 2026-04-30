from __future__ import annotations

import json
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QMainWindow

from ..config import StencilConfig


def resolve_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def ui_dist_candidates(project_root: Path) -> list[Path]:
    base = Path(getattr(sys, "_MEIPASS", project_root))
    exe_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else project_root
    return [
        base / "ui-vue" / "dist" / "index.html",
        exe_dir / "ui-vue" / "dist" / "index.html",
        project_root / "ui-vue" / "dist" / "index.html",
        project_root / "dist" / "index.html",
    ]


def resolve_ui_dist(project_root: Path) -> Path | None:
    for candidate in ui_dist_candidates(project_root):
        if candidate.exists():
            return candidate
    return None


def resolve_log_path(project_root: Path) -> Path | None:
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


def resolve_ui_state_path(project_root: Path) -> Path:
    return StencilConfig.default_path(project_root).parent / "ui_state.json"


def load_ui_state(path: Path) -> dict[str, str]:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_ui_state(path: Path, state: dict[str, str]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def default_export_dir() -> Path:
    home = Path.home()
    documents = home / "Documents"
    base = documents if documents.exists() else home
    return base / "StencilForge" / "Exports"


def resolve_icon_path(project_root: Path) -> Path | None:
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


def fit_to_screen(
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


def center_window(window: QMainWindow, target_size: tuple[int, int]) -> None:
    screen = QGuiApplication.primaryScreen()
    if screen is None:
        window.resize(*target_size)
        return
    geometry = screen.availableGeometry()
    width = min(target_size[0], max(geometry.width(), 1))
    height = min(target_size[1], max(geometry.height(), 1))
    window.resize(width, height)
    x = geometry.x() + max((geometry.width() - width) // 2, 0)
    y = geometry.y() + max((geometry.height() - height) // 2, 0)
    window.move(x, y)
