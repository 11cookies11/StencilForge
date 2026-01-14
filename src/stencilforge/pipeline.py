from __future__ import annotations

from pathlib import Path
from fnmatch import fnmatch
import logging
import math
import shutil

from shapely import affinity
from shapely.geometry import box, Polygon, MultiPoint, LineString
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, triangulate, linemerge
from shapely.validation import explain_validity
import trimesh
from PIL import Image, ImageDraw

from .config import StencilConfig
from .gerber_adapter import GerberGeometryService

logger = logging.getLogger(__name__)


def generate_stencil(input_dir: Path, output_path: Path, config: StencilConfig) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    config.validate()
    geometry_service = GerberGeometryService(config)
    logger.info("Generating stencil from %s", input_dir)
    logger.info("Output STL: %s", output_path)
    if config.debug_enabled and config.debug_log_detail:
        logger.info(
            "Config: mode=%s backend=%s thickness=%s offset=%s outline_margin=%s arc_steps=%s curve_resolution=%s",
            config.output_mode,
            config.model_backend,
            config.thickness_mm,
            config.paste_offset_mm,
            config.outline_margin_mm,
            config.arc_steps,
            config.curve_resolution,
        )
    debug_dir = _resolve_debug_dir(output_path, config)
    paste_files = _find_files(input_dir, config.paste_patterns)
    if not paste_files:
        raise FileNotFoundError("No paste layer files found in input directory.")
    if config.debug_enabled and config.debug_log_detail:
        logger.info("Paste files: %s", ", ".join(p.name for p in paste_files))
    logger.info("Paste layers: %s", ", ".join([p.name for p in paste_files]))
    paste_geom = geometry_service.load_paste_geometry(paste_files)
    if paste_geom is None or paste_geom.is_empty:
        raise ValueError("Paste layer produced empty geometry.")
    _log_geometry("paste", paste_geom, config.debug_enabled and config.debug_log_detail)
    _dump_geometry(debug_dir, "step2_paste", paste_geom)
    if config.qfn_regen_enabled:
        try:
            paste_geom = _regenerate_qfn_paste(paste_geom, config)
        except Exception as exc:
            logger.warning("QFN regeneration skipped: %s", exc)

    paste_geom = paste_geom.buffer(
        config.paste_offset_mm, resolution=config.curve_resolution
    )
    if paste_geom.is_empty:
        raise ValueError("Paste offset produced empty geometry.")
    logger.info("Paste offset: %s mm", config.paste_offset_mm)
    _log_geometry("paste_offset", paste_geom, config.debug_enabled and config.debug_log_detail)
    _dump_geometry(debug_dir, "step2_paste_offset", paste_geom)

    outline_geom = None
    outline_files = _find_files(input_dir, config.outline_patterns)
    if outline_files:
        if debug_dir is not None:
            try:
                shutil.copy2(outline_files[0], debug_dir / "outline_source.gko")
            except OSError:
                logger.warning("Failed to copy outline source to debug dir.")
            try:
                # 调试：按 GKO 指令路径输出彩色线段图。
                # ???? GKO ????????????
                _dump_gko_paths_png(outline_files[0], debug_dir)
            except Exception as exc:
                logger.warning("Failed to render GKO paths: %s", exc)
        if debug_dir is not None and config.debug_enabled:
            try:
                outline_geom, outline_debug = geometry_service.load_outline_geometry_debug(outline_files[0])
                outline_segments = outline_debug.get("segments_geom")
                if outline_segments is not None:
                    # 调试：外形原始线段。
                    # ??????????
                    _dump_geometry(debug_dir, "step2_outline_segments", outline_segments)
                outline_loops = outline_debug.get("loops_geom")
                if outline_loops is not None:
                    # 调试：闭合后的线段环。
                    # ???????????
                    _dump_geometry(debug_dir, "step2_outline_segments_closed", outline_loops)
                max_gap = outline_debug.get("max_gap_pair")
                if outline_segments is not None and max_gap is not None:
                    points = [max_gap[0], max_gap[1]]
                    image = _geometry_png_with_markers(
                        outline_segments,
                        points,
                        stroke="#1f2937",
                        marker="#dc2626",
                    )
                    if image is not None:
                        # 调试：最大缺口端点标注。
                        # ????????????
                        image.save(debug_dir / "step2_outline_segments_gap.png")
                snapped_segments = outline_debug.get("snapped_geom")
                if snapped_segments is not None:
                    _dump_geometry(debug_dir, "step2_outline_segments_snapped", snapped_segments)
                snap_tol = outline_debug.get("snap_tol")
                if snap_tol is not None:
                    logger.info("Outline snap tol used: %s", snap_tol)
            except Exception as exc:
                logger.warning("Failed to dump outline debug: %s", exc)
                outline_geom = geometry_service.load_outline_geometry(outline_files[0])
        else:
            outline_geom = geometry_service.load_outline_geometry(outline_files[0])
        logger.info("Outline layer: %s", outline_files[0].name)

    if outline_geom is None or outline_geom.is_empty:
        # 外形层缺失时，用 paste 外包做兜底。
        # ???????? paste ??????
        outline_geom = _outline_from_paste(paste_geom, config.outline_margin_mm)
        logger.info("Outline fallback margin: %s mm", config.outline_margin_mm)
    else:
        _log_geometry("outline", outline_geom, config.debug_enabled and config.debug_log_detail)
    _dump_geometry(debug_dir, "step2_outline", outline_geom)
    _dump_geometry(debug_dir, "step5_outline", outline_geom)

    logger.info("Output mode: %s", config.output_mode)
    if config.output_mode == "holes_only":
        stencil_2d = paste_geom
    else:
        stencil_2d = outline_geom.difference(paste_geom)
        hole_count = _count_holes(stencil_2d)
        logger.info(
            "Stencil 2D: type=%s area=%.6f bounds=%s holes=%s",
            stencil_2d.geom_type,
            stencil_2d.area,
            stencil_2d.bounds if not stencil_2d.is_empty else None,
            hole_count,
        )
        _write_debug_svg(output_path, outline_geom, paste_geom, stencil_2d)
        _log_geometry("stencil_2d", stencil_2d, config.debug_enabled and config.debug_log_detail)
        _dump_geometry(debug_dir, "step6_stencil_2d", stencil_2d)
    locator_bridge_geom = None
    if (
        config.locator_enabled
        and config.locator_mode == "step"
        and outline_geom is not None
        and not outline_geom.is_empty
        and config.locator_clearance_mm > 0
    ):
        locator_bridge_geom = _build_locator_bridge(
            outline_geom,
            config.locator_clearance_mm,
            config.locator_open_side,
            config.locator_open_width_mm,
        )
        if locator_bridge_geom is not None and not locator_bridge_geom.is_empty:
            stencil_2d = unary_union([stencil_2d, locator_bridge_geom])
            logger.info("Locator bridge: clearance=%s open=%s(%s)", config.locator_clearance_mm, config.locator_open_side, config.locator_open_width_mm)
            _dump_geometry(debug_dir, "locator_bridge", locator_bridge_geom)

    logger.info("Base thickness: %s mm", config.thickness_mm)

    locator_geom = None
    locator_step_geom = None
    if config.locator_enabled and outline_geom is not None and not outline_geom.is_empty:
        if config.locator_mode == "step":
            locator_step_geom = _build_locator_step(
                outline_geom,
                config.locator_clearance_mm,
                config.locator_step_width_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )
            if (
                locator_step_geom is not None
                and not locator_step_geom.is_empty
                and config.locator_step_height_mm > 0
            ):
                logger.info(
                    "Locator step: height=%s width=%s clearance=%s open=%s(%s)",
                    config.locator_step_height_mm,
                    config.locator_step_width_mm,
                    config.locator_clearance_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )
            else:
                locator_step_geom = None
                locator_geom = _build_locator_ring(
                    outline_geom,
                    config.locator_clearance_mm,
                    config.locator_width_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )
                if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
                    logger.info(
                        "Locator wall: height=%s width=%s clearance=%s open=%s(%s)",
                        config.locator_height_mm,
                        config.locator_width_mm,
                        config.locator_clearance_mm,
                        config.locator_open_side,
                        config.locator_open_width_mm,
                    )
        else:
            locator_geom = _build_locator_ring(
                outline_geom,
                config.locator_clearance_mm,
                config.locator_width_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )
            if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
                logger.info(
                    "Locator wall: height=%s width=%s clearance=%s open=%s(%s)",
                    config.locator_height_mm,
                    config.locator_width_mm,
                    config.locator_clearance_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )
    if locator_step_geom is not None and not locator_step_geom.is_empty:
        _dump_geometry(debug_dir, "locator_step", locator_step_geom)
    if locator_geom is not None and not locator_geom.is_empty:
        _dump_geometry(debug_dir, "locator_wall", locator_geom)

    if config.model_backend == "cadquery":
        _export_cadquery_stl(stencil_2d, locator_geom, locator_step_geom, output_path, config)
        return

    mesh = _extrude_geometry(stencil_2d, config.thickness_mm)
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_mesh = _extrude_geometry(locator_geom, config.locator_height_mm)
        locator_mesh.apply_translation((0, 0, config.thickness_mm))
        mesh = trimesh.util.concatenate([mesh, locator_mesh])
    if locator_step_geom is not None and not locator_step_geom.is_empty and config.locator_step_height_mm > 0:
        step_mesh = _extrude_geometry(locator_step_geom, config.locator_step_height_mm)
        step_mesh.apply_translation((0, 0, -config.locator_step_height_mm))
        mesh = trimesh.util.concatenate([mesh, step_mesh])

    logger.info("Cleaning mesh...")
    try:
        _cleanup_mesh(mesh)
    except Exception as exc:
        logger.warning("Mesh cleanup failed: %s", exc)
    logger.info("Translating mesh to origin...")
    try:
        _translate_to_origin(mesh)
    except Exception as exc:
        logger.warning("Mesh translation failed: %s", exc)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if mesh.is_empty or mesh.faces.size == 0:
        raise ValueError("Generated mesh is empty; check outline/paste geometry.")
    watertight = getattr(mesh, "is_watertight", None)
    euler = getattr(mesh, "euler_number", None)
    logger.info("Mesh stats: faces=%s watertight=%s euler=%s", mesh.faces.shape[0], watertight, euler)
    mesh.export(output_path, file_type="stl_ascii")
    try:
        size = output_path.stat().st_size
    except OSError:
        size = 0
    logger.info("STL size: %s bytes", size)
    if size <= 0:
        raise ValueError("Exported STL file is empty.")
    try:
        check_mesh = trimesh.load_mesh(output_path, force="mesh")
        faces = getattr(check_mesh, "faces", None)
        face_count = int(faces.shape[0]) if faces is not None else 0
        logger.info("STL check: faces=%s", face_count)
        if face_count == 0:
            raise ValueError("Exported STL has no faces; check geometry.")
    except Exception as exc:
        raise ValueError(f"Failed to validate exported STL: {exc}") from exc
    logger.info("STL export complete")


