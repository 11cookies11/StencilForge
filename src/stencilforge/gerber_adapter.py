from __future__ import annotations

"""Compatibility layer for legacy imports."""

from pathlib import Path
from typing import Iterable

from .config import StencilConfig
from .geometry import GerberGeometryService, OutlineBuilder, PrimitiveGeometryBuilder

__all__ = [
    "GerberGeometryService",
    "OutlineBuilder",
    "PrimitiveGeometryBuilder",
    "load_outline_geometry",
    "load_paste_geometry",
]


def load_paste_geometry(paths: Iterable[Path], config: StencilConfig):
    return GerberGeometryService(config).load_paste_geometry(paths)


def load_outline_geometry(path: Path, config: StencilConfig):
    return GerberGeometryService(config).load_outline_geometry(path)
