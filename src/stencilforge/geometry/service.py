from __future__ import annotations

"""Gerber geometry service: load layers and normalize units."""

import builtins
from contextlib import contextmanager
import logging
from pathlib import Path
from threading import RLock
from typing import Iterable

from gerber import load_layer
from shapely import affinity
from shapely.ops import unary_union

from ..config import StencilConfig
from .outline import OutlineBuilder
from .primitives import PrimitiveGeometryBuilder

logger = logging.getLogger(__name__)
_OPEN_PATCH_LOCK = RLock()


class GerberGeometryService:
    def __init__(self, config: StencilConfig) -> None:
        self._config = config
        self._primitive_builder = PrimitiveGeometryBuilder(config)
        self._outline_builder = OutlineBuilder(config)
        self._last_outline_debug: dict | None = None

    def load_paste_geometry(self, paths: Iterable[Path]):
        geometries = []
        for path in paths:
            layer = self._load_layer(path, "paste")
            geom = self._primitive_builder.build(layer.primitives)
            geom = self._scale_to_mm(geom, layer.cam_source.units)
            geometries.append(geom)
        return self._merge_geometries(geometries)

    def load_outline_geometry(self, path: Path):
        layer = self._load_layer(path, "outline")
        geom = self._outline_builder.build(layer.primitives, layer.cam_source.units)
        self._last_outline_debug = self._outline_builder.get_last_robust_debug()
        geom = self._scale_to_mm(geom, layer.cam_source.units)
        return geom

    def get_last_outline_debug(self) -> dict | None:
        return self._last_outline_debug

    @staticmethod
    def _load_layer(path: Path, label: str):
        logger.info("Loading %s layer: %s", label, path.name)
        with _legacy_open_mode_compat():
            with _legacy_outline_primitive_compat():
                layer = load_layer(str(path))
        logger.info("Units: %s, primitives: %s", layer.cam_source.units, len(layer.primitives))
        return layer

    @staticmethod
    def _scale_to_mm(geom, units: str):
        if geom is None or geom.is_empty:
            return geom
        if units == "inch":
            return affinity.scale(geom, xfact=25.4, yfact=25.4, origin=(0, 0))
        return geom

    @staticmethod
    def _merge_geometries(geometries):
        if not geometries:
            return None
        return unary_union([g for g in geometries if g is not None and not g.is_empty])


@contextmanager
def _legacy_open_mode_compat():
    # pcb-tools still uses "rU" in some parsing paths; Python 3.11 removed it.
    with _OPEN_PATCH_LOCK:
        original_open = builtins.open

        def compat_open(file, mode="r", *args, **kwargs):
            if isinstance(mode, str) and "U" in mode:
                mode = mode.replace("U", "") or "r"
            return original_open(file, mode, *args, **kwargs)

        builtins.open = compat_open
        try:
            yield
        finally:
            builtins.open = original_open


@contextmanager
def _legacy_outline_primitive_compat():
    # Some public Gerbers contain unclosed AM outline primitives.
    # Patch parser behavior to auto-close the final point for compatibility.
    with _OPEN_PATCH_LOCK:
        try:
            import gerber.am_statements as am_statements
        except Exception:
            yield
            return

        original_init = am_statements.AMOutlinePrimitive.__init__

        def compat_init(self, code, exposure, start_point, points, rotation):
            try:
                return original_init(self, code, exposure, start_point, points, rotation)
            except ValueError as exc:
                if "must be closed" not in str(exc):
                    raise
                patched_points = list(points)
                if patched_points and patched_points[-1] != start_point:
                    patched_points.append(start_point)
                return original_init(self, code, exposure, start_point, patched_points, rotation)

        am_statements.AMOutlinePrimitive.__init__ = compat_init
        try:
            yield
        finally:
            am_statements.AMOutlinePrimitive.__init__ = original_init