def _find_files(input_dir: Path, patterns: list[str]) -> list[Path]:
    if not patterns:
        return []
    files = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        for pattern in patterns:
            if _match(pattern.lower(), name):
                files.append(path)
                break
    return sorted(set(files))


def _match(pattern: str, name: str) -> bool:
    return fnmatch(name, pattern)


def _outline_from_paste(paste_geom, margin_mm: float):
    min_x, min_y, max_x, max_y = paste_geom.bounds
    return box(min_x - margin_mm, min_y - margin_mm, max_x + margin_mm, max_y + margin_mm)


def _build_locator_ring(
    outline_geom,
    clearance_mm: float,
    width_mm: float,
    open_side: str,
    open_width_mm: float,
):
    if width_mm <= 0:
        return None
    inner = outline_geom.buffer(clearance_mm)
    outer = outline_geom.buffer(clearance_mm + width_mm)
    ring = outer.difference(inner)
    ring = _apply_open_side(ring, outer, open_side, open_width_mm)
    return ring


def _build_locator_step(
    outline_geom,
    clearance_mm: float,
    step_width_mm: float,
    open_side: str,
    open_width_mm: float,
):
    if step_width_mm <= 0:
        return None
    inner = outline_geom.buffer(clearance_mm)
    outer = outline_geom.buffer(clearance_mm + step_width_mm)
    step = outer.difference(inner)
    step = _apply_open_side(step, outer, open_side, open_width_mm)
    return step


