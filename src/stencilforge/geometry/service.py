from __future__ import annotations

"""Gerber 几何服务：负责读取图层与单位换算。"""

import logging
from pathlib import Path
from typing import Iterable

from gerber import load_layer
from shapely import affinity
from shapely.ops import unary_union

from ..config import StencilConfig
from .outline import OutlineBuilder
from .primitives import PrimitiveGeometryBuilder

logger = logging.getLogger(__name__)


class GerberGeometryService:
    def __init__(self, config: StencilConfig) -> None:
        self._config = config
        self._primitive_builder = PrimitiveGeometryBuilder(config)
        self._outline_builder = OutlineBuilder(config)
        self._last_outline_debug: dict | None = None

    def load_paste_geometry(self, paths: Iterable[Path]):
        # 读取多份锡膏层并合并
        geometries = []
        for path in paths:
            layer = self._load_layer(path, "paste")
            geom = self._primitive_builder.build(layer.primitives)
            geom = self._scale_to_mm(geom, layer.cam_source.units)
            geometries.append(geom)
        return self._merge_geometries(geometries)

    def load_outline_geometry(self, path: Path):
        # 读取板框并构建轮廓
        layer = self._load_layer(path, "outline")
        geom = self._outline_builder.build(layer.primitives, layer.cam_source.units)
        self._last_outline_debug = self._outline_builder.get_last_robust_debug()
        geom = self._scale_to_mm(geom, layer.cam_source.units)
        return geom

    def get_last_outline_debug(self) -> dict | None:
        return self._last_outline_debug

    @staticmethod
    def _load_layer(path: Path, label: str):
        # Gerber 图层读取与基础信息输出
        logger.info("Loading %s layer: %s", label, path.name)
        layer = load_layer(str(path))
        logger.info("Units: %s, primitives: %s", layer.cam_source.units, len(layer.primitives))
        return layer

    @staticmethod
    def _scale_to_mm(geom, units: str):
        # 统一单位为 mm
        if geom is None or geom.is_empty:
            return geom
        if units == "inch":
            return affinity.scale(geom, xfact=25.4, yfact=25.4, origin=(0, 0))
        return geom

    @staticmethod
    def _merge_geometries(geometries):
        # 合并多几何并忽略空项
        if not geometries:
            return None
        return unary_union([g for g in geometries if g is not None and not g.is_empty])
