from __future__ import annotations

"""2D to 3D geometry helpers for STL generation."""

import logging

import trimesh
from shapely import constrained_delaunay_triangles
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.ops import triangulate, unary_union

logger = logging.getLogger(__name__)


def extrude_geometry(geometry, thickness_mm: float):
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
    if geometry.is_valid:
        return geometry
    return geometry.buffer(0)


def orient_geometry(geometry):
    if geometry.is_empty:
        return geometry
    if geometry.geom_type == "Polygon":
        return orient(geometry, sign=1.0)
    if geometry.geom_type == "MultiPolygon":
        return geometry.__class__([orient(poly, sign=1.0) for poly in geometry.geoms])
    return geometry


def count_holes(geometry) -> int:
    if geometry.is_empty:
        return 0
    if geometry.geom_type == "Polygon":
        return len(geometry.interiors)
    if geometry.geom_type == "MultiPolygon":
        return sum(len(poly.interiors) for poly in geometry.geoms)
    return 0


def count_polygons(geometry) -> int:
    if geometry.is_empty:
        return 0
    if geometry.geom_type == "Polygon":
        return 1
    if geometry.geom_type == "MultiPolygon":
        return len(geometry.geoms)
    return 0


def extrude_polygon_solid(poly, thickness_mm: float) -> trimesh.Trimesh:
    triangles, coverage = _triangulate_polygon_robust(poly)
    if coverage < 0.995:
        logger.warning(
            "Triangulation coverage low: poly_area=%.6f kept=%.6f coverage=%.3f",
            float(poly.area),
            float(poly.area * coverage),
            float(coverage),
        )
        try:
            return trimesh.creation.extrude_polygon(poly, thickness_mm, engine="earcut")
        except Exception as exc:
            logger.warning("Earcut fallback failed: %s", exc)

    if not triangles:
        raise ValueError("Triangulation failed for polygon.")

    vertices = []
    faces = []
    vertex_index = {}

    def add_vertex(x, y, z):
        key = (float(x), float(y), float(z))
        idx = vertex_index.get(key)
        if idx is None:
            idx = len(vertices)
            vertices.append(key)
            vertex_index[key] = idx
        return idx

    for tri in triangles:
        coords = list(tri.exterior.coords)[:3]
        top = [add_vertex(x, y, thickness_mm) for x, y in coords]
        bottom = [add_vertex(x, y, 0.0) for x, y in coords]
        faces.append(top)
        faces.append(bottom[::-1])

    # Build side walls for outer ring and all holes to preserve cutouts.
    rings = [(poly.exterior, False)] + [(ring, True) for ring in poly.interiors]
    for ring, is_hole in rings:
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
            if is_hole:
                faces.append([v1, v3, v2])
                faces.append([v1, v4, v3])
            else:
                faces.append([v1, v2, v3])
                faces.append([v1, v3, v4])

    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def solidify_geometry(geometry):
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


def _triangulate_polygon_robust(poly):
    triangles = []
    kept_area = 0.0

    cdt = None
    try:
        cdt = constrained_delaunay_triangles(poly)
    except Exception as exc:
        logger.warning("Constrained triangulation failed, fallback to unconstrained: %s", exc)

    if cdt is not None and not cdt.is_empty:
        tri_geoms = [cdt] if cdt.geom_type == "Polygon" else list(cdt.geoms)
        for tri in tri_geoms:
            if tri.area <= 0:
                continue
            # Require full triangle to stay inside polygon (including hole boundaries).
            if not poly.covers(tri):
                continue
            triangles.append(tri)
            kept_area += tri.area
        coverage = kept_area / poly.area if poly.area > 0 else 0.0
        if coverage >= 0.995 and triangles:
            return triangles, coverage

    triangles = []
    kept_area = 0.0
    for tri in triangulate(poly):
        if tri.area <= 0:
            continue
        if not poly.covers(tri):
            continue
        triangles.append(tri)
        kept_area += tri.area
    coverage = kept_area / poly.area if poly.area > 0 else 0.0
    return triangles, coverage