def _build_locator_bridge(
    outline_geom,
    clearance_mm: float,
    open_side: str,
    open_width_mm: float,
):
    if clearance_mm <= 0:
        return None
    outer = outline_geom.buffer(clearance_mm)
    ring = outer.difference(outline_geom)
    ring = _apply_open_side(ring, outer, open_side, open_width_mm)
    return ring


def _apply_open_side(ring, outer, open_side: str, open_width_mm: float):
    if open_side == "none" or open_width_mm <= 0:
        return ring
    min_x, min_y, max_x, max_y = outer.bounds
    if open_side == "top":
        cutter = box(min_x - open_width_mm, max_y - open_width_mm, max_x + open_width_mm, max_y + open_width_mm)
    elif open_side == "bottom":
        cutter = box(min_x - open_width_mm, min_y - open_width_mm, max_x + open_width_mm, min_y + open_width_mm)
    elif open_side == "left":
        cutter = box(min_x - open_width_mm, min_y - open_width_mm, min_x + open_width_mm, max_y + open_width_mm)
    elif open_side == "right":
        cutter = box(max_x - open_width_mm, min_y - open_width_mm, max_x + open_width_mm, max_y + open_width_mm)
    else:
        return ring
    return ring.difference(cutter)


def _extrude_geometry(geometry, thickness_mm: float):
    geometry = _ensure_valid(geometry)
    geometry = _orient_geometry(geometry)
    geometry = _solidify_geometry(geometry)
    meshes = []
    if geometry.geom_type == "Polygon":
        if geometry.area > 0:
            meshes.append(_extrude_polygon_solid(geometry, thickness_mm))
    elif geometry.geom_type == "MultiPolygon":
        for poly in geometry.geoms:
            poly = _ensure_valid(poly)
            if poly.area <= 0:
                continue
            meshes.append(_extrude_polygon_solid(poly, thickness_mm))
    else:
        merged = unary_union([geometry])
        if merged.geom_type == "Polygon":
            merged = _ensure_valid(merged)
            if merged.area > 0:
                meshes.append(_extrude_polygon_solid(merged, thickness_mm))
        elif merged.geom_type == "MultiPolygon":
            for poly in merged.geoms:
                poly = _ensure_valid(poly)
                if poly.area <= 0:
                    continue
                meshes.append(_extrude_polygon_solid(poly, thickness_mm))
    if not meshes:
        raise ValueError("Failed to create STL mesh from geometry.")
    mesh = trimesh.util.concatenate(meshes)
    if mesh.is_empty or mesh.faces.size == 0:
        raise ValueError("Failed to create non-empty STL mesh from geometry.")
    return mesh


def _ensure_valid(geometry):
    if geometry.is_valid:
        return geometry
    return geometry.buffer(0)


def _orient_geometry(geometry):
    if geometry.is_empty:
        return geometry
    if geometry.geom_type == "Polygon":
        return orient(geometry, sign=1.0)
    if geometry.geom_type == "MultiPolygon":
        return geometry.__class__([orient(poly, sign=1.0) for poly in geometry.geoms])
    return geometry


def _count_holes(geometry) -> int:
    if geometry.is_empty:
        return 0
    if geometry.geom_type == "Polygon":
        return len(geometry.interiors)
    if geometry.geom_type == "MultiPolygon":
        return sum(len(poly.interiors) for poly in geometry.geoms)
    return 0


def _count_polygons(geometry) -> int:
    if geometry.is_empty:
        return 0
    if geometry.geom_type == "Polygon":
        return 1
    if geometry.geom_type == "MultiPolygon":
        return len(geometry.geoms)
    return 0


