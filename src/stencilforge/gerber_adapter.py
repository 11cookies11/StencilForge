from __future__ import annotations

"""兼容入口：保留旧 API，内部转发到 geometry 子模块。"""

from pathlib import Path
from typing import Iterable

from .config import StencilConfig
from .geometry import GerberGeometryService, OutlineBuilder, PrimitiveGeometryBuilder

__all__ = [
    "GerberGeometryService",
    "OutlineBuilder",
    "PrimitiveGeometryBuilder",
    "load_outline_geometry",
    "load_outline_geometry_debug",
    "load_outline_segments",
    "load_paste_geometry",
]


def load_paste_geometry(paths: Iterable[Path], config: StencilConfig):
    # 兼容旧调用：直接转发到服务类
    return GerberGeometryService(config).load_paste_geometry(paths)


def load_outline_geometry(path: Path, config: StencilConfig):
    # 兼容旧调用：直接转发到服务类
    return GerberGeometryService(config).load_outline_geometry(path)


def load_outline_geometry_debug(path: Path, config: StencilConfig):
    # 兼容旧调用：直接转发到服务类
    return GerberGeometryService(config).load_outline_geometry_debug(path)


def load_outline_segments(path: Path, config: StencilConfig):
    # 兼容旧调用：直接转发到服务类
    return GerberGeometryService(config).load_outline_segments(path)
