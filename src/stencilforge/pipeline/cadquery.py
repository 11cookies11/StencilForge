from __future__ import annotations

"""CadQuery 导出：将 2D 几何挤出为 3D 并导出 STL。"""

import logging
import time
from pathlib import Path

from shapely.ops import unary_union
from shapely.geometry import Polygon

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
    base_solids = cadquery_extrude_geometry(
        stencil_2d, config.thickness_mm, cq, config
    )
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
        locator_solids = cadquery_extrude_geometry(
            locator_geom, config.locator_height_mm, cq, config
        )
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
            locator_step_geom, config.locator_step_height_mm, cq, config
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

    t0 = time.perf_counter()
    solid = combine_cadquery_solids(solids, cq)
    logger.info("CadQuery boolean combine in %.3fs", time.perf_counter() - t0)
    t0 = time.perf_counter()
    solid = translate_cadquery_to_origin(solid)
    logger.info("CadQuery translate in %.3fs", time.perf_counter() - t0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tolerance = (
        config.stl_tolerance
        if getattr(config, "stl_tolerance", 0) and config.stl_tolerance > 0
        else config.stl_linear_deflection
    )
    cq.exporters.export(
        solid,
        str(output_path),
        exportType="STL",
        tolerance=tolerance,
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


def cadquery_extrude_geometry(geometry, thickness_mm: float, cq, config: StencilConfig):
    # 2D preprocess before extrude.
    t0 = time.perf_counter()
    geometry = ensure_valid(geometry)
    geometry = orient_geometry(geometry)
    geometry = solidify_geometry(geometry)
    geometry = _simplify_geometry(
        geometry,
        simplify_tol=getattr(config, "cadquery_simplify_tol_mm", 0.0),
        min_edge=getattr(config, "cadquery_short_edge_min_mm", 0.0),
        quantize=getattr(config, "cadquery_quantize_mm", 0.0),
    )
    logger.info("CadQuery 2D preprocess in %.3fs", time.perf_counter() - t0)

    polygons = []
    if geometry.geom_type == "Polygon":
        if geometry.area > 0:
            polygons.append(geometry)
    elif geometry.geom_type == "MultiPolygon":
        polygons.extend([poly for poly in geometry.geoms if poly.area > 0])
    else:
        t0 = time.perf_counter()
        merged = unary_union([geometry])
        logger.info("CadQuery 2D union in %.3fs", time.perf_counter() - t0)
        if merged.geom_type == "Polygon":
            if merged.area > 0:
                polygons.append(merged)
        elif merged.geom_type == "MultiPolygon":
            polygons.extend([poly for poly in merged.geoms if poly.area > 0])

    solids = []
    for idx, poly in enumerate(polygons, start=1):
        t0 = time.perf_counter()
        solid = cadquery_extrude_polygon(poly, thickness_mm, cq)
        logger.info(
            "CadQuery polygon %s/%s extrude in %.3fs",
            idx,
            len(polygons),
            time.perf_counter() - t0,
        )
        if solid is None:
            continue
        solids.append(solid)
    return solids


def cadquery_extrude_polygon(poly, thickness_mm: float, cq):
    # Outer boundary extrusion and hole cutting.
    hole_count = len(poly.interiors)
    logger.info("CadQuery polygon holes: %s", hole_count)
    outer = ring_to_cadquery_wire(poly.exterior, cq)
    if outer is None:
        return None
    hole_wires = []
    for hole_idx, hole in enumerate(poly.interiors, start=1):
        hole_wire = ring_to_cadquery_wire(hole, cq)
        if hole_wire is None:
            continue
        if hole_idx == 1 or hole_idx % 100 == 0 or hole_idx == hole_count:
            logger.info("CadQuery hole %s/%s wire built", hole_idx, hole_count)
        hole_wires.append(hole_wire)
    try:
        t0 = time.perf_counter()
        face = cq.Face.makeFromWires(outer, hole_wires)
        logger.info("CadQuery face build in %.3fs", time.perf_counter() - t0)
        t0 = time.perf_counter()
        base = cq.Workplane("XY").add(face).toPending().extrude(thickness_mm).val()
        logger.info("CadQuery face extrude in %.3fs", time.perf_counter() - t0)
        return base
    except Exception as exc:
        logger.warning("CadQuery face build failed, fallback to cuts: %s", exc)
    t0 = time.perf_counter()
    base = cq.Workplane("XY").add(outer).toPending().extrude(thickness_mm).val()
    logger.info("CadQuery outer extrude in %.3fs", time.perf_counter() - t0)
    hole_solids = []
    for hole_idx, hole in enumerate(poly.interiors, start=1):
        hole_wire = ring_to_cadquery_wire(hole, cq)
        if hole_wire is None:
            continue
        t0 = time.perf_counter()
        hole_solid = cq.Workplane("XY").add(hole_wire).toPending().extrude(thickness_mm).val()
        if hole_idx == 1 or hole_idx % 100 == 0 or hole_idx == hole_count:
            logger.info(
                "CadQuery hole %s/%s extrude in %.3fs",
                hole_idx,
                hole_count,
                time.perf_counter() - t0,
            )
        hole_solids.append(hole_solid)
    if hole_solids:
        batch_size = 50
        try:
            for start in range(0, len(hole_solids), batch_size):
                batch = hole_solids[start : start + batch_size]
                batch_end = start + len(batch)
                t0 = time.perf_counter()
                base = base.cut(cq.Compound.makeCompound(batch))
                logger.info(
                    "CadQuery hole batch cut %s-%s/%s in %.3fs",
                    start + 1,
                    batch_end,
                    hole_count,
                    time.perf_counter() - t0,
                )
        except Exception:
            for hole_idx, hole_solid in enumerate(hole_solids, start=1):
                t0 = time.perf_counter()
                base = base.cut(hole_solid)
                if hole_idx == 1 or hole_idx % 100 == 0 or hole_idx == hole_count:
                    logger.info(
                        "CadQuery hole %s/%s cut in %.3fs",
                        hole_idx,
                        hole_count,
                        time.perf_counter() - t0,
                    )
    return base



def _simplify_geometry(geometry, simplify_tol: float, min_edge: float, quantize: float):
    if simplify_tol and simplify_tol > 0:
        geometry = geometry.simplify(simplify_tol, preserve_topology=True)
    if (not min_edge or min_edge <= 0) and (not quantize or quantize <= 0):
        return geometry
    geom = geometry
    if geom.geom_type not in ("Polygon", "MultiPolygon"):
        try:
            geom = unary_union([geom])
        except Exception:
            return geometry
    if geom.geom_type == "Polygon":
        polys = [geom]
    elif geom.geom_type == "MultiPolygon":
        polys = list(geom.geoms)
    else:
        return geometry
    cleaned = []
    for poly in polys:
        ext = _clean_ring(poly.exterior.coords, min_edge, quantize)
        if not ext:
            continue
        holes = []
        for ring in poly.interiors:
            hole = _clean_ring(ring.coords, min_edge, quantize)
            if hole:
                holes.append(hole)
        cleaned_poly = Polygon(ext, holes)
        if cleaned_poly.is_valid and cleaned_poly.area > 0:
            cleaned.append(cleaned_poly)
    if not cleaned:
        return geometry
    return unary_union(cleaned) if len(cleaned) > 1 else cleaned[0]


def _clean_ring(coords, min_edge: float, quantize: float):
    points = list(coords)
    if len(points) < 3:
        return None
    if points[0] == points[-1]:
        points = points[:-1]
    if quantize and quantize > 0:
        points = [(round(x / quantize) * quantize, round(y / quantize) * quantize) for x, y in points]
    if not points:
        return None
    cleaned = [points[0]]
    for point in points[1:]:
        dx = point[0] - cleaned[-1][0]
        dy = point[1] - cleaned[-1][1]
        if min_edge and min_edge > 0 and (dx * dx + dy * dy) ** 0.5 < min_edge:
            continue
        cleaned.append(point)
    if len(cleaned) < 3:
        return None
    if cleaned[0] == cleaned[-1]:
        cleaned = cleaned[:-1]
    return cleaned



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