def _export_cadquery_stl(
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

    solids = _cadquery_extrude_geometry(stencil_2d, config.thickness_mm, cq)
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_solids = _cadquery_extrude_geometry(locator_geom, config.locator_height_mm, cq)
        for solid in locator_solids:
            solids.append(solid.translate((0, 0, config.thickness_mm)))
    if locator_step_geom is not None and not locator_step_geom.is_empty and config.locator_step_height_mm > 0:
        step_solids = _cadquery_extrude_geometry(
            locator_step_geom, config.locator_step_height_mm, cq
        )
        for solid in step_solids:
            solids.append(solid.translate((0, 0, -config.locator_step_height_mm)))

    if not solids:
        raise ValueError("Failed to create CadQuery solids from geometry.")

    solid = _combine_cadquery_solids(solids, cq)
    solid = _translate_cadquery_to_origin(solid)

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


def _cadquery_extrude_geometry(geometry, thickness_mm: float, cq):
    geometry = _ensure_valid(geometry)
    geometry = _orient_geometry(geometry)
    geometry = _solidify_geometry(geometry)

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
        solid = _cadquery_extrude_polygon(poly, thickness_mm, cq)
        if solid is None:
            continue
        solids.append(solid)
    return solids


def _cadquery_extrude_polygon(poly, thickness_mm: float, cq):
    outer = _ring_to_cadquery_wire(poly.exterior, cq)
    if outer is None:
        return None
    base = cq.Workplane("XY").add(outer).toPending().extrude(thickness_mm).val()
    hole_solids = []
    for hole in poly.interiors:
        hole_wire = _ring_to_cadquery_wire(hole, cq)
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


def _ring_to_cadquery_wire(ring, cq):
    coords = list(ring.coords)
    if len(coords) < 3:
        return None
    if coords[0] == coords[-1]:
        coords = coords[:-1]
    return cq.Wire.makePolygon(coords, close=True)


def _combine_cadquery_solids(solids, cq):
    if len(solids) == 1:
        return solids[0]
    result = solids[0]
    for solid in solids[1:]:
        try:
            result = result.fuse(solid)
        except Exception:
            return cq.Compound.makeCompound(solids)
    return result


def _translate_cadquery_to_origin(solid):
    bbox = solid.BoundingBox()
    offset = (-bbox.xmin, -bbox.ymin, -bbox.zmin)
    return solid.translate(offset)


def _extrude_polygon_solid(poly, thickness_mm: float) -> trimesh.Trimesh:
    triangles = []
    kept_area = 0.0
    for tri in triangulate(poly):
        if not poly.covers(tri.representative_point()):
            continue
        triangles.append(tri)
        kept_area += tri.area
    coverage = kept_area / poly.area if poly.area > 0 else 0
    if coverage < 0.98:
        # Try a buffered copy to recover boundary triangles on tricky polygons.
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
        key = (float(x), float(y), float(z))
        idx = vertex_index.get(key)
        if idx is None:
            idx = len(vertices)
            vertices.append(key)
            vertex_index[key] = idx
        return idx

    # Top and bottom faces
    for tri in triangles:
        coords = list(tri.exterior.coords)[:3]
        top = [add_vertex(x, y, thickness_mm) for x, y in coords]
        bottom = [add_vertex(x, y, 0.0) for x, y in coords]
        faces.append(top)
        faces.append(bottom[::-1])

    # Side walls for exterior ring only
    rings = [poly.exterior]
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


def _solidify_geometry(geometry):
    if geometry.is_empty:
        return geometry
    if geometry.geom_type == "Polygon" and geometry.interiors:
        holes = [Polygon(hole.coords).buffer(0) for hole in geometry.interiors if len(hole.coords) >= 3]
        if holes:
            return geometry.difference(unary_union(holes))
    if geometry.geom_type == "MultiPolygon":
        parts = []
        for poly in geometry.geoms:
            parts.append(_solidify_geometry(poly))
        return unary_union([p for p in parts if p is not None and not p.is_empty])
    return geometry


def _regenerate_qfn_paste(geometry, config: StencilConfig):
    polys = _flatten_polygons(geometry)
    if not polys:
        return geometry
    pads = _detect_qfn_pads(polys, config)
    if pads is None:
        return geometry
    qfn, score = _build_qfn_group(pads, polys, config)
    if qfn is None or score < config.qfn_confidence_threshold:
        return geometry
    logger.info("QFN detect: pads=%s score=%.2f", len(qfn["pads"]), score)
    regenerated = _regenerate_qfn_geometry(qfn, polys, config)
    if regenerated is None:
        return geometry
    return regenerated


def _flatten_polygons(geometry):
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)
    polygons = []
    if hasattr(geometry, "geoms"):
        for geom in geometry.geoms:
            if geom.geom_type == "Polygon":
                polygons.append(geom)
            elif geom.geom_type == "MultiPolygon":
                polygons.extend(list(geom.geoms))
    return polygons


def _detect_qfn_pads(polys, config: StencilConfig):
    pads = []
    for poly in polys:
        metrics = _polygon_rect_metrics(poly)
        if metrics is None:
            continue
        rect_area, long_side, short_side, angle = metrics
        if rect_area <= 0:
            continue
        rectangularity = poly.area / rect_area
        aspect = long_side / short_side if short_side > 0 else 0
        if rectangularity < 0.85:
            continue
        if not 1.2 <= aspect <= 6.0:
            continue
        if short_side > config.qfn_max_pad_width_mm:
            continue
        pads.append(
            {
                "poly": poly,
                "center": (poly.centroid.x, poly.centroid.y),
                "angle": angle,
                "long": long_side,
                "short": short_side,
            }
        )
    if len(pads) < 12:
        return None
    return pads


def _polygon_rect_metrics(poly):
    try:
        rect = poly.minimum_rotated_rectangle
    except Exception:
        return None
    coords = list(rect.exterior.coords)
    if len(coords) < 4:
        return None
    edges = []
    for i in range(4):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % 4]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        edges.append((length, dx, dy))
    edges.sort(key=lambda e: e[0], reverse=True)
    long_len, long_dx, long_dy = edges[0]
    short_len = edges[-1][0]
    angle = math.degrees(math.atan2(long_dy, long_dx))
    angle = _normalize_angle(angle)
    return rect.area, long_len, short_len, angle


def _normalize_angle(angle_deg: float) -> float:
    angle = angle_deg % 180.0
    if angle < 0:
        angle += 180.0
    return angle


def _rotate_point(point, angle_deg: float):
    x, y = point
    radians = math.radians(angle_deg)
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _build_qfn_group(pads, polys, config: StencilConfig):
    centers = [p["center"] for p in pads]
    rect = MultiPoint(centers).minimum_rotated_rectangle
    rect_metrics = _polygon_rect_metrics(rect)
    if rect_metrics is None:
        return None, 0.0
    _, _, _, global_angle = rect_metrics
    for pad in pads:
        pad["center_norm"] = _rotate_point(pad["center"], -global_angle)
        pad["angle_norm"] = _normalize_angle(pad["angle"] - global_angle)

    horizontal = []
    vertical = []
    for pad in pads:
        angle = pad["angle_norm"]
        if angle <= 30 or angle >= 150:
            horizontal.append(pad)
        elif 60 <= angle <= 120:
            vertical.append(pad)
    if len(horizontal) < 6 or len(vertical) < 6:
        return None, 0.0

    horiz_rows = _cluster_rows(horizontal, axis="y", config=config)
    vert_rows = _cluster_rows(vertical, axis="x", config=config)
    if not horiz_rows or not vert_rows:
        return None, 0.0

    center = _estimate_center(pads)
    qfn = _pick_qfn_sides(horiz_rows, vert_rows, center)
    if qfn is None:
        return None, 0.0

    center_pad = _detect_center_pad(polys, center, pads, global_angle)
    qfn["center_pad"] = center_pad
    qfn["global_angle"] = global_angle
    score = _score_qfn(qfn)
    return qfn, score


