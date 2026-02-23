from __future__ import annotations

from shapely.geometry import Polygon
from shapely.ops import unary_union

from stencilforge.pipeline.geometry import extrude_polygon_solid


def test_extrude_polygon_preserves_hole_projection() -> None:
    # Outer rectangle with a central hole and a narrow neck nearby.
    outer = [(0, 0), (40, 0), (40, 24), (0, 24), (0, 0)]
    hole = [(14, 8), (26, 8), (26, 16), (14, 16), (14, 8)]
    poly = Polygon(outer, [hole])

    thickness = 0.12
    mesh = extrude_polygon_solid(poly, thickness)

    top_triangles = []
    for face in mesh.faces:
        pts = mesh.vertices[face]
        if abs(float(pts[0][2]) - thickness) > 1e-9:
            continue
        if abs(float(pts[1][2]) - thickness) > 1e-9:
            continue
        if abs(float(pts[2][2]) - thickness) > 1e-9:
            continue
        top_triangles.append(Polygon([(float(pts[0][0]), float(pts[0][1])), (float(pts[1][0]), float(pts[1][1])), (float(pts[2][0]), float(pts[2][1]))]))

    assert top_triangles

    top_union = unary_union(top_triangles).buffer(0)

    # Top projection should match the source polygon closely.
    sym = top_union.symmetric_difference(poly)
    denom = max(poly.area, 1e-9)
    assert sym.area / denom < 1e-3

    # Hole must stay empty.
    hole_poly = Polygon(hole)
    assert top_union.intersection(hole_poly).area < 1e-6
