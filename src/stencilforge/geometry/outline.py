from __future__ import annotations

"""板框解析：从 Gerber 线段/圆弧构建闭合轮廓并填充。"""

import argparse
import math
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from gerber import primitives as gprim
from gerber import load_layer
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.strtree import STRtree
from shapely.ops import linemerge, polygonize, unary_union

from ..config import StencilConfig
from .primitives import PrimitiveGeometryBuilder

logger = logging.getLogger(__name__)


Point2D = tuple[float, float]
Segment2D = tuple[Point2D, Point2D]


@dataclass(frozen=True)
class RobustOutlineConfig:
    eps_mm: float = 0.001
    arc_max_chord_error_mm: float = 0.01
    use_buffer_fallback: bool = True
    buffer_scale: float = 2.0
    min_seg_len_scale: float = 0.5
    try_fix_invalid: bool = True
    collect_debug_data: bool = False
    max_debug_segments: int = 20000
    max_debug_offset_vectors: int = 800
    max_debug_gap_markers: int = 60
    gap_bridge_mm: float = 0.05
    gap_bridge_max_links: int = 200


class RobustOutlineExtractor:
    def __init__(self, cfg: RobustOutlineConfig, primitive_builder: PrimitiveGeometryBuilder) -> None:
        self.cfg = cfg
        self._primitive_builder = primitive_builder
        self.debug: Dict[str, Any] = {}

    def extract(self, primitives) -> Polygon:
        segments = self._primitives_to_segments(primitives)
        self.debug["eps_mm"] = self.cfg.eps_mm
        self.debug["arc_max_chord_error_mm"] = self.cfg.arc_max_chord_error_mm
        self.debug["raw_segments_count"] = len(segments)
        if self.cfg.collect_debug_data:
            self.debug["raw_segments"] = self._limit_segments(segments)
            self.debug["bbox"] = self._segments_bbox(segments)
        segments = self._snap_segments(segments)
        self.debug["snapped_segments_count"] = len(segments)
        if self.cfg.collect_debug_data:
            self.debug["snapped_segments"] = self._limit_segments(segments)
        segments = self._filter_and_dedupe_segments(segments)
        self.debug["deduped_segments_count"] = len(segments)
        if self.cfg.collect_debug_data:
            self.debug["deduped_segments"] = self._limit_segments(segments)
            self.debug["offset_vectors"] = self._build_offset_vectors(
                self.debug.get("raw_segments", []),
            )
            self.debug["gap_markers"] = self._build_gap_markers(segments)
        if self.cfg.gap_bridge_mm > 0:
            segments, bridged = self._bridge_gaps(segments)
            if bridged:
                self.debug["bridged_segments_count"] = len(bridged)
                if self.cfg.collect_debug_data:
                    self.debug["bridged_segments"] = self._limit_segments(bridged)
        if not segments:
            raise ValueError(self._format_error("no segments after filtering"))
        polygons = []
        poly_stats: Dict[str, Any] = {}
        poly_exc: Exception | None = None
        try:
            polygons, poly_stats = self._polygonize_segments(segments)
        except Exception as exc:
            poly_exc = exc
        used_fallback = False
        if not polygons and self.cfg.use_buffer_fallback:
            try:
                polygons = self._fallback_buffer_polygon(segments)
                used_fallback = True
            except Exception as exc:
                poly_exc = exc
        if poly_stats:
            self.debug.update(poly_stats)
        if not polygons:
            extra = f" polygonize_error={poly_exc}" if poly_exc else ""
            if poly_stats:
                extra += f" polygonize_stats={poly_stats}"
            raise ValueError(self._format_error("polygonize produced no polygons") + extra)
        poly = self._choose_largest_polygon(polygons)
        if poly is None or poly.is_empty:
            raise ValueError(self._format_error("empty polygon result"))
        if self.cfg.try_fix_invalid and not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty or poly.area <= 0:
            raise ValueError(self._format_error("invalid polygon area"))
        self.debug["polygon_count"] = len(polygons)
        self.debug["chosen_area"] = float(poly.area)
        self.debug["used_fallback"] = used_fallback
        if self.cfg.collect_debug_data:
            self.debug["chosen_polygon_coords"] = self._polygon_coords(poly)
        return poly

    def _primitives_to_segments(self, primitives) -> list[Segment2D]:
        segments: list[Segment2D] = []
        for prim in primitives:
            if isinstance(prim, gprim.Line):
                segments.append((prim.start, prim.end))
            elif isinstance(prim, gprim.Arc):
                points = self._discretize_arc(prim)
                for i in range(len(points) - 1):
                    segments.append((points[i], points[i + 1]))
            elif isinstance(prim, gprim.Region):
                geom = self._primitive_builder._region_to_shape(prim)
                segments.extend(self._segments_from_shape(geom))
        return segments

    def _segments_from_shape(self, geom) -> list[Segment2D]:
        if geom is None or geom.is_empty:
            return []
        segments: list[Segment2D] = []
        if geom.geom_type == "Polygon":
            segments.extend(self._segments_from_ring(list(geom.exterior.coords)))
        elif geom.geom_type == "MultiPolygon":
            for poly in geom.geoms:
                segments.extend(self._segments_from_ring(list(poly.exterior.coords)))
        return segments

    @staticmethod
    def _segments_from_ring(coords: list[Point2D]) -> list[Segment2D]:
        if len(coords) < 2:
            return []
        return [(coords[i], coords[i + 1]) for i in range(len(coords) - 1)]

    def _discretize_arc(self, arc: gprim.Arc) -> list[Point2D]:
        if arc.center is None or arc.radius is None:
            raise ValueError("R-arc not supported: missing arc center or radius")
        radius = float(arc.radius)
        if radius <= 0:
            raise ValueError("Arc radius must be > 0")
        start = float(arc.start_angle)
        end = float(arc.end_angle)
        if arc.direction == "counterclockwise":
            if end <= start:
                end += 2 * math.pi
            sweep = end - start
        else:
            if end >= start:
                end -= 2 * math.pi
            sweep = start - end
        chord_err = float(self.cfg.arc_max_chord_error_mm)
        max_angle = 2 * math.acos(max(0.0, 1.0 - chord_err / radius))
        if max_angle <= 0 or math.isnan(max_angle):
            max_angle = sweep
        steps = max(2, int(math.ceil(sweep / max_angle)) + 1)
        angles = [start + sweep * i / (steps - 1) for i in range(steps)]
        if arc.direction != "counterclockwise":
            angles = [start - sweep * i / (steps - 1) for i in range(steps)]
        cx, cy = arc.center
        return [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]

    def _snap_point(self, point: Point2D) -> Point2D:
        eps = self.cfg.eps_mm
        return (round(point[0] / eps) * eps, round(point[1] / eps) * eps)

    def _snap_segments(self, segments: list[Segment2D]) -> list[Segment2D]:
        return [(self._snap_point(p1), self._snap_point(p2)) for p1, p2 in segments]

    def _filter_and_dedupe_segments(self, segments: list[Segment2D]) -> list[Segment2D]:
        min_len = self.cfg.eps_mm * self.cfg.min_seg_len_scale
        deduped: list[Segment2D] = []
        seen: set[tuple[Point2D, Point2D]] = set()
        for p1, p2 in segments:
            if self._segment_length(p1, p2) < min_len:
                continue
            key = (p1, p2) if p1 <= p2 else (p2, p1)
            if key in seen:
                continue
            seen.add(key)
            deduped.append((p1, p2))
        return deduped

    @staticmethod
    def _segment_length(p1: Point2D, p2: Point2D) -> float:
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        return (dx * dx + dy * dy) ** 0.5

    def _limit_segments(self, segments: list[Segment2D]) -> list[Segment2D]:
        limit = self.cfg.max_debug_segments
        if limit <= 0 or len(segments) <= limit:
            return list(segments)
        stride = max(1, int(math.ceil(len(segments) / limit)))
        return [segments[idx] for idx in range(0, len(segments), stride)][:limit]

    def _segments_bbox(self, segments: list[Segment2D]) -> tuple[float, float, float, float] | None:
        if not segments:
            return None
        xs = []
        ys = []
        for p1, p2 in segments:
            xs.extend((p1[0], p2[0]))
            ys.extend((p1[1], p2[1]))
        return (min(xs), min(ys), max(xs), max(ys))

    def _build_offset_vectors(self, raw_segments: list[Segment2D]) -> list[tuple[Point2D, Point2D, float]]:
        offsets: dict[Point2D, tuple[Point2D, float]] = {}
        for p1, p2 in raw_segments:
            for point in (p1, p2):
                snapped = self._snap_point(point)
                dist = self._segment_length(point, snapped)
                current = offsets.get(point)
                if current is None or dist > current[1]:
                    offsets[point] = (snapped, dist)
        vectors = [(raw, snapped, dist) for raw, (snapped, dist) in offsets.items()]
        vectors.sort(key=lambda item: item[2], reverse=True)
        limit = self.cfg.max_debug_offset_vectors
        if limit >= 0:
            vectors = vectors[:limit]
        return vectors

    @staticmethod
    def _polygon_coords(poly: Polygon) -> list[Point2D]:
        coords = list(poly.exterior.coords)
        if len(coords) > 1 and coords[0] == coords[-1]:
            coords = coords[:-1]
        return coords

    def _build_gap_markers(self, segments: list[Segment2D]) -> list[tuple[Point2D, Point2D, float]]:
        endpoints: list[Point2D] = []
        for p1, p2 in segments:
            endpoints.append(p1)
            endpoints.append(p2)
        if len(endpoints) < 2:
            return []
        gaps = []
        for i, p1 in enumerate(endpoints):
            min_dist = None
            closest = None
            for j, p2 in enumerate(endpoints):
                if i == j:
                    continue
                dist = self._segment_length(p1, p2)
                if min_dist is None or dist < min_dist:
                    min_dist = dist
                    closest = p2
            if min_dist is not None and closest is not None:
                gaps.append((p1, closest, min_dist))
        gaps.sort(key=lambda item: item[2], reverse=True)
        limit = self.cfg.max_debug_gap_markers
        if limit >= 0:
            gaps = gaps[:limit]
        return gaps

    def _bridge_gaps(self, segments: list[Segment2D]) -> tuple[list[Segment2D], list[Segment2D]]:
        if not segments:
            return segments, []
        endpoints: list[Point2D] = []
        for p1, p2 in segments:
            endpoints.append(p1)
            endpoints.append(p2)
        if len(endpoints) < 2:
            return segments, []
        nearest: list[tuple[int, float]] = []
        for i, p1 in enumerate(endpoints):
            best_idx = -1
            best_dist = None
            for j, p2 in enumerate(endpoints):
                if i == j:
                    continue
                dist = self._segment_length(p1, p2)
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best_idx = j
            if best_idx >= 0 and best_dist is not None:
                nearest.append((best_idx, best_dist))
            else:
                nearest.append((-1, 0.0))
        bridged = []
        used = set()
        max_links = self.cfg.gap_bridge_max_links
        for i, (j, dist) in enumerate(nearest):
            if j < 0 or i in used or j in used:
                continue
            if dist > self.cfg.gap_bridge_mm:
                continue
            back_idx, back_dist = nearest[j]
            if back_idx != i:
                continue
            if back_dist > self.cfg.gap_bridge_mm:
                continue
            p1 = endpoints[i]
            p2 = endpoints[j]
            key = (p1, p2) if p1 <= p2 else (p2, p1)
            if key in used:
                continue
            bridged.append((p1, p2))
            used.add(i)
            used.add(j)
            if max_links >= 0 and len(bridged) >= max_links:
                break
        if not bridged:
            return segments, []
        return segments + bridged, bridged

    def _polygonize_segments(self, segments: list[Segment2D]) -> tuple[list[Polygon], Dict[str, Any]]:
        lines = [LineString([p1, p2]) for p1, p2 in segments]
        if not lines:
            return [], {"polygonize_union_type": None, "polygonize_merged_type": None}
        unioned = unary_union(lines)
        merged = linemerge(unioned)
        polygons = [poly for poly in polygonize(merged)]
        stats = {
            "polygonize_union_type": getattr(unioned, "geom_type", None),
            "polygonize_merged_type": getattr(merged, "geom_type", None),
            "polygonize_count": len(polygons),
        }
        return polygons, stats

    @staticmethod
    def _choose_largest_polygon(polygons: list[Polygon]) -> Polygon | None:
        if not polygons:
            return None
        return max(polygons, key=lambda p: p.area)

    def _fallback_buffer_polygon(self, segments: list[Segment2D]) -> list[Polygon]:
        lines = [LineString([p1, p2]) for p1, p2 in segments]
        if not lines:
            return []
        unioned = unary_union(lines)
        buffered = unioned.buffer(self.cfg.eps_mm * self.cfg.buffer_scale)
        if buffered.is_empty:
            return []
        if buffered.geom_type == "Polygon":
            return [buffered]
        if buffered.geom_type == "MultiPolygon":
            return list(buffered.geoms)
        return []

    def _format_error(self, reason: str) -> str:
        return (
            f"robust outline failed: {reason}; eps_mm={self.cfg.eps_mm} "
            f"arc_err={self.cfg.arc_max_chord_error_mm} raw={self.debug.get('raw_segments_count')} "
            f"deduped={self.debug.get('deduped_segments_count')} fallback={self.cfg.use_buffer_fallback}"
        )


