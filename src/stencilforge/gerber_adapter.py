from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import Iterable

from gerber import load_layer
from gerber import primitives as gprim
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, MultiPoint, MultiLineString
from shapely.ops import unary_union, polygonize, linemerge, snap

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
    geom, _ = _outline_from_primitives(layer.primitives, config)
    geom = _scale_to_mm(geom, layer.cam_source.units)
    return geom


def load_outline_geometry_debug(path: Path, config: StencilConfig):
    logger.info("Loading outline layer: %s", path.name)
    layer = load_layer(str(path))
    logger.info("Units: %s, primitives: %s", layer.cam_source.units, len(layer.primitives))
    geom, debug = _outline_from_primitives(layer.primitives, config)
    geom = _scale_to_mm(geom, layer.cam_source.units)
    debug_geom = debug.get("segments_geom")
    if debug_geom is not None:
        debug["segments_geom"] = _scale_to_mm(debug_geom, layer.cam_source.units)
    snapped_geom = debug.get("snapped_geom")
    if snapped_geom is not None:
        debug["snapped_geom"] = _scale_to_mm(snapped_geom, layer.cam_source.units)
    return geom, debug


def load_outline_segments(path: Path, config: StencilConfig):
    layer = load_layer(str(path))
    segments = []
    for prim in layer.primitives:
        if isinstance(prim, gprim.Line):
            segments.append(LineString([prim.start, prim.end]))
        elif isinstance(prim, gprim.Arc):
            arc_pts = _arc_points(prim, config.arc_steps)
            if len(arc_pts) >= 2:
                segments.append(LineString(arc_pts))
    merged = unary_union(segments) if segments else None
    geom = merged
    if geom is not None:
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
    debug = {
        "source": None,
        "segments_geom": None,
        "snapped_geom": None,
        "snap_tol": None,
        "polygonize_polygons": 0,
        "loops_count": 0,
        "loops_geom": None,
        "max_gap_pair": None,
    }
    for prim in primitives:
        if isinstance(prim, gprim.Region):
            geom = _region_to_shape(prim, config)
            if geom is not None and not geom.is_empty:
                logger.info("Outline source: region")
                debug["source"] = "region"
                return geom, debug
    segments = _outline_segments_from_primitives(primitives, config)
    if segments:
        logger.info("Outline segments: %s", len(segments))
        merged = unary_union(segments)
        debug["source"] = "segments"
        debug["segments_geom"] = merged
        debug["max_gap_pair"] = _find_max_gap_pair(segments)
        loops = _build_loops_in_order(segments, config.outline_snap_mm)
        if not loops:
            loops = _build_closed_loops(segments, config.outline_snap_mm)
        if loops:
            debug["loops_count"] = len(loops)
            debug["loops_geom"] = MultiLineString(loops) if len(loops) > 1 else loops[0]
            polygons = _loops_to_polygons(loops)
        else:
            polygons = []
        if not polygons:
            polygons = list(polygonize(merged))
            polygons, snapped_geom, snap_tol = _maybe_snap_polygonize(merged, polygons, config)
            debug["snapped_geom"] = snapped_geom
            debug["snap_tol"] = snap_tol
            debug["polygonize_polygons"] = len(polygons)
        if polygons:
            logger.info("Outline loops: polygons=%s", len(polygons))
            if config.outline_fill_rule == "legacy":
                poly = max(polygons, key=lambda p: p.area)
                if not poly.is_valid:
                    poly = poly.buffer(0)
                return poly, debug
            filled = _outline_evenodd(polygons)
            if filled is not None and not filled.is_empty:
                logger.info("Outline fill rule: evenodd")
                return filled, debug
        logger.info("Outline polygonize failed; using convex hull fallback")
        merged_lines = linemerge(merged)
        points = []
        if isinstance(merged_lines, LineString):
            points = list(merged_lines.coords)
        elif hasattr(merged_lines, "geoms"):
            for geom in merged_lines.geoms:
                points.extend(list(geom.coords))
        if len(points) >= 3:
            hull = MultiPoint(points).convex_hull
            if not hull.is_empty:
                logger.info("Outline fallback: convex hull from %s points", len(points))
                return hull, debug
    logger.info("Outline fallback: primitives_to_geometry")
    debug["source"] = "primitives"
    return _primitives_to_geometry(primitives, config), debug


def _outline_segments_from_primitives(primitives, config: StencilConfig):
    segments = []
    for prim in primitives:
        if isinstance(prim, gprim.Line):
            segments.append(LineString([prim.start, prim.end]))
        elif isinstance(prim, gprim.Arc):
            arc_pts = _arc_points(prim, config.arc_steps)
            if len(arc_pts) >= 2:
                segments.append(LineString(arc_pts))
    return segments


