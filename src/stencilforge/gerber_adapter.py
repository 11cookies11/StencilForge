from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import Iterable

from gerber import load_layer
from gerber import primitives as gprim
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize

from .config import StencilConfig

logger = logging.getLogger(__name__)


def load_paste_geometry(paths: Iterable[Path], config: StencilConfig):
    geometries = []
    for path in paths:
        logger.info("Loading paste layer: %s", path.name)
        layer = load_layer(str(path))
        logger.info("Units: %s, primitives: %s", layer.cam_source.units, len(layer.primitives))
        geom = _primitives_to_geometry(layer.primitives, config)
        geom = _scale_to_mm(geom, layer.cam_source.units)
        geometries.append(geom)
    return _merge_geometries(geometries)


def load_outline_geometry(path: Path, config: StencilConfig):
    logger.info("Loading outline layer: %s", path.name)
    layer = load_layer(str(path))
    logger.info("Units: %s, primitives: %s", layer.cam_source.units, len(layer.primitives))
    geom = _outline_from_primitives(layer.primitives, config)
    geom = _scale_to_mm(geom, layer.cam_source.units)
    return geom


def _scale_to_mm(geom, units: str):
    if geom is None or geom.is_empty:
        return geom
    if units == "inch":
        return affinity.scale(geom, xfact=25.4, yfact=25.4, origin=(0, 0))
    return geom


def _merge_geometries(geometries):
    if not geometries:
        return None
    return unary_union([g for g in geometries if g is not None and not g.is_empty])


def _primitives_to_geometry(primitives, config: StencilConfig):
    dark = []
    clear = []
    for prim in primitives:
        geom = _primitive_to_shape(prim, config)
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


def _primitive_to_shape(prim, config: StencilConfig):
    if isinstance(prim, gprim.Circle):
        geom = Point(prim.position).buffer(
            prim.radius, resolution=config.curve_resolution
        )
        return _subtract_hole(geom, prim)
    if isinstance(prim, gprim.Rectangle):
        geom = Polygon(prim.vertices)
        return _subtract_hole(geom, prim)
    if isinstance(prim, gprim.Obround):
        shapes = [
            _primitive_to_shape(prim.subshapes["circle1"], config),
            _primitive_to_shape(prim.subshapes["circle2"], config),
            _primitive_to_shape(prim.subshapes["rectangle"], config),
        ]
        return unary_union(shapes)
    if isinstance(prim, gprim.Polygon):
        geom = Polygon(prim.vertices)
        return _subtract_hole(geom, prim)
    if isinstance(prim, gprim.Line):
        return _line_to_shape(prim, config)
    if isinstance(prim, gprim.Arc):
        return _arc_to_shape(prim, config)
    if isinstance(prim, gprim.Region):
        return _region_to_shape(prim, config)
    return None


def _subtract_hole(geom, prim):
    hole_diameter = getattr(prim, "hole_diameter", 0) or 0
    if hole_diameter <= 0:
        return geom
    hole = Point(prim.position).buffer(hole_diameter / 2.0, resolution=32)
    return geom.difference(hole)


def _line_to_shape(line: gprim.Line, config: StencilConfig):
    if isinstance(line.aperture, gprim.Circle):
        radius = line.aperture.radius
        return LineString([line.start, line.end]).buffer(
            radius, cap_style=1, join_style=2, resolution=config.curve_resolution
        )
    if isinstance(line.aperture, gprim.Rectangle):
        return Polygon(line.vertices)
    width = getattr(line.aperture, "width", None)
    height = getattr(line.aperture, "height", None)
    if width and height:
        radius = max(width, height) / 2.0
        return LineString([line.start, line.end]).buffer(
            radius, cap_style=1, join_style=2, resolution=config.curve_resolution
        )
    return None


def _arc_to_shape(arc: gprim.Arc, config: StencilConfig):
    points = _arc_points(arc, config.arc_steps)
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
        radius, cap_style=1, join_style=2, resolution=config.curve_resolution
    )


def _arc_points(arc: gprim.Arc, steps: int):
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


def _region_to_shape(region: gprim.Region, config: StencilConfig):
    points = []
    for prim in region.primitives:
        if isinstance(prim, gprim.Line):
            if not points:
                points.append(prim.start)
            points.append(prim.end)
        elif isinstance(prim, gprim.Arc):
            arc_pts = _arc_points(prim, config.arc_steps)
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
    return _primitives_to_geometry(region.primitives, config)


def _outline_from_primitives(primitives, config: StencilConfig):
    for prim in primitives:
        if isinstance(prim, gprim.Region):
            return _region_to_shape(prim, config)
    segments = []
    for prim in primitives:
        if isinstance(prim, gprim.Line):
            segments.append(LineString([prim.start, prim.end]))
        elif isinstance(prim, gprim.Arc):
            arc_pts = _arc_points(prim, config.arc_steps)
            if len(arc_pts) >= 2:
                segments.append(LineString(arc_pts))
    if segments:
        polygons = list(polygonize(segments))
        if polygons:
            return max(polygons, key=lambda p: p.area)
    points = []
    for prim in primitives:
        if isinstance(prim, gprim.Line):
            if not points:
                points.append(prim.start)
            points.append(prim.end)
        elif isinstance(prim, gprim.Arc):
            arc_pts = _arc_points(prim, config.arc_steps)
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
    return _primitives_to_geometry(primitives, config)
