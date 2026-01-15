from __future__ import annotations

"""板框解析：从 Gerber 线段/圆弧构建闭合轮廓并填充。"""

import math
import logging

from gerber import primitives as gprim
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.strtree import STRtree
from shapely.ops import unary_union

from ..config import StencilConfig
from .primitives import PrimitiveGeometryBuilder

logger = logging.getLogger(__name__)


class OutlineBuilder:
    def __init__(self, config: StencilConfig) -> None:
        self._config = config
        self._primitive_builder = PrimitiveGeometryBuilder(config)
        self._close_tol_mm = 0.02
        self._merge_tol_mm = config.outline_merge_tol_mm

    def build(self, primitives, units: str | None = None):
        return self._outline_from_primitives(primitives, units)

    def _outline_from_primitives(self, primitives, units: str | None = None):
        # 优先使用 Region；否则用线段集合闭合为轮廓
        for prim in primitives:
            if isinstance(prim, gprim.Region):
                geom = self._primitive_builder._region_to_shape(prim)
                if geom is not None and not geom.is_empty:
                    logger.info("Outline source: region")
                    return geom
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