def _build_loops_in_order(segments, tol: float):
    loops = []
    current = []
    start_point = None
    for seg in segments:
        coords = list(seg.coords)
        if len(coords) < 2:
            continue
        if not current:
            current = coords[:]
            start_point = current[0]
            continue
        last = current[-1]
        if _points_close(last, coords[0], tol):
            current.extend(coords[1:])
        elif _points_close(last, coords[-1], tol):
            current.extend(list(reversed(coords))[:-1])
        else:
            loops.extend(_finalize_path_loop(current, start_point, tol))
            current = coords[:]
            start_point = current[0]
    if current:
        loops.extend(_finalize_path_loop(current, start_point, tol))
    logger.info("Outline loops ordered: %s", len(loops))
    return loops


def _finalize_path_loop(path, start_point, tol: float):
    if not path:
        return []
    if start_point is None:
        start_point = path[0]
    if _points_close(path[-1], start_point, tol):
        if path[-1] != path[0]:
            path.append(path[0])
        if len(path) >= 4:
            return [LineString(path)]
    return []


def _points_close(p1, p2, tol: float) -> bool:
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    dist = (dx * dx + dy * dy) ** 0.5
    if tol <= 0:
        return dist == 0
    return dist <= tol


def _build_closed_loops(segments, tol: float):
    _log_endpoint_gaps(segments, tol)
    edges = []
    adjacency = {}
    nodes = []
    def _node_for(point):
        return _cluster_point(nodes, point, tol)

    for line in segments:
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        start_node = _node_for(coords[0])
        end_node = _node_for(coords[-1])
        edge = {
            "coords": coords,
            "start": start_node,
            "end": end_node,
            "used": False,
        }
        idx = len(edges)
        edges.append(edge)
        adjacency.setdefault(start_node, []).append(idx)
        adjacency.setdefault(end_node, []).append(idx)
    loops = []
    for idx, edge in enumerate(edges):
        if edge["used"]:
            continue
        start = edge["start"]
        path = []
        edge["used"] = True
        path = list(edge["coords"])
        current = edge["end"]
        prev_dir = _edge_dir(edge, start, nodes)
        steps = 0
        while True:
            if current == start:
                break
            next_idx = _pick_next_edge(edges, adjacency, current, prev_dir, nodes)
            if next_idx is None:
                path = []
                break
            next_edge = edges[next_idx]
            next_edge["used"] = True
            if current == next_edge["start"]:
                coords = next_edge["coords"]
                current = next_edge["end"]
                prev_dir = _edge_dir(next_edge, next_edge["start"], nodes)
            else:
                coords = list(reversed(next_edge["coords"]))
                current = next_edge["start"]
                prev_dir = _edge_dir(next_edge, next_edge["end"], nodes)
            path.extend(coords[1:])
            steps += 1
            if steps > len(edges):
                path = []
                break
        if path:
            if path[0] != path[-1]:
                path.append(path[0])
            if len(path) >= 4:
                loops.append(LineString(path))
    logger.info("Outline loops built: %s", len(loops))
    return loops


def _cluster_point(nodes, point, tol: float):
    px, py = float(point[0]), float(point[1])
    if tol <= 0:
        nodes.append((px, py))
        return len(nodes) - 1
    best = None
    for idx, (nx, ny) in enumerate(nodes):
        dx = px - nx
        dy = py - ny
        if (dx * dx + dy * dy) ** 0.5 <= tol:
            best = idx
            break
    if best is None:
        nodes.append((px, py))
        return len(nodes) - 1
    # Update node position by averaging to stabilize clustering.
    nx, ny = nodes[best]
    nodes[best] = ((nx + px) / 2.0, (ny + py) / 2.0)
    return best


def _edge_dir(edge, node_idx, nodes):
    coords = edge["coords"]
    if len(coords) < 2:
        return (0.0, 0.0)
    if node_idx == edge["start"]:
        p1 = coords[0]
        p2 = coords[1]
    else:
        p1 = coords[-1]
        p2 = coords[-2]
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    length = (dx * dx + dy * dy) ** 0.5
    if length == 0:
        return (0.0, 0.0)
    return (dx / length, dy / length)


def _pick_next_edge(edges, adjacency, node_idx, prev_dir, nodes):
    candidates = []
    for candidate in adjacency.get(node_idx, []):
        if edges[candidate]["used"]:
            continue
        edge = edges[candidate]
        if node_idx == edge["start"]:
            direction = _edge_dir(edge, edge["start"], nodes)
        else:
            direction = _edge_dir(edge, edge["end"], nodes)
        candidates.append((candidate, direction))
    if not candidates:
        return None
    if prev_dir == (0.0, 0.0):
        return candidates[0][0]
    best = None
    best_angle = None
    for idx, direction in candidates:
        dot = prev_dir[0] * direction[0] + prev_dir[1] * direction[1]
        angle = 1.0 - dot
        if best is None or angle < best_angle:
            best = idx
            best_angle = angle
    return best


