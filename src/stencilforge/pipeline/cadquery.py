from __future__ import annotations

import logging
from pathlib import Path

from shapely.ops import unary_union

from ..config import StencilConfig
from .geometry import ensure_valid, orient_geometry, solidify_geometry

logger = logging.getLogger(__name__)


def export_cadquery_stl(
    stencil_2d,
    locator_geom,
    locator_step_geom,
    output_path: Path,
    config: StencilConfig,
) -> None:
    try:
        import cadquery as cq
    except ImportError as exc:
        raise ImportError("CadQuery is required for model_backend=cadquery") from exc

    solids = cadquery_extrude_geometry(stencil_2d, config.thickness_mm, cq)
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_solids = cadquery_extrude_geometry(locator_geom, config.locator_height_mm, cq)
        for solid in locator_solids:
            solids.append(solid.translate((0, 0, config.thickness_mm)))
    if locator_step_geom is not None and not locator_step_geom.is_empty and config.locator_step_height_mm > 0:
        step_solids = cadquery_extrude_geometry(
            locator_step_geom, config.locator_step_height_mm, cq
        )
        for solid in step_solids:
            solids.append(solid.translate((0, 0, -config.locator_step_height_mm)))

    if not solids:
        raise ValueError("Failed to create CadQuery solids from geometry.")

    solid = combine_cadquery_solids(solids, cq)
    solid = translate_cadquery_to_origin(solid)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cq.exporters.export(
        solid,
        str(output_path),
        exportType="STL",
        tolerance=config.stl_linear_deflection,
        angularTolerance=config.stl_angular_deflection,
    )
    try:
        size = output_path.stat().st_size
    except OSError:
        size = 0
    logger.info("STL size: %s bytes", size)
    if size <= 0:
        raise ValueError("Exported STL file is empty.")


def cadquery_extrude_geometry(geometry, thickness_mm: float, cq):
    geometry = ensure_valid(geometry)
    geometry = orient_geometry(geometry)
    geometry = solidify_geometry(geometry)

    polygons = []
    if geometry.geom_type == "Polygon":
        if geometry.area > 0:
            polygons.append(geometry)
    elif geometry.geom_type == "MultiPolygon":
        polygons.extend([poly for poly in geometry.geoms if poly.area > 0])
    else:
        merged = unary_union([geometry])
        if merged.geom_type == "Polygon":
            if merged.area > 0:
                polygons.append(merged)
        elif merged.geom_type == "MultiPolygon":
            polygons.extend([poly for poly in merged.geoms if poly.area > 0])

    solids = []
    for poly in polygons:
        solid = cadquery_extrude_polygon(poly, thickness_mm, cq)
        if solid is None:
            continue
        solids.append(solid)
    return solids


def cadquery_extrude_polygon(poly, thickness_mm: float, cq):
    outer = ring_to_cadquery_wire(poly.exterior, cq)
    if outer is None:
        return None
    base = cq.Workplane("XY").add(outer).toPending().extrude(thickness_mm).val()
    hole_solids = []
    for hole in poly.interiors:
        hole_wire = ring_to_cadquery_wire(hole, cq)
        if hole_wire is None:
            continue
        hole_solid = cq.Workplane("XY").add(hole_wire).toPending().extrude(thickness_mm).val()
        hole_solids.append(hole_solid)
    if hole_solids:
        try:
            base = base.cut(cq.Compound.makeCompound(hole_solids))
        except Exception:
            for hole_solid in hole_solids:
                base = base.cut(hole_solid)
    return base


def ring_to_cadquery_wire(ring, cq):
    coords = list(ring.coords)
    if len(coords) < 3:
        return None
    if coords[0] == coords[-1]:
        coords = coords[:-1]
    return cq.Wire.makePolygon(coords, close=True)


def combine_cadquery_solids(solids, cq):
    if len(solids) == 1:
        return solids[0]
    result = solids[0]
    for solid in solids[1:]:
        try:
            result = result.fuse(solid)
        except Exception:
            return cq.Compound.makeCompound(solids)
    return result


def translate_cadquery_to_origin(solid):
    bbox = solid.BoundingBox()
    offset = (-bbox.xmin, -bbox.ymin, -bbox.zmin)
    return solid.translate(offset)