class OutlineBuilder:
    def __init__(self, config: StencilConfig) -> None:
        self._config = config
        self._primitive_builder = PrimitiveGeometryBuilder(config)
        self._close_tol_mm = 0.02
        self._merge_tol_mm = config.outline_merge_tol_mm
        self._last_robust_debug: Dict[str, Any] | None = None

    def build(self, primitives, units: str | None = None):
        self._last_robust_debug = None
        return self._outline_from_primitives(primitives, units)

    def _outline_from_primitives(self, primitives, units: str | None = None):
        # 优先使用 Region；否则用线段集合闭合为轮廓
        for prim in primitives:
            if isinstance(prim, gprim.Region):
                geom = self._primitive_builder._region_to_shape(prim)
                if geom is not None and not geom.is_empty:
                    logger.info("Outline source: region")
                    return geom
        if self._config.outline_close_strategy == "robust_polygonize":
            eps = self._tol_in_units(self._config.outline_snap_eps_mm, units)
            arc_err = self._tol_in_units(self._config.outline_arc_max_chord_error_mm, units)
            cfg = RobustOutlineConfig(
                eps_mm=eps,
                arc_max_chord_error_mm=arc_err,
                collect_debug_data=self._config.ui_debug_plot_outline,
                max_debug_segments=self._config.ui_debug_plot_max_segments,
                max_debug_offset_vectors=self._config.ui_debug_plot_max_offset_vectors,
                max_debug_gap_markers=self._config.ui_debug_plot_max_offset_vectors,
                gap_bridge_mm=self._config.outline_gap_bridge_mm,
            )
            extractor = RobustOutlineExtractor(cfg, self._primitive_builder)
            try:
                poly = extractor.extract(primitives)
                self._last_robust_debug = self._finalize_debug(extractor.debug, units)
                return poly
            except Exception as exc:
                logger.warning("Robust outline failed, falling back to legacy: %s", exc)
        segments = self._outline_segments_from_primitives(primitives)
        if segments:
            # 先尝试按路径顺序闭合，再退回基于图的闭合
            logger.info("Outline segments: %s", len(segments))
            merge_tol = self._tol_in_units(self._merge_tol_mm, units)
            close_tol = self._tol_in_units(self._close_tol_mm, units)
            if merge_tol > 0:
                segments = self._merge_near_colinear_segments(segments, merge_tol)
            merged = unary_union(segments)
            segments = self._merge_outline_segments(segments, merged)
            loops = self._build_loops_in_order(segments, close_tol)
            if not loops:
                loops = self._build_closed_loops(segments, close_tol)
            if loops:
                polygons = self._loops_to_polygons(loops)
            else:
                polygons = []
            if polygons:
                logger.info("Outline loops: polygons=%s", len(polygons))
                if self._config.outline_fill_rule == "legacy":
                    # 旧逻辑：取最大面积多边形作为板框
                    poly = max(polygons, key=lambda p: p.area)
                    if not poly.is_valid:
                        poly = poly.buffer(0)
                    return poly
                filled = self._outline_evenodd(polygons)
                if filled is not None and not filled.is_empty:
                    # 奇偶规则填充：适用于套娃轮廓
                    logger.info("Outline fill rule: evenodd")
                    return filled
        logger.info("Outline fallback: primitives_to_geometry")
        return self._primitive_builder._primitives_to_geometry(primitives)

    def get_last_robust_debug(self) -> Dict[str, Any] | None:
        return self._last_robust_debug

    def _finalize_debug(self, debug: Dict[str, Any], units: str | None) -> Dict[str, Any]:
        debug = dict(debug)
        debug["eps_mm"] = float(self._config.outline_snap_eps_mm)
        debug["arc_max_chord_error_mm"] = float(self._config.outline_arc_max_chord_error_mm)
        if units == "inch":
            debug = self._scale_debug_to_mm(debug)
        return debug

    def _scale_debug_to_mm(self, debug: Dict[str, Any]) -> Dict[str, Any]:
        scale = 25.4

        def scale_point(point: Point2D) -> Point2D:
            return (point[0] * scale, point[1] * scale)

        def scale_segment(segment: Segment2D) -> Segment2D:
            return (scale_point(segment[0]), scale_point(segment[1]))

        def scale_segments(segments: list[Segment2D]) -> list[Segment2D]:
            return [scale_segment(seg) for seg in segments]

        if "raw_segments" in debug:
            debug["raw_segments"] = scale_segments(debug["raw_segments"])
        if "snapped_segments" in debug:
            debug["snapped_segments"] = scale_segments(debug["snapped_segments"])
        if "deduped_segments" in debug:
            debug["deduped_segments"] = scale_segments(debug["deduped_segments"])
        if "chosen_polygon_coords" in debug:
            debug["chosen_polygon_coords"] = [scale_point(p) for p in debug["chosen_polygon_coords"]]
        if "bbox" in debug and debug["bbox"] is not None:
            min_x, min_y, max_x, max_y = debug["bbox"]
            debug["bbox"] = (min_x * scale, min_y * scale, max_x * scale, max_y * scale)
        if "offset_vectors" in debug:
            scaled = []
            for raw, snapped, dist in debug["offset_vectors"]:
                scaled.append((scale_point(raw), scale_point(snapped), dist * scale))
            debug["offset_vectors"] = scaled
        return debug

    def _outline_segments_from_primitives(self, primitives):
        # 仅从线段/圆弧提取轮廓线
        segments = []
        for prim in primitives:
            if isinstance(prim, gprim.Line):
                segments.append(LineString([prim.start, prim.end]))
            elif isinstance(prim, gprim.Arc):
                arc_pts = _arc_points(prim, self._config.arc_steps)
                if len(arc_pts) >= 2:
                    segments.append(LineString(arc_pts))
        return segments

    def _merge_near_colinear_segments(self, segments, tol: float):
        # 合并近似共线且重叠/相接的冗余线段，避免闭合受干扰
        if tol <= 0 or len(segments) < 2:
            return segments
        lines = [line for line in segments if line is not None and not line.is_empty and len(line.coords) >= 2]
        if len(lines) < 2:
            return lines
        removed = set()
        merged_count = 0
        angle_cos = math.cos(math.radians(1.0))
        changed = True
        while changed:
            changed = False
            active = [line for idx, line in enumerate(lines) if idx not in removed]
            if len(active) < 2:
                break
            tree = STRtree(active)
            geom_to_idx = {id(line): idx for idx, line in enumerate(lines) if idx not in removed}
            for idx, line in enumerate(lines):
                if idx in removed:
                    continue
                corridor = line.buffer(tol, cap_style=2, join_style=2)
                for candidate in tree.query(corridor):
                    cand_idx = geom_to_idx.get(id(candidate))
                    if cand_idx is None or cand_idx == idx or cand_idx in removed:
                        continue
                    merged = self._try_merge_lines(line, lines[cand_idx], tol, angle_cos)
                    if merged is None:
                        continue
                    lines[idx] = merged
                    removed.add(cand_idx)
                    merged_count += 1
                    changed = True
                    break
                if changed:
                    break
        merged_lines = [line for idx, line in enumerate(lines) if idx not in removed]
        if merged_count:
            logger.info("Outline segments merged near-colinear: %s -> %s", len(segments), len(merged_lines))
        return merged_lines

    def _tol_in_units(self, tol_mm: float, units: str | None) -> float:
        if tol_mm <= 0:
            return 0.0
        if units == "inch":
            return tol_mm / 25.4
        return tol_mm

    def _try_merge_lines(self, line_a: LineString, line_b: LineString, tol: float, angle_cos: float):
        if line_a is None or line_b is None:
            return None
        coords_a = list(line_a.coords)
        coords_b = list(line_b.coords)
        if len(coords_a) < 2 or len(coords_b) < 2:
            return None
        ax0, ay0 = coords_a[0]
        ax1, ay1 = coords_a[-1]
        bx0, by0 = coords_b[0]
        bx1, by1 = coords_b[-1]
        dax = ax1 - ax0
        day = ay1 - ay0
        dbx = bx1 - bx0
        dby = by1 - by0
        len_a = (dax * dax + day * day) ** 0.5
        len_b = (dbx * dbx + dby * dby) ** 0.5
        if len_a == 0 or len_b == 0:
            return None
        dir_a = (dax / len_a, day / len_a)
        dir_b = (dbx / len_b, dby / len_b)
        dot = abs(dir_a[0] * dir_b[0] + dir_a[1] * dir_b[1])
        if dot < angle_cos:
            return None
        if line_a.distance(Point(coords_b[0])) > tol or line_a.distance(Point(coords_b[-1])) > tol:
            return None

        def proj(point) -> float:
            return (point[0] - ax0) * dir_a[0] + (point[1] - ay0) * dir_a[1]

        t_a0 = proj(coords_a[0])
        t_a1 = proj(coords_a[-1])
        t_b0 = proj(coords_b[0])
        t_b1 = proj(coords_b[-1])
        a_min = min(t_a0, t_a1)
        a_max = max(t_a0, t_a1)
        b_min = min(t_b0, t_b1)
        b_max = max(t_b0, t_b1)
        if a_max < b_min:
            gap = b_min - a_max
        elif b_max < a_min:
            gap = a_min - b_max
        else:
            gap = 0.0
        if gap > tol:
            return None
        t_min = min(a_min, b_min)
        t_max = max(a_max, b_max)
        start = (ax0 + dir_a[0] * t_min, ay0 + dir_a[1] * t_min)
        end = (ax0 + dir_a[0] * t_max, ay0 + dir_a[1] * t_max)
        if self._points_close(start, end, tol):
            return None
        return LineString([start, end])

    def _merge_outline_segments(self, segments, merged):
        # 合并重叠/共线线段，减少重复以利于闭合。
        if merged is None:
            return segments
        merged_segments = []

        def _collect_lines(geom):
            if geom is None or geom.is_empty:
                return
            if isinstance(geom, LineString):
                if len(geom.coords) >= 2:
                    merged_segments.append(geom)
                return
            if isinstance(geom, MultiLineString):
                for line in geom.geoms:
                    _collect_lines(line)
                return
            for child in getattr(geom, "geoms", []):
                _collect_lines(child)

        _collect_lines(merged)
        if merged_segments:
            logger.info("Outline segments merged: %s -> %s", len(segments), len(merged_segments))
            return merged_segments
        return segments

    def _build_loops_in_order(self, segments, tol: float):
        # 按原始顺序拼接，若端点接近则延续
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
            if self._points_close(last, coords[0], tol):
                current.extend(coords[1:])
            elif self._points_close(last, coords[-1], tol):
                current.extend(list(reversed(coords))[:-1])
            else:
                loops.extend(self._finalize_path_loop(current, start_point, tol))
                current = coords[:]
                start_point = current[0]
        if current:
            loops.extend(self._finalize_path_loop(current, start_point, tol))
        logger.info("Outline loops ordered: %s", len(loops))
        return loops

    def _finalize_path_loop(self, path, start_point, tol: float):
        if not path:
            return []
        if start_point is None:
            start_point = path[0]
        if self._points_close(path[-1], start_point, tol):
            if path[-1] != path[0]:
                path.append(path[0])
            if len(path) >= 4:
                return [LineString(path)]
        return []

    def _build_closed_loops(self, segments, tol: float):
        # 构建端点邻接图，尝试遍历成闭合环
        edges = []
        adjacency = {}
        nodes = []

        def _node_for(point):
            return self._cluster_point(nodes, point, tol)

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
        for edge in edges:
            if edge["used"]:
                continue
            start = edge["start"]
            edge["used"] = True
            path = list(edge["coords"])
            current = edge["end"]
            prev_dir = self._edge_dir(edge, start)
            steps = 0
            while True:
                if current == start:
                    break
                next_idx = self._pick_next_edge(edges, adjacency, current, prev_dir)
                if next_idx is None:
                    path = []
                    break
                next_edge = edges[next_idx]
                next_edge["used"] = True
                if current == next_edge["start"]:
                    coords = next_edge["coords"]
                    current = next_edge["end"]
                    prev_dir = self._edge_dir(next_edge, next_edge["start"])
                else:
                    coords = list(reversed(next_edge["coords"]))
                    current = next_edge["start"]
                    prev_dir = self._edge_dir(next_edge, next_edge["end"])
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

    def _cluster_point(self, nodes, point, tol: float):
        # 端点吸附：将近邻点聚成同一节点
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
        nx, ny = nodes[best]
        nodes[best] = ((nx + px) / 2.0, (ny + py) / 2.0)
        return best

    def _edge_dir(self, edge, node_idx):
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

    def _pick_next_edge(self, edges, adjacency, node_idx, prev_dir):
        # 选择与当前方向夹角最小的边，减少交叉
        candidates = []
        for candidate in adjacency.get(node_idx, []):
            if edges[candidate]["used"]:
                continue
            edge = edges[candidate]
            if node_idx == edge["start"]:
                direction = self._edge_dir(edge, edge["start"])
            else:
                direction = self._edge_dir(edge, edge["end"])
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

    def _points_close(self, p1, p2, tol: float) -> bool:
        dx = p1[0] - p2[0]
        dy = p1[1] - p2[1]
        dist = (dx * dx + dy * dy) ** 0.5
        if tol <= 0:
            return dist == 0
        return dist <= tol


    def _loops_to_polygons(self, loops):
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

    def _outline_evenodd(self, polygons):
        # 使用包含层级的奇偶规则填充多边形
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


