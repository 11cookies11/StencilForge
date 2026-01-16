from __future__ import annotations

"""CadQuery 导出：将 2D 几何挤出为 3D 并导出 STL。"""

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
    # CadQuery 在处理复杂孔洞时更稳，但依赖安装
    try:
        import cadquery as cq
    except ImportError as exc:
        raise ImportError("CadQuery is required for model_backend=cadquery") from exc

    main_stats = _geometry_complexity(stencil_2d)
    logger.info(
        "CadQuery input main: type=%s area=%.6f bounds=%s polys=%s holes=%s points=%s",
        main_stats["geom_type"],
        main_stats["area"],
        main_stats["bounds"],
        main_stats["polygons"],
        main_stats["holes"],
        main_stats["points"],
    )
    base_solids = cadquery_extrude_geometry(stencil_2d, config.thickness_mm, cq)
    solids = list(base_solids)
    # Locator solids extrude and merge.
    locator_solids = []
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_stats = _geometry_complexity(locator_geom)
        logger.info(
            "CadQuery input locator: type=%s area=%.6f bounds=%s polys=%s holes=%s points=%s",
            locator_stats["geom_type"],
            locator_stats["area"],
            locator_stats["bounds"],
            locator_stats["polygons"],
            locator_stats["holes"],
            locator_stats["points"],
        )
        locator_solids = cadquery_extrude_geometry(locator_geom, config.locator_height_mm, cq)
        for solid in locator_solids:
            solids.append(solid.translate((0, 0, config.thickness_mm)))
    step_solids = []
    if locator_step_geom is not None and not locator_step_geom.is_empty and config.locator_step_height_mm > 0:
        step_stats = _geometry_complexity(locator_step_geom)
        logger.info(
            "CadQuery input step: type=%s area=%.6f bounds=%s polys=%s holes=%s points=%s",
            step_stats["geom_type"],
            step_stats["area"],
            step_stats["bounds"],
            step_stats["polygons"],
            step_stats["holes"],
            step_stats["points"],
        )
        step_solids = cadquery_extrude_geometry(
            locator_step_geom, config.locator_step_height_mm, cq
        )
        for solid in step_solids:
            solids.append(solid.translate((0, 0, -config.locator_step_height_mm)))

    if not solids:
        raise ValueError("Failed to create CadQuery solids from geometry.")

    logger.info(
        "CadQuery solids: base=%s locator=%s step=%s total=%s",
        len(base_solids),
        len(locator_solids),
        len(step_solids),
        len(solids),
    )

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


def _geometry_complexity(geometry) -> dict[str, object]:
    stats = {
        "geom_type": None,
        "area": 0.0,
        "bounds": None,
        "polygons": 0,
        "holes": 0,
        "points": 0,
    }
    if geometry is None or geometry.is_empty:
        return stats
    stats["geom_type"] = geometry.geom_type
    try:
        stats["area"] = float(geometry.area)
    except Exception:
        stats["area"] = 0.0
    try:
        stats["bounds"] = geometry.bounds
    except Exception:
        stats["bounds"] = None
    geom = geometry
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        try:
            geom = unary_union([geom])
        except Exception:
            return stats
    if geom.geom_type == "Polygon":
        polys = [geom]
    elif geom.geom_type == "MultiPolygon":
        polys = list(geom.geoms)
    else:
        return stats
    stats["polygons"] = len(polys)
    holes = 0
    points = 0
    for poly in polys:
        ext = list(poly.exterior.coords)
        if len(ext) > 1 and ext[0] == ext[-1]:
            ext = ext[:-1]
        points += len(ext)
        for ring in poly.interiors:
            holes += 1
            coords = list(ring.coords)
            if len(coords) > 1 and coords[0] == coords[-1]:
                coords = coords[:-1]
            points += len(coords)
    stats["holes"] = holes
    stats["points"] = points
    return stats


def cadquery_extrude_geometry(geometry, thickness_mm: float, cq):
    # 统一几何处理后挤出
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
    # 外轮廓挤出为实体，再逐个孔洞切割
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
    # CadQuery 需要闭合线段作为 Wire
    coords = list(ring.coords)
    if len(coords) < 3:
        return None
    if coords[0] == coords[-1]:
        coords = coords[:-1]
    return cq.Wire.makePolygon(coords, close=True)


def combine_cadquery_solids(solids, cq):
    # 尝试 fuse；失败则退回 Compound
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
    # 将模型移动到原点，便于后续切片/对齐
    bbox = solid.BoundingBox()
    offset = (-bbox.xmin, -bbox.ymin, -bbox.zmin)
    return solid.translate(offset)