def _cluster_rows(pads, axis: str, config: StencilConfig):
    widths = [p["short"] for p in pads if p["short"] > 0]
    if not widths:
        return []
    width_median = _median(widths)
    tol = max(width_median * 1.5, config.qfn_min_feature_mm * 0.5)
    key_index = 1 if axis == "y" else 0
    sorted_pads = sorted(pads, key=lambda p: p["center_norm"][key_index])
    rows = []
    current = []
    last_value = None
    for pad in sorted_pads:
        value = pad["center_norm"][key_index]
        if last_value is None or abs(value - last_value) <= tol:
            current.append(pad)
        else:
            if len(current) >= 3:
                rows.append(_make_row(current, axis))
            current = [pad]
        last_value = value
    if len(current) >= 3:
        rows.append(_make_row(current, axis))
    return rows


def _make_row(pads, axis: str):
    direction_axis = "x" if axis == "y" else "y"
    if direction_axis == "x":
        pads_sorted = sorted(pads, key=lambda p: p["center_norm"][0])
        coord = _median([p["center_norm"][1] for p in pads])
    else:
        pads_sorted = sorted(pads, key=lambda p: p["center_norm"][1])
        coord = _median([p["center_norm"][0] for p in pads])
    return {
        "pads": pads_sorted,
        "axis": axis,
        "coord": coord,
    }


def _estimate_center(pads):
    xs = [p["center_norm"][0] for p in pads]
    ys = [p["center_norm"][1] for p in pads]
    return (_median(xs), _median(ys))


def _pick_qfn_sides(horiz_rows, vert_rows, center):
    if len(horiz_rows) < 2 or len(vert_rows) < 2:
        return None
    horiz_rows = sorted(horiz_rows, key=lambda r: r["coord"])
    vert_rows = sorted(vert_rows, key=lambda r: r["coord"])
    bottom = horiz_rows[0]
    top = horiz_rows[-1]
    left = vert_rows[0]
    right = vert_rows[-1]
    sides = [top, right, bottom, left]
    if any(len(side["pads"]) < 3 for side in sides):
        return None
    counts = [len(side["pads"]) for side in sides]
    if max(counts) - min(counts) > max(2, int(0.3 * max(counts))):
        return None
    pads = []
    for side in sides:
        pads.extend(side["pads"])
    return {
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
        "pads": pads,
        "center_norm": center,
    }


def _detect_center_pad(polys, center_norm, pads, global_angle):
    pad_areas = [p["poly"].area for p in pads]
    if not pad_areas:
        return None
    area_median = _median(pad_areas)
    max_poly = None
    max_area = 0.0
    for poly in polys:
        if poly.area < area_median * 4.0:
            continue
        center = (poly.centroid.x, poly.centroid.y)
        center_rot = _rotate_point(center, -global_angle)
        dx = center_rot[0] - center_norm[0]
        dy = center_rot[1] - center_norm[1]
        distance = math.hypot(dx, dy)
        if distance > max(1.0, area_median ** 0.5 * 4.0):
            continue
        if poly.area > max_area:
            max_area = poly.area
            max_poly = poly
    return max_poly


def _score_qfn(qfn):
    scores = []
    spacing_scores = []
    for side in (qfn["top"], qfn["bottom"], qfn["left"], qfn["right"]):
        pitches = _side_pitches(side)
        spacing_scores.append(_score_variation(pitches, target_cv=0.2))
    scores.append(_average(spacing_scores))
    pad_widths = [p["short"] for p in qfn["pads"]]
    scores.append(_score_variation(pad_widths, target_cv=0.25))
    counts = [len(qfn["top"]["pads"]), len(qfn["bottom"]["pads"]), len(qfn["left"]["pads"]), len(qfn["right"]["pads"])]
    symmetry = 1.0 - (max(counts) - min(counts)) / max(counts)
    scores.append(max(0.0, symmetry))
    scores.append(1.0)
    base = _average(scores)
    if qfn.get("center_pad") is not None:
        base = min(1.0, base + 0.05)
    return base


def _side_pitches(side):
    pads = side["pads"]
    if len(pads) < 2:
        return []
    if side["axis"] == "y":
        coords = [p["center_norm"][0] for p in pads]
    else:
        coords = [p["center_norm"][1] for p in pads]
    coords = sorted(coords)
    return [coords[i + 1] - coords[i] for i in range(len(coords) - 1)]


def _score_variation(values, target_cv: float):
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean <= 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    cv = math.sqrt(variance) / mean
    return max(0.0, 1.0 - cv / target_cv)


