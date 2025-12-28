from __future__ import annotations

from pathlib import Path
from fnmatch import fnmatch
import logging

from shapely.geometry import box, Polygon
from shapely.geometry.polygon import orient
from shapely.ops import unary_union, triangulate
import trimesh

from .config import StencilConfig
from .gerber_adapter import load_outline_geometry, load_paste_geometry

logger = logging.getLogger(__name__)


def generate_stencil(input_dir: Path, output_path: Path, config: StencilConfig) -> None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    config.validate()
    logger.info("Generating stencil from %s", input_dir)
    logger.info("Output STL: %s", output_path)
    paste_files = _find_files(input_dir, config.paste_patterns)
    if not paste_files:
        raise FileNotFoundError("No paste layer files found in input directory.")
    logger.info("Paste layers: %s", ", ".join([p.name for p in paste_files]))
    paste_geom = load_paste_geometry(paste_files, config)
    if paste_geom is None or paste_geom.is_empty:
        raise ValueError("Paste layer produced empty geometry.")
    logger.info(
        "Paste geometry: type=%s area=%.6f bounds=%s",
        paste_geom.geom_type,
        paste_geom.area,
        paste_geom.bounds,
    )

    paste_geom = paste_geom.buffer(
        config.paste_offset_mm, resolution=config.curve_resolution
    )
    if paste_geom.is_empty:
        raise ValueError("Paste offset produced empty geometry.")
    logger.info("Paste offset: %s mm", config.paste_offset_mm)

    outline_geom = None
    outline_files = _find_files(input_dir, config.outline_patterns)
    if outline_files:
        outline_geom = load_outline_geometry(outline_files[0], config)
        logger.info("Outline layer: %s", outline_files[0].name)

    if outline_geom is None or outline_geom.is_empty:
        outline_geom = _outline_from_paste(paste_geom, config.outline_margin_mm)
        logger.info("Outline fallback margin: %s mm", config.outline_margin_mm)
    else:
        logger.info(
            "Outline geometry: type=%s area=%.6f bounds=%s",
            outline_geom.geom_type,
            outline_geom.area,
            outline_geom.bounds,
        )

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
    logger.info("Base thickness: %s mm", config.thickness_mm)

    locator_geom = None
    if config.locator_enabled and outline_geom is not None and not outline_geom.is_empty:
        locator_geom = _build_locator_ring(
            outline_geom,
            config.locator_clearance_mm,
            config.locator_width_mm,
            config.locator_open_side,
            config.locator_open_width_mm,
        )
        if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
            logger.info(
                "Locator: height=%s width=%s clearance=%s open=%s(%s)",
                config.locator_height_mm,
                config.locator_width_mm,
                config.locator_clearance_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )

    if config.model_backend == "cadquery":
        _export_cadquery_stl(stencil_2d, locator_geom, output_path, config)
        return

    mesh = _extrude_geometry(stencil_2d, config.thickness_mm)
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_mesh = _extrude_geometry(locator_geom, config.locator_height_mm)
        locator_mesh.apply_translation((0, 0, config.thickness_mm))
        mesh = trimesh.util.concatenate([mesh, locator_mesh])

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


def _export_cadquery_stl(stencil_2d, locator_geom, output_path: Path, config: StencilConfig) -> None:
    try:
        import cadquery as cq
    except ImportError as exc:
        raise ImportError("CadQuery is required for model_backend=cadquery") from exc

    solids = _cadquery_extrude_geometry(stencil_2d, config.thickness_mm, cq)
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_solids = _cadquery_extrude_geometry(locator_geom, config.locator_height_mm, cq)
        for solid in locator_solids:
            solids.append(solid.translate((0, 0, config.thickness_mm)))

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
