from __future__ import annotations

"""2D -> 3D 几何处理：面片校正、孔洞处理、挤出与基本统计。"""

import logging

from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, triangulate
import trimesh

logger = logging.getLogger(__name__)


def extrude_geometry(geometry, thickness_mm: float):
    # 统一处理几何：合法性修复、方向一致化、孔洞固化
    geometry = ensure_valid(geometry)
    geometry = orient_geometry(geometry)
    geometry = solidify_geometry(geometry)
    meshes = []
    if geometry.geom_type == "Polygon":
        if geometry.area > 0:
            meshes.append(extrude_polygon_solid(geometry, thickness_mm))
    elif geometry.geom_type == "MultiPolygon":
        for poly in geometry.geoms:
            poly = ensure_valid(poly)
            if poly.area <= 0:
                continue
            meshes.append(extrude_polygon_solid(poly, thickness_mm))
    else:
        merged = unary_union([geometry])
        if merged.geom_type == "Polygon":
            merged = ensure_valid(merged)
            if merged.area > 0:
                meshes.append(extrude_polygon_solid(merged, thickness_mm))
        elif merged.geom_type == "MultiPolygon":
            for poly in merged.geoms:
                poly = ensure_valid(poly)
                if poly.area <= 0:
                    continue
                meshes.append(extrude_polygon_solid(poly, thickness_mm))
    if not meshes:
        raise ValueError("Failed to create STL mesh from geometry.")
    mesh = trimesh.util.concatenate(meshes)
    if mesh.is_empty or mesh.faces.size == 0:
        raise ValueError("Failed to create non-empty STL mesh from geometry.")
    return mesh


def ensure_valid(geometry):
    # Shapely buffer(0) 是常用的自交修复手段
    if geometry.is_valid:
        return geometry
    return geometry.buffer(0)


def orient_geometry(geometry):
    # 统一多边形方向，避免挤出法向混乱
    if geometry.is_empty:
        return geometry
    if geometry.geom_type == "Polygon":
        return orient(geometry, sign=1.0)
    if geometry.geom_type == "MultiPolygon":
        return geometry.__class__([orient(poly, sign=1.0) for poly in geometry.geoms])
    return geometry


def count_holes(geometry) -> int:
    # 统计孔洞数量，便于 debug 输出
    if geometry.is_empty:
        return 0
    if geometry.geom_type == "Polygon":
        return len(geometry.interiors)
    if geometry.geom_type == "MultiPolygon":
        return sum(len(poly.interiors) for poly in geometry.geoms)
    return 0


def count_polygons(geometry) -> int:
    # 统计 polygon 数量，便于 debug 输出
    if geometry.is_empty:
        return 0
    if geometry.geom_type == "Polygon":
        return 1
    if geometry.geom_type == "MultiPolygon":
        return len(geometry.geoms)
    return 0


def extrude_polygon_solid(poly, thickness_mm: float) -> trimesh.Trimesh:
    # 通过三角剖分生成上下表面，再补齐侧壁
    triangles = []
    kept_area = 0.0
    for tri in triangulate(poly):
        if not poly.covers(tri.representative_point()):
            continue
        triangles.append(tri)
        kept_area += tri.area
    coverage = kept_area / poly.area if poly.area > 0 else 0
    if coverage < 0.98:
        # 对复杂轮廓，尝试 buffer(0) 以恢复边界三角形
        fallback = poly.buffer(0)
        triangles = []
        kept_area = 0.0
        for tri in triangulate(fallback):
            if fallback.covers(tri.representative_point()):
                triangles.append(tri)
                kept_area += tri.area
        coverage = kept_area / fallback.area if fallback.area > 0 else 0
        if coverage < 0.98:
            logger.warning(
                "Triangulation coverage low: poly_area=%.6f kept=%.6f coverage=%.3f",
                float(fallback.area),
                float(kept_area),
                float(coverage),
            )
            try:
                return trimesh.creation.extrude_polygon(
                    fallback, thickness_mm, engine="earcut"
                )
            except Exception as exc:
                logger.warning("Earcut fallback failed: %s", exc)
    if not triangles:
        raise ValueError("Triangulation failed for polygon.")

    vertices = []
    faces = []
    vertex_index = {}

    def add_vertex(x, y, z):
        # 顶点去重，避免重复点导致的面异常
        key = (float(x), float(y), float(z))
        idx = vertex_index.get(key)
        if idx is None:
            idx = len(vertices)
            vertices.append(key)
            vertex_index[key] = idx
        return idx

    # 上下表面：同一三角形分别放到 z=0 和 z=thickness
    for tri in triangles:
        coords = list(tri.exterior.coords)[:3]
        top = [add_vertex(x, y, thickness_mm) for x, y in coords]
        bottom = [add_vertex(x, y, 0.0) for x, y in coords]
        faces.append(top)
        faces.append(bottom[::-1])

    rings = [poly.exterior]
    # 侧壁：沿外轮廓逐段生成四边形（拆成两个三角形）
    for ring in rings:
        coords = list(ring.coords)
        if len(coords) < 2:
            continue
        if coords[0] == coords[-1]:
            coords = coords[:-1]
        for i in range(len(coords)):
            x1, y1 = coords[i]
            x2, y2 = coords[(i + 1) % len(coords)]
            v1 = add_vertex(x1, y1, 0.0)
            v2 = add_vertex(x2, y2, 0.0)
            v3 = add_vertex(x2, y2, thickness_mm)
            v4 = add_vertex(x1, y1, thickness_mm)
            faces.append([v1, v2, v3])
            faces.append([v1, v3, v4])

    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def solidify_geometry(geometry):
    # 将孔洞显式差分，避免后续挤出错误
    if geometry.is_empty:
        return geometry
    if geometry.geom_type == "Polygon" and geometry.interiors:
        holes = [
            Polygon(hole.coords).buffer(0)
            for hole in geometry.interiors
            if len(hole.coords) >= 3
        ]
        if holes:
            return geometry.difference(unary_union(holes))
    if geometry.geom_type == "MultiPolygon":
        parts = []
        for poly in geometry.geoms:
            parts.append(solidify_geometry(poly))
        return unary_union([p for p in parts if p is not None and not p.is_empty])
    return geometry