def _log_endpoint_gaps(segments, tol: float) -> None:
    endpoints = []
    for line in segments:
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        endpoints.append(coords[0])
        endpoints.append(coords[-1])
    if not endpoints:
        return
    gaps = []
    for i, point in enumerate(endpoints):
        min_dist = None
        for j, other in enumerate(endpoints):
            if i == j:
                continue
            dx = point[0] - other[0]
            dy = point[1] - other[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if min_dist is None or dist < min_dist:
                min_dist = dist
        if min_dist is not None:
            gaps.append(min_dist)
    if not gaps:
        return
    gaps.sort()
    count = len(gaps)
    avg = sum(gaps) / count
    p50 = gaps[int(count * 0.5)]
    p90 = gaps[int(count * 0.9)]
    max_gap = gaps[-1]
    logger.info(
        "Outline endpoint gaps: count=%s avg=%.6f p50=%.6f p90=%.6f max=%.6f snap_tol=%.6f",
        count,
        avg,
        p50,
        p90,
        max_gap,
        tol,
    )
    max_info = _find_max_gap_pair(segments)
    if max_info is not None:
        (p1, p2, dist) = max_info
        logger.info(
            "Outline max gap pair: dist=%.6f p1=(%.6f, %.6f) p2=(%.6f, %.6f)",
            dist,
            p1[0],
            p1[1],
            p2[0],
            p2[1],
        )


def _find_max_gap_pair(segments):
    endpoints = []
    for line in segments:
        coords = list(line.coords)
        if len(coords) < 2:
            continue
        endpoints.append(coords[0])
        endpoints.append(coords[-1])
    if len(endpoints) < 2:
        return None
    max_dist = -1.0
    max_pair = None
    for i, p1 in enumerate(endpoints):
        min_dist = None
        min_point = None
        for j, p2 in enumerate(endpoints):
            if i == j:
                continue
            dx = p1[0] - p2[0]
            dy = p1[1] - p2[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if min_dist is None or dist < min_dist:
                min_dist = dist
                min_point = p2
        if min_dist is not None and min_dist > max_dist:
            max_dist = min_dist
            max_pair = (p1, min_point, min_dist)
    return max_pair


def _loops_to_polygons(loops):
    polygons = []
    for loop in loops:
        coords = list(loop.coords)
        if len(coords) < 4:
            continue
        poly = Polygon(coords)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if not poly.is_empty and poly.area > 0:
            polygons.append(poly)
    return polygons


def _outline_evenodd(polygons):
    cleaned = []
    for poly in polygons:
        if poly is None or poly.is_empty:
            continue
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        cleaned.append(poly)
    if not cleaned:
        return None
    cleaned.sort(key=lambda p: p.area, reverse=True)
    parents = [-1] * len(cleaned)
    for i, poly in enumerate(cleaned):
        point = poly.representative_point()
        for j in range(i):
            if cleaned[j].contains(point):
                parents[i] = j
                break
    depths = [0] * len(cleaned)
    for i in range(len(cleaned)):
        depth = 0
        parent = parents[i]
        while parent != -1:
            depth += 1
            parent = parents[parent]
        depths[i] = depth
    even_polys = [poly for poly, depth in zip(cleaned, depths) if depth % 2 == 0]
    odd_polys = [poly for poly, depth in zip(cleaned, depths) if depth % 2 == 1]
    result = unary_union(even_polys) if even_polys else None
    if result is None:
        return None
    if odd_polys:
        result = result.difference(unary_union(odd_polys))
    return result


def _maybe_snap_polygonize(merged, polygons, config: StencilConfig):
    best_snapped = None
    best_tol = None
    def _is_good(poly_list) -> bool:
        try:
            bounds = merged.bounds
            bbox_area = max((bounds[2] - bounds[0]) * (bounds[3] - bounds[1]), 0.0)
            max_area = max((poly.area for poly in poly_list), default=0.0)
            return bbox_area > 0 and max_area >= bbox_area * 0.2
        except Exception:
            return False

    if polygons and _is_good(polygons):
        return polygons, None, None

    if config.outline_snap_mm <= 0:
        return polygons, None, None

    tolerances = []
    base = config.outline_snap_mm
    for factor in (1.0, 2.0, 5.0):
        tol = base * factor
        if tol > 0:
            tolerances.append(tol)

    for tol in tolerances:
        try:
            snapped = snap(merged, merged, tol)
        except Exception:
            continue
        snapped_polys = list(polygonize(snapped))
        if snapped_polys and _is_good(snapped_polys):
            logger.info("Outline snap polygonize: tol=%s polygons=%s", tol, len(snapped_polys))
            return snapped_polys, snapped, tol
        if snapped_polys:
            logger.info("Outline snap polygonize (small): tol=%s polygons=%s", tol, len(snapped_polys))
            polygons = snapped_polys
            best_snapped = snapped
            best_tol = tol

    return polygons, best_snapped, best_tol