def _average(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def _median(values):
    values = sorted(values)
    if not values:
        return 0.0
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _regenerate_qfn_geometry(qfn, polys, config: StencilConfig):
    min_feature = config.qfn_min_feature_mm
    slots = []
    kept = []
    pad_set = {id(p["poly"]) for p in qfn["pads"]}
    center_pad = qfn.get("center_pad")
    for poly in polys:
        if id(poly) in pad_set:
            continue
        if center_pad is not None and poly.equals(center_pad):
            continue
        kept.append(poly)

    for side in (qfn["top"], qfn["bottom"], qfn["left"], qfn["right"]):
        pitch, pad_width = _estimate_pitch_and_width(side)
        if pitch is None or pad_width is None:
            return None
        web = pitch - pad_width
        if web < min_feature:
            side_slots = _generate_slots_for_side(side, qfn, min_feature)
            if not side_slots:
                return None
            slots.extend(side_slots)
        else:
            kept.extend([p["poly"] for p in side["pads"]])

    if center_pad is not None:
        windows = _generate_center_windowpane(center_pad, qfn, min_feature)
        if windows:
            kept.extend(windows)
        else:
            kept.append(center_pad)

    merged = unary_union(kept + slots)
    return merged


def _estimate_pitch_and_width(side):
    pitches = _side_pitches(side)
    if not pitches:
        return None, None
    pitch = _median(pitches)
    widths = [p["short"] for p in side["pads"]]
    pad_width = _median(widths)
    return pitch, pad_width


def _generate_slots_for_side(side, qfn, min_feature):
    pads = side["pads"]
    count = len(pads)
    if count <= 6:
        slots_count = 2
    elif count <= 12:
        slots_count = 3
    else:
        slots_count = 4

    if side["axis"] == "y":
        coords = [p["center_norm"][0] for p in pads]
        row_coord = side["coord"]
        direction = "x"
    else:
        coords = [p["center_norm"][1] for p in pads]
        row_coord = side["coord"]
        direction = "y"

    coord_min = min(coords)
    coord_max = max(coords)
    span = coord_max - coord_min
    if span <= 0:
        return []

    pad_width = _median([p["short"] for p in pads])
    slot_width = max(min_feature, pad_width)
    slot_length = max(2 * slot_width, min(span * 0.8, span))
    slot_length = max(slot_length, span * 0.6)

    centers = []
    for i in range(slots_count):
        t = (i + 0.5) / slots_count
        center = coord_min + t * span
        low = coord_min + slot_length / 2.0
        high = coord_max - slot_length / 2.0
        if high < low:
            center = (coord_min + coord_max) / 2.0
        else:
            center = max(low, min(high, center))
        centers.append(center)

    outward = _outward_sign(side, qfn["center_norm"])
    bias = min(0.3 * slot_width, 0.25)
    slots = []
    for center in centers:
        if direction == "x":
            cx, cy = center, row_coord + outward * bias
            slot = box(
                cx - slot_length / 2.0,
                cy - slot_width / 2.0,
                cx + slot_length / 2.0,
                cy + slot_width / 2.0,
            )
        else:
            cx, cy = row_coord + outward * bias, center
            slot = box(
                cx - slot_width / 2.0,
                cy - slot_length / 2.0,
                cx + slot_width / 2.0,
                cy + slot_length / 2.0,
            )
        slot = affinity.rotate(slot, qfn["global_angle"], origin=(0, 0))
        slots.append(slot)
    return slots


def _outward_sign(side, center_norm):
    if side["axis"] == "y":
        return 1.0 if side["coord"] > center_norm[1] else -1.0
    return 1.0 if side["coord"] > center_norm[0] else -1.0


def _generate_center_windowpane(center_pad, qfn, min_feature):
    rotated = affinity.rotate(center_pad, -qfn["global_angle"], origin=(0, 0))
    bounds = rotated.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= min_feature * 2 or height <= min_feature * 2:
        return None
    if min(width, height) < 3.0:
        rows = cols = 2
    elif min(width, height) < 6.0:
        rows = cols = 3
    else:
        rows = cols = 4

    web = min_feature
    cell_w_max = (width - (cols + 1) * web) / cols
    cell_h_max = (height - (rows + 1) * web) / rows
    if cell_w_max < min_feature or cell_h_max < min_feature:
        return None

    target_area = rotated.area * 0.5
    max_area = cell_w_max * cell_h_max * rows * cols
    scale = math.sqrt(min(1.0, target_area / max_area))
    cell_w = max(min_feature, cell_w_max * scale)
    cell_h = max(min_feature, cell_h_max * scale)

    total_w = cols * cell_w + (cols - 1) * web
    total_h = rows * cell_h + (rows - 1) * web
    start_x = (bounds[0] + bounds[2]) / 2.0 - total_w / 2.0
    start_y = (bounds[1] + bounds[3]) / 2.0 - total_h / 2.0

    windows = []
    for r in range(rows):
        for c in range(cols):
            x0 = start_x + c * (cell_w + web)
            y0 = start_y + r * (cell_h + web)
            rect = box(x0, y0, x0 + cell_w, y0 + cell_h)
            rect = rect.intersection(rotated)
            if rect.is_empty or rect.area < min_feature * min_feature * 0.5:
                continue
            rect = affinity.rotate(rect, qfn["global_angle"], origin=(0, 0))
            windows.append(rect)
    return windows if windows else None


def _cleanup_mesh(mesh: trimesh.Trimesh) -> None:
    before_faces = int(mesh.faces.shape[0]) if mesh.faces is not None else 0
    if hasattr(mesh, "remove_degenerate_faces"):
        mesh.remove_degenerate_faces()
    if hasattr(mesh, "remove_duplicate_faces"):
        mesh.remove_duplicate_faces()
    if hasattr(mesh, "remove_infinite_values"):
        mesh.remove_infinite_values()
    if hasattr(mesh, "merge_vertices"):
        mesh.merge_vertices()
    if hasattr(mesh, "remove_unreferenced_vertices"):
        mesh.remove_unreferenced_vertices()
    if hasattr(mesh, "fix_normals"):
        try:
            mesh.fix_normals()
        except Exception:
            pass
    after_faces = int(mesh.faces.shape[0]) if mesh.faces is not None else 0
    logger.info("Mesh cleanup: faces %s -> %s", before_faces, after_faces)


def _translate_to_origin(mesh: trimesh.Trimesh) -> None:
    bounds = mesh.bounds
    if bounds is None:
        return
    min_x, min_y, min_z = bounds[0]
    offset = (-min_x, -min_y, -min_z)
    mesh.apply_translation(offset)
    logger.info("Mesh translated to origin: offset=%s", offset)


def _resolve_debug_dir(output_path: Path, config: StencilConfig) -> Path | None:
    if not config.debug_enabled:
        return None
    if not config.debug_dump_dir:
        return None
    base = Path(config.debug_dump_dir)
    if not base.is_absolute():
        base = Path.cwd() / base
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base
    except OSError:
        logger.warning("Failed to create debug dump dir: %s", base)
        return None


def _log_geometry(label: str, geom, detail: bool) -> None:
    if geom is None:
        logger.info("%s geometry: None", label)
        return
    if geom.is_empty:
        logger.info("%s geometry: empty", label)
        return
    poly_count = _count_polygons(geom)
    hole_count = _count_holes(geom)
    logger.info(
        "%s geometry: type=%s area=%.6f bounds=%s polygons=%s holes=%s",
        label,
        geom.geom_type,
        geom.area,
        geom.bounds,
        poly_count,
        hole_count,
    )
    if detail:
        try:
            valid = geom.is_valid
        except Exception:
            valid = None
        if valid is False:
            try:
                reason = explain_validity(geom)
            except Exception:
                reason = "unknown"
            logger.info("%s geometry validity: invalid (%s)", label, reason)
        elif valid is True:
            logger.info("%s geometry validity: ok", label)


def _dump_geometry(out_dir: Path | None, name: str, geom) -> None:
    if out_dir is None or geom is None or geom.is_empty:
        return
    safe = name.replace(" ", "_").lower()
    try:
        (out_dir / f"{safe}.wkt").write_text(geom.wkt, encoding="utf-8")
    except OSError:
        pass
    try:
        svg = _geometry_svg(geom, stroke="#1f2937")
        if svg:
            (out_dir / f"{safe}.svg").write_text(svg, encoding="utf-8")
    except OSError:
        pass
    try:
        png = _geometry_png(geom, stroke="#1f2937")
        if png is not None:
            png.save(out_dir / f"{safe}.png")
    except OSError:
        pass


def _geometry_svg(geom, stroke: str) -> str:
    if geom is None or geom.is_empty:
        return ""
    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= 0 or height <= 0:
        return ""
    padding = 2.0
    view = (
        bounds[0] - padding,
        bounds[1] - padding,
        width + padding * 2,
        height + padding * 2,
    )
    svg = geom.svg(scale_factor=1.0)
    svg = svg.replace(
        "<svg ",
        f"<svg viewBox=\"{view[0]} {view[1]} {view[2]} {view[3]}\" ",
    )
    svg = svg.replace(
        "fill=\"none\"",
        f"fill=\"none\" stroke=\"{stroke}\" stroke-width=\"0.1\"",
    )
    return svg


def _geometry_png(geom, stroke: str, target_size: int = 1024) -> Image.Image | None:
    if geom is None or geom.is_empty:
        return None
    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= 0 or height <= 0:
        return None
    scale = float(target_size) / max(width, height)
    padding = 10
    img_w = max(int(width * scale) + padding * 2, 1)
    img_h = max(int(height * scale) + padding * 2, 1)
    image = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(image)

    def map_point(point) -> tuple[float, float]:
        x, y = point
        px = (x - bounds[0]) * scale + padding
        py = (bounds[3] - y) * scale + padding
        return (px, py)

    def draw_poly(poly) -> None:
        exterior = [map_point(p) for p in poly.exterior.coords]
        if len(exterior) >= 2:
            draw.line(exterior, fill=stroke, width=2)
        for interior in poly.interiors:
            ring = [map_point(p) for p in interior.coords]
            if len(ring) >= 2:
                draw.line(ring, fill=stroke, width=1)

    def draw_line(line) -> None:
        coords = [map_point(p) for p in line.coords]
        if len(coords) >= 2:
            draw.line(coords, fill=stroke, width=1)

    def draw_point(point, color: str, radius: int = 4) -> None:
        px, py = map_point(point)
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), outline=color, width=2)

    def draw_geom(item) -> None:
        if item is None or item.is_empty:
            return
        if item.geom_type == "Polygon":
            draw_poly(item)
        elif item.geom_type == "MultiPolygon":
            for poly in item.geoms:
                draw_poly(poly)
        elif item.geom_type == "LineString":
            draw_line(item)
        elif item.geom_type == "MultiLineString":
            for line in item.geoms:
                draw_line(line)
        elif item.geom_type == "GeometryCollection":
            for sub in item.geoms:
                draw_geom(sub)

    draw_geom(geom)
    return image