def _arc_points(arc: gprim.Arc, steps: int):
    # 与 primitives 中类似的圆弧采样
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


def _cli() -> int:
    parser = argparse.ArgumentParser(description="Outline extraction quick check")
    parser.add_argument("--input", required=True, help="Outline Gerber file path")
    parser.add_argument("--strategy", default="legacy", help="outline close strategy")
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        raise SystemExit(f"input not found: {path}")

    config = StencilConfig.from_dict({"outline_close_strategy": args.strategy})
    layer = load_layer(str(path))
    units = layer.cam_source.units
    builder = OutlineBuilder(config)

    if args.strategy == "robust_polygonize":
        eps = builder._tol_in_units(config.outline_snap_eps_mm, units)
        arc_err = builder._tol_in_units(config.outline_arc_max_chord_error_mm, units)
        cfg = RobustOutlineConfig(eps_mm=eps, arc_max_chord_error_mm=arc_err)
        extractor = RobustOutlineExtractor(cfg, builder._primitive_builder)
        geom = extractor.extract(layer.primitives)
        used_fallback = extractor.debug.get("used_fallback")
    else:
        geom = builder.build(layer.primitives, units)
        used_fallback = None

    if units == "inch":
        geom = affinity.scale(geom, xfact=25.4, yfact=25.4, origin=(0, 0))

    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    point_count = None
    if geom.geom_type == "Polygon":
        point_count = len(geom.exterior.coords)
    elif geom.geom_type == "MultiPolygon" and geom.geoms:
        poly = max(geom.geoms, key=lambda p: p.area)
        point_count = len(poly.exterior.coords)

    print(f"bbox: {bounds}")
    print(f"width: {width}")
    print(f"height: {height}")
    print(f"area: {geom.area}")
    print(f"point_count: {point_count}")
    print(f"is_valid: {geom.is_valid}")
    if used_fallback is not None:
        print(f"used_fallback: {used_fallback}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
