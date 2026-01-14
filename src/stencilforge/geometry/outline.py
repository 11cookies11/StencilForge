from __future__ import annotations

"""板框解析：从 Gerber 线段/圆弧构建闭合轮廓并填充。"""

import math
import logging

from gerber import primitives as gprim
from shapely.geometry import LineString, MultiLineString, Polygon
from shapely.ops import unary_union

from ..config import StencilConfig
from .primitives import PrimitiveGeometryBuilder

logger = logging.getLogger(__name__)


class OutlineBuilder:
    def __init__(self, config: StencilConfig) -> None:
        self._config = config
        self._primitive_builder = PrimitiveGeometryBuilder(config)

    def build(self, primitives):
        return self._outline_from_primitives(primitives)

    def build_segments(self, primitives):
        return self._outline_segments_from_primitives(primitives)

    def _outline_from_primitives(self, primitives):
        # 优先使用 Region；否则用线段集合闭合为轮廓
        debug = {
            "source": None,
            "segments_geom": None,
            "snapped_geom": None,
            "snap_tol": None,
            "loops_count": 0,
            "loops_geom": None,
            "max_gap_pair": None,
        }
        for prim in primitives:
            if isinstance(prim, gprim.Region):
                geom = self._primitive_builder._region_to_shape(prim)
                if geom is not None and not geom.is_empty:
                    logger.info("Outline source: region")
                    debug["source"] = "region"
                    return geom, debug
        segments = self._outline_segments_from_primitives(primitives)
        if segments:
            # 先尝试按路径顺序闭合，再退回基于图的闭合
            logger.info("Outline segments: %s", len(segments))
            merged = unary_union(segments)
            debug["source"] = "segments"
            debug["segments_geom"] = merged
            debug["max_gap_pair"] = self._find_max_gap_pair(segments)
            loops = self._build_loops_in_order(segments, self._config.outline_snap_mm)
            if not loops:
                loops = self._build_closed_loops(segments, self._config.outline_snap_mm)
            if loops:
                debug["loops_count"] = len(loops)
                debug["loops_geom"] = MultiLineString(loops) if len(loops) > 1 else loops[0]
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
                    return poly, debug
                filled = self._outline_evenodd(polygons)
                if filled is not None and not filled.is_empty:
                    # 奇偶规则填充：适用于套娃轮廓
                    logger.info("Outline fill rule: evenodd")
                    return filled, debug
        logger.info("Outline fallback: primitives_to_geometry")
        debug["source"] = "primitives"
        return self._primitive_builder._primitives_to_geometry(primitives), debug

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
        self._log_endpoint_gaps(segments, tol)
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

    def _log_endpoint_gaps(self, segments, tol: float) -> None:
        # 输出端点间距离统计，辅助判断断点问题
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
        max_info = self._find_max_gap_pair(segments)
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

    def _find_max_gap_pair(self, segments):
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