def _geometry_png_with_markers(geom, points, stroke: str, marker: str) -> Image.Image | None:
    if geom is None or geom.is_empty:
        return None
    image = _geometry_png(geom, stroke=stroke)
    if image is None:
        return None
    draw = ImageDraw.Draw(image)
    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= 0 or height <= 0:
        return image
    scale = float(1024) / max(width, height)
    padding = 10

    def map_point(point) -> tuple[float, float]:
        x, y = point
        px = (x - bounds[0]) * scale + padding
        py = (bounds[3] - y) * scale + padding
        return (px, py)

    for point in points:
        px, py = map_point(point)
        draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline=marker, width=2)
    return image


def _dump_gko_paths_png(path: Path, out_dir: Path, px_per_mm: float = 10.0) -> None:
    segments = _parse_gko_paths(path)
    if not segments:
        return
    segments = _merge_colinear_segments(segments, tol=1e-6)
    points = []
    for segment, _ in segments:
        points.extend(segment)
    min_x = min(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_x = max(p[0] for p in points)
    max_y = max(p[1] for p in points)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return
    padding = 10
    img_w = max(int(width * px_per_mm) + padding * 2, 1)
    img_h = max(int(height * px_per_mm) + padding * 2, 1)
    image = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(image)
    colors = [
        "#1f2937",
        "#0f766e",
        "#7c2d12",
        "#1d4ed8",
        "#6d28d9",
        "#9f1239",
        "#15803d",
    ]

    def map_point(point):
        x, y = point
        px = (x - min_x) * px_per_mm + padding
        py = (max_y - y) * px_per_mm + padding
        return (px, py)

    for seg_idx, (segment, color_idx) in enumerate(segments):
        coords = [map_point(p) for p in segment]
        if len(coords) >= 2:
            draw.line(coords, fill=colors[color_idx % len(colors)], width=2)
            sx, sy = coords[0]
            ex, ey = coords[-1]
            color = colors[color_idx % len(colors)]
            jitter = 4.0
            angle = (seg_idx * 0.61803398875) % (2 * math.pi)
            ox = math.cos(angle) * jitter
            oy = math.sin(angle) * jitter
            draw.ellipse((sx + ox - 3, sy + oy - 3, sx + ox + 3, sy + oy + 3), fill=color, outline=color)
            draw.ellipse((ex - ox - 3, ey - oy - 3, ex - ox + 3, ey - oy + 3), fill=color, outline=color)
    gap = _max_gap_pair_from_segments(segments)
    if gap is not None:
        p1, p2, _ = gap
        for point in (p1, p2):
            px, py = map_point(point)
            draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline="#dc2626", width=2)
    image.save(out_dir / "step2_outline_segments_paths.png")
    image.save(out_dir / "step2_outline_segments_paths_deduped.png")


