from __future__ import annotations

"""Gerber primitive -> Shapely 几何的转换逻辑。"""

import math
import logging

from gerber import primitives as gprim
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..config import StencilConfig

logger = logging.getLogger(__name__)


def _merge_geometries(geometries):
    # 合并多个几何，自动忽略空/None
    if not geometries:
        return None
    return unary_union([g for g in geometries if g is not None and not g.is_empty])


class PrimitiveGeometryBuilder:
    def __init__(self, config: StencilConfig) -> None:
        self._config = config

    def build(self, primitives):
        return self._primitives_to_geometry(primitives)

    def _primitives_to_geometry(self, primitives):
        # 根据极性（dark/clear）构建最终几何
        dark = []
        clear = []
        for prim in primitives:
            geom = self._primitive_to_shape(prim)
            if geom is None or geom.is_empty:
                continue
            if getattr(prim, "level_polarity", "dark") == "clear":
                clear.append(geom)
            else:
                dark.append(geom)
        merged = _merge_geometries(dark)
        if clear:
            merged = merged.difference(_merge_geometries(clear))
        return merged

    def _primitive_to_shape(self, prim):
        # 将单个 Gerber 原语转换为 Shapely 几何
        if isinstance(prim, gprim.Circle):
            geom = Point(prim.position).buffer(
                prim.radius, resolution=self._config.curve_resolution
            )
            return self._subtract_hole(geom, prim)
        if isinstance(prim, gprim.Rectangle):
            geom = Polygon(prim.vertices)
            return self._subtract_hole(geom, prim)
        if isinstance(prim, gprim.Obround):
            shapes = [
                self._primitive_to_shape(prim.subshapes["circle1"]),
                self._primitive_to_shape(prim.subshapes["circle2"]),
                self._primitive_to_shape(prim.subshapes["rectangle"]),
            ]
            return unary_union(shapes)
        if isinstance(prim, gprim.Polygon):
            geom = Polygon(prim.vertices)
            return self._subtract_hole(geom, prim)
        if isinstance(prim, gprim.Line):
            return self._line_to_shape(prim)
        if isinstance(prim, gprim.Arc):
            return self._arc_to_shape(prim)
        if isinstance(prim, gprim.Region):
            return self._region_to_shape(prim)
        return None

    @staticmethod
    def _subtract_hole(geom, prim):
        # 若原语带孔，则从几何上减去
        hole_diameter = getattr(prim, "hole_diameter", 0) or 0
        if hole_diameter <= 0:
            return geom
        hole = Point(prim.position).buffer(hole_diameter / 2.0, resolution=32)
        return geom.difference(hole)

    def _line_to_shape(self, line: gprim.Line):
        # 线段按口径（aperture）转换为缓冲形状
        if isinstance(line.aperture, gprim.Circle):
            radius = line.aperture.radius
            return LineString([line.start, line.end]).buffer(
                radius,
                cap_style=1,
                join_style=2,
                resolution=self._config.curve_resolution,
            )
        if isinstance(line.aperture, gprim.Rectangle):
            return Polygon(line.vertices)
        width = getattr(line.aperture, "width", None)
        height = getattr(line.aperture, "height", None)
        if width and height:
            radius = max(width, height) / 2.0
            return LineString([line.start, line.end]).buffer(
                radius,
                cap_style=1,
                join_style=2,
                resolution=self._config.curve_resolution,
            )
        return None

    def _arc_to_shape(self, arc: gprim.Arc):
        # 圆弧离散成线段后缓冲成面
        points = self._arc_points(arc, self._config.arc_steps)
        radius = None
        if isinstance(arc.aperture, gprim.Circle):
            radius = arc.aperture.radius
        if radius is None:
            width = getattr(arc.aperture, "width", None)
            height = getattr(arc.aperture, "height", None)
            if width and height:
                radius = max(width, height) / 2.0
        if radius is None:
            return None
        return LineString(points).buffer(
            radius,
            cap_style=1,
            join_style=2,
            resolution=self._config.curve_resolution,
        )

    @staticmethod
    def _arc_points(arc: gprim.Arc, steps: int):
        # 生成圆弧采样点，顺/逆时针处理不同
        steps = max(8, steps)
        start = arc.start_angle
        end = arc.end_angle
        if arc.direction == "counterclockwise":
            if end <= start:
                end += 2 * math.pi
            angles = [start + (end - start) * i / (steps - 1) for i in range(steps)]
        else:
            if end >= start:
                end -= 2 * math.pi
            angles = [start + (end - start) * i / (steps - 1) for i in range(steps)]
        cx, cy = arc.center
        return [(cx + arc.radius * math.cos(a), cy + arc.radius * math.sin(a)) for a in angles]

    def _region_to_shape(self, region: gprim.Region):
        # Region 由线段/圆弧闭合而成，拼成多边形
        points = []
        for prim in region.primitives:
            if isinstance(prim, gprim.Line):
                if not points:
                    points.append(prim.start)
                points.append(prim.end)
            elif isinstance(prim, gprim.Arc):
                arc_pts = self._arc_points(prim, self._config.arc_steps)
                if not points:
                    points.append(arc_pts[0])
                    points.extend(arc_pts[1:])
                else:
                    points.extend(arc_pts)
        if len(points) >= 3:
            if points[0] != points[-1]:
                points.append(points[0])
            poly = Polygon(points)
            if not poly.is_valid:
                poly = poly.buffer(0)
            return poly
        return self._primitives_to_geometry(region.primitives)