def _parse_gko_paths(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    scale = 1e5
    for line in text:
        if line.startswith("%FSLAX"):
            digits = line.strip("%*")
            parts = digits.replace("FSLAX", "").split("Y")
            if len(parts) == 2 and len(parts[0]) == 2:
                try:
                    scale = 10 ** int(parts[0][1])
                except ValueError:
                    pass
            break

    mode = "G01"
    current = None
    segments = []
    path_index = 0

    def parse_coord(line, key):
        if key not in line:
            return None
        idx = line.find(key) + 1
        num = []
        while idx < len(line) and (line[idx].isdigit() or line[idx] in "+-"):
            num.append(line[idx])
            idx += 1
        if not num:
            return None
        return int("".join(num)) / scale

    for raw in text:
        line = raw.strip()
        if not line or line.startswith("G04") or line.startswith("%") or line.startswith("M02"):
            continue
        if "G01" in line:
            mode = "G01"
        elif "G02" in line:
            mode = "G02"
        elif "G03" in line:
            mode = "G03"

        d01 = "D01" in line
        d02 = "D02" in line

        x = parse_coord(line, "X")
        y = parse_coord(line, "Y")
        i = parse_coord(line, "I")
        j = parse_coord(line, "J")
        if x is None and y is None and not d02 and not d01:
            continue
        if x is None and current is not None:
            x = current[0]
        if y is None and current is not None:
            y = current[1]
        if x is None or y is None:
            continue
        next_point = (x, y)
        if d02:
            current = next_point
            path_index += 1
            continue
        if d01 and current is not None:
            if mode in ("G02", "G03") and i is not None and j is not None:
                center = (current[0] + i, current[1] + j)
                arc = _arc_points_raw(current, next_point, center, mode == "G03", steps=64)
                segments.append((arc, path_index))
            else:
                segments.append(([current, next_point], path_index))
        current = next_point
    return segments


def _merge_intersections(segments):
    if not segments:
        return segments
    lines = []
    for seg, _ in segments:
        if len(seg) >= 2:
            lines.append(LineString(seg))
    if not lines:
        return segments
    merged = unary_union(lines)
    merged = linemerge(merged)
    flat = []
    if isinstance(merged, LineString):
        flat = [merged]
    elif hasattr(merged, "geoms"):
        flat = list(merged.geoms)
    merged_segments = [(list(line.coords), idx) for idx, line in enumerate(flat) if len(line.coords) >= 2]
    logger.info("Outline segments merged: %s -> %s", len(segments), len(merged_segments))
    return merged_segments


def _points_close(p1, p2, tol: float) -> bool:
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return (dx * dx + dy * dy) ** 0.5 <= tol


def _colinear(p1, p2, p3, tol: float) -> bool:
    dx1 = p2[0] - p1[0]
    dy1 = p2[1] - p1[1]
    dx2 = p3[0] - p2[0]
    dy2 = p3[1] - p2[1]
    cross = dx1 * dy2 - dy1 * dx2
    return abs(cross) <= tol


def _merge_colinear_segments(segments, tol: float):
    merged = []
    for seg, path_idx in segments:
        if not merged:
            merged.append((seg, path_idx))
            continue
        last_seg, last_idx = merged[-1]
        if (
            path_idx == last_idx
            and len(last_seg) == 2
            and len(seg) == 2
            and _points_close(last_seg[-1], seg[0], tol)
            and _colinear(last_seg[0], last_seg[1], seg[1], tol)
        ):
            merged[-1] = ([last_seg[0], seg[1]], path_idx)
        else:
            merged.append((seg, path_idx))
    return merged


def _segment_key(seg, tol: float):
    if len(seg) < 2:
        return None
    def r(p):
        return (round(p[0], 6), round(p[1], 6))
    first = r(seg[0])
    last = r(seg[-1])
    mid = r(seg[len(seg) // 2])
    ends = tuple(sorted((first, last)))
    return (ends, mid)


def _dedupe_segments(segments, tol: float):
    seen = set()
    kept = []
    removed = 0
    for seg, idx in segments:
        key = _segment_key(seg, tol)
        if key is None:
            continue
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        kept.append((seg, idx))
    return kept, removed


def _max_gap_pair_from_segments(segments):
    endpoints = []
    for segment, _ in segments:
        if len(segment) < 2:
            continue
        endpoints.append(segment[0])
        endpoints.append(segment[-1])
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


def _arc_points_raw(start, end, center, ccw: bool, steps: int = 64):
    sx, sy = start
    ex, ey = end
    cx, cy = center
    start_angle = math.atan2(sy - cy, sx - cx)
    end_angle = math.atan2(ey - cy, ex - cx)
    if ccw:
        if end_angle <= start_angle:
            end_angle += 2 * math.pi
        angles = [start_angle + (end_angle - start_angle) * i / (steps - 1) for i in range(steps)]
    else:
        if end_angle >= start_angle:
            end_angle -= 2 * math.pi
        angles = [start_angle + (end_angle - start_angle) * i / (steps - 1) for i in range(steps)]
    radius = math.hypot(sx - cx, sy - cy)
    return [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]


def _write_debug_svg(output_path: Path, outline, paste, stencil) -> None:
    if output_path is None:
        return
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, geom, color in (
        ("outline", outline, "#d64545"),
        ("paste", paste, "#2e7d32"),
        ("stencil", stencil, "#1e3a8a"),
    ):
        if geom is None or geom.is_empty:
            continue
        bounds = geom.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        if width <= 0 or height <= 0:
            continue
        padding = 2.0
        view = (
            bounds[0] - padding,
            bounds[1] - padding,
            width + padding * 2,
            height + padding * 2,
        )
        svg = geom.svg(scale_factor=1.0)
        svg = svg.replace(
            "<svg ",
            f"<svg viewBox=\"{view[0]} {view[1]} {view[2]} {view[3]}\" ",
        )
        svg = svg.replace(
            "fill=\"none\"",
            f"fill=\"none\" stroke=\"{color}\" stroke-width=\"0.1\"",
        )
        (out_dir / f"stencil_debug_{name}.svg").write_text(svg, encoding="utf-8")
