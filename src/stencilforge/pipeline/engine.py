from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Protocol

import numpy as np
import trimesh
from shapely.geometry import MultiPolygon, Polygon
from shapely import constrained_delaunay_triangles
from shapely.ops import unary_union

from ..config import StencilConfig
from .cadquery import export_cadquery_stl
from .geometry import ensure_valid, extrude_geometry, orient_geometry
from .mesh import cleanup_mesh, translate_to_origin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineExportInput:
    stencil_2d: object
    locator_geom: object
    locator_step_geom: object
    output_path: object
    config: StencilConfig


class ModelEngine(Protocol):
    name: str

    def export(self, data: EngineExportInput) -> None:
        ...


class CadQueryEngine:
    name = "cadquery"

    def export(self, data: EngineExportInput) -> None:
        export_cadquery_stl(
            data.stencil_2d,
            data.locator_geom,
            data.locator_step_geom,
            data.output_path,
            data.config,
        )


class TrimeshEngine:
    name = "trimesh"

    def export(self, data: EngineExportInput) -> None:
        cfg = data.config

        t0 = time.perf_counter()
        mesh = extrude_geometry(data.stencil_2d, cfg.thickness_mm)
        logger.info("Base mesh extrusion in %.3fs", time.perf_counter() - t0)

        if data.locator_geom is not None and not data.locator_geom.is_empty and cfg.locator_height_mm > 0:
            t0 = time.perf_counter()
            locator_mesh = extrude_geometry(data.locator_geom, cfg.locator_height_mm)
            logger.info("Locator mesh extrusion in %.3fs", time.perf_counter() - t0)
            locator_mesh.apply_translation((0, 0, cfg.thickness_mm))
            mesh = trimesh.util.concatenate([mesh, locator_mesh])

        if (
            data.locator_step_geom is not None
            and not data.locator_step_geom.is_empty
            and cfg.locator_step_height_mm > 0
        ):
            t0 = time.perf_counter()
            step_mesh = extrude_geometry(data.locator_step_geom, cfg.locator_step_height_mm)
            logger.info("Locator step extrusion in %.3fs", time.perf_counter() - t0)
            step_mesh.apply_translation((0, 0, -cfg.locator_step_height_mm))
            mesh = trimesh.util.concatenate([mesh, step_mesh])

        logger.info("Cleaning mesh...")
        try:
            t0 = time.perf_counter()
            cleanup_mesh(mesh)
            logger.info("Mesh cleanup in %.3fs", time.perf_counter() - t0)
        except Exception as exc:
            logger.warning("Mesh cleanup failed: %s", exc)

        logger.info("Translating mesh to origin...")
        try:
            t0 = time.perf_counter()
            translate_to_origin(mesh)
            logger.info("Mesh translation in %.3fs", time.perf_counter() - t0)
        except Exception as exc:
            logger.warning("Mesh translation failed: %s", exc)

        data.output_path.parent.mkdir(parents=True, exist_ok=True)
        if mesh.is_empty or mesh.faces.size == 0:
            raise ValueError("Generated mesh is empty; check outline/paste geometry.")

        watertight = getattr(mesh, "is_watertight", None)
        euler = getattr(mesh, "euler_number", None)
        logger.info("Mesh stats: faces=%s watertight=%s euler=%s", mesh.faces.shape[0], watertight, euler)

        t0 = time.perf_counter()
        mesh.export(data.output_path, file_type="stl_ascii")
        logger.info("STL export write in %.3fs", time.perf_counter() - t0)

        try:
            size = data.output_path.stat().st_size
        except OSError:
            size = 0
        logger.info("STL size: %s bytes", size)
        if size <= 0:
            raise ValueError("Exported STL file is empty.")

        try:
            t0 = time.perf_counter()
            check_mesh = trimesh.load_mesh(data.output_path, force="mesh")
            faces = getattr(check_mesh, "faces", None)
            face_count = int(faces.shape[0]) if faces is not None else 0
            logger.info("STL reload check in %.3fs", time.perf_counter() - t0)
            logger.info("STL check: faces=%s", face_count)
            if face_count == 0:
                raise ValueError("Exported STL has no faces; check geometry.")
        except Exception as exc:
            raise ValueError(f"Failed to validate exported STL: {exc}") from exc

        logger.info("STL export complete")


class SfMeshEngine:
    name = "sfmesh"

    def export(self, data: EngineExportInput) -> None:
        cfg = data.config

        t0 = time.perf_counter()
        base_geom = _prepare_sfmesh_geometry(data.stencil_2d, cfg, preserve_holes=True)
        mesh = _extrude_with_cdt(base_geom, cfg.thickness_mm)
        logger.info("sfmesh base extrusion in %.3fs", time.perf_counter() - t0)

        if data.locator_geom is not None and not data.locator_geom.is_empty and cfg.locator_height_mm > 0:
            t0 = time.perf_counter()
            locator_geom = _prepare_sfmesh_geometry(data.locator_geom, cfg, preserve_holes=False)
            locator_mesh = _extrude_with_cdt(locator_geom, cfg.locator_height_mm)
            logger.info("sfmesh locator extrusion in %.3fs", time.perf_counter() - t0)
            locator_mesh.apply_translation((0, 0, cfg.thickness_mm))
            mesh = trimesh.util.concatenate([mesh, locator_mesh])

        if (
            data.locator_step_geom is not None
            and not data.locator_step_geom.is_empty
            and cfg.locator_step_height_mm > 0
        ):
            t0 = time.perf_counter()
            step_geom = _prepare_sfmesh_geometry(data.locator_step_geom, cfg, preserve_holes=False)
            step_mesh = _extrude_with_cdt(step_geom, cfg.locator_step_height_mm)
            logger.info("sfmesh locator step extrusion in %.3fs", time.perf_counter() - t0)
            step_mesh.apply_translation((0, 0, -cfg.locator_step_height_mm))
            mesh = trimesh.util.concatenate([mesh, step_mesh])

        critical_hole_width = _critical_hole_width_mm(base_geom, cfg.sfmesh_hole_protect_max_width_mm)
        if _should_attempt_watertight(mesh, cfg):
            t0 = time.perf_counter()
            pitch_mm = _adaptive_voxel_pitch(mesh, cfg, critical_hole_width)
            mesh = _rebuild_watertight_voxel(mesh, pitch_mm, cfg)
            logger.info(
                "sfmesh watertight rebuild in %.3fs (pitch=%s mm)",
                time.perf_counter() - t0,
                pitch_mm,
            )
        elif cfg.sfmesh_quality_mode in {"auto", "watertight"}:
            logger.info(
                "sfmesh watertight skipped: mode=%s faces=%s limit=%s watertight=%s",
                cfg.sfmesh_quality_mode,
                int(mesh.faces.shape[0]) if getattr(mesh, "faces", None) is not None else 0,
                cfg.sfmesh_watertight_face_limit,
                bool(getattr(mesh, "is_watertight", False)),
            )

        mesh = _maybe_decimate_mesh(mesh, cfg)

        logger.info("Cleaning mesh...")
        try:
            t0 = time.perf_counter()
            cleanup_mesh(mesh)
            _repair_mesh_topology(mesh)
            logger.info("Mesh cleanup in %.3fs", time.perf_counter() - t0)
        except Exception as exc:
            logger.warning("Mesh cleanup failed: %s", exc)

        logger.info("Translating mesh to origin...")
        try:
            t0 = time.perf_counter()
            translate_to_origin(mesh)
            logger.info("Mesh translation in %.3fs", time.perf_counter() - t0)
        except Exception as exc:
            logger.warning("Mesh translation failed: %s", exc)

        data.output_path.parent.mkdir(parents=True, exist_ok=True)
        if mesh.is_empty or mesh.faces.size == 0:
            raise ValueError("Generated mesh is empty; check outline/paste geometry.")

        watertight = getattr(mesh, "is_watertight", None)
        euler = getattr(mesh, "euler_number", None)
        logger.info("Mesh stats: faces=%s watertight=%s euler=%s", mesh.faces.shape[0], watertight, euler)

        t0 = time.perf_counter()
        mesh.export(data.output_path, file_type="stl")
        logger.info("STL export write (binary) in %.3fs", time.perf_counter() - t0)

        try:
            size = data.output_path.stat().st_size
        except OSError:
            size = 0
        logger.info("STL size: %s bytes", size)
        if size <= 0:
            raise ValueError("Exported STL file is empty.")

        try:
            t0 = time.perf_counter()
            check_mesh = trimesh.load_mesh(data.output_path, force="mesh")
            faces = getattr(check_mesh, "faces", None)
            face_count = int(faces.shape[0]) if faces is not None else 0
            logger.info("STL reload check in %.3fs", time.perf_counter() - t0)
            logger.info("STL check: faces=%s", face_count)
            if face_count == 0:
                raise ValueError("Exported STL has no faces; check geometry.")
        except Exception as exc:
            raise ValueError(f"Failed to validate exported STL: {exc}") from exc

        logger.info("STL export complete")


_ENGINES: dict[str, ModelEngine] = {
    "cadquery": CadQueryEngine(),
    "trimesh": TrimeshEngine(),
    "sfmesh": SfMeshEngine(),
}


def get_model_engine(name: str) -> ModelEngine:
    key = (name or "").strip().lower()
    if key == "sfmesh":
        logger.warning("Backend 'sfmesh' is deprecated and mapped to 'trimesh'.")
        key = "trimesh"
    engine = _ENGINES.get(key)
    if engine is None:
        supported = ", ".join(sorted(_ENGINES.keys()))
        raise ValueError(f"Unsupported model backend '{name}'. Supported: {supported}")
    return engine


def _extrude_with_cdt(geometry, thickness_mm: float) -> trimesh.Trimesh:
    geometry = ensure_valid(geometry)
    geometry = orient_geometry(geometry)
    if geometry.is_empty:
        raise ValueError("Geometry is empty after preprocessing.")

    polygons = []
    if geometry.geom_type == "Polygon":
        polygons = [geometry]
    elif geometry.geom_type == "MultiPolygon":
        polygons = [poly for poly in geometry.geoms if poly.area > 0]
    else:
        merged = unary_union([geometry])
        if merged.geom_type == "Polygon":
            polygons = [merged]
        elif merged.geom_type == "MultiPolygon":
            polygons = [poly for poly in merged.geoms if poly.area > 0]

    meshes: list[trimesh.Trimesh] = []
    for poly in polygons:
        poly = ensure_valid(poly)
        if poly.is_empty or poly.area <= 0:
            continue
        meshes.append(_extrude_polygon_with_cdt(poly, thickness_mm))

    if not meshes:
        raise ValueError("Failed to create STL mesh from geometry.")
    mesh = trimesh.util.concatenate(meshes)
    if mesh.is_empty or mesh.faces.size == 0:
        raise ValueError("Failed to create non-empty STL mesh from geometry.")
    return mesh


def _extrude_polygon_with_cdt(poly, thickness_mm: float) -> trimesh.Trimesh:
    triangles = constrained_delaunay_triangles(poly)
    if triangles is None or triangles.is_empty:
        return extrude_geometry(poly, thickness_mm)

    tri_list = []
    if triangles.geom_type == "Polygon":
        tri_list = [triangles]
    elif triangles.geom_type == "MultiPolygon":
        tri_list = list(triangles.geoms)
    else:
        return extrude_geometry(poly, thickness_mm)
    tri_list = [tri for tri in tri_list if tri.area > 0 and poly.covers(tri.representative_point())]
    covered_area = sum(tri.area for tri in tri_list)
    coverage = covered_area / poly.area if poly.area > 0 else 0.0
    if coverage < 0.995:
        logger.warning(
            "sfmesh CDT coverage low: poly_area=%.6f kept=%.6f coverage=%.3f",
            float(poly.area),
            float(covered_area),
            float(coverage),
        )
        return extrude_geometry(poly, thickness_mm)

    vertices = []
    faces = []
    vertex_index = {}

    def add_vertex(x: float, y: float, z: float) -> int:
        key = (float(x), float(y), float(z))
        idx = vertex_index.get(key)
        if idx is None:
            idx = len(vertices)
            vertices.append(key)
            vertex_index[key] = idx
        return idx

    for tri in tri_list:
        coords = list(tri.exterior.coords)
        if len(coords) < 4:
            continue
        p0, p1, p2 = coords[0], coords[1], coords[2]
        top = [
            add_vertex(p0[0], p0[1], thickness_mm),
            add_vertex(p1[0], p1[1], thickness_mm),
            add_vertex(p2[0], p2[1], thickness_mm),
        ]
        bottom = [
            add_vertex(p0[0], p0[1], 0.0),
            add_vertex(p1[0], p1[1], 0.0),
            add_vertex(p2[0], p2[1], 0.0),
        ]
        faces.append(top)
        faces.append(bottom[::-1])

    for ring in [poly.exterior]:
        coords = list(ring.coords)
        if len(coords) < 2:
            continue
        if coords[0] == coords[-1]:
            coords = coords[:-1]
        _append_side_faces(coords, thickness_mm, add_vertex, faces, reverse=False)

    for ring in poly.interiors:
        coords = list(ring.coords)
        if len(coords) < 2:
            continue
        if coords[0] == coords[-1]:
            coords = coords[:-1]
        # Hole side walls need opposite winding from exterior wall.
        _append_side_faces(coords, thickness_mm, add_vertex, faces, reverse=True)

    if not faces:
        return extrude_geometry(poly, thickness_mm)
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _append_side_faces(coords, thickness_mm: float, add_vertex, faces: list[list[int]], reverse: bool) -> None:
    if len(coords) < 2:
        return
    for i in range(len(coords)):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % len(coords)]
        v1 = add_vertex(x1, y1, 0.0)
        v2 = add_vertex(x2, y2, 0.0)
        v3 = add_vertex(x2, y2, thickness_mm)
        v4 = add_vertex(x1, y1, thickness_mm)
        if reverse:
            faces.append([v1, v3, v2])
            faces.append([v1, v4, v3])
        else:
            faces.append([v1, v2, v3])
            faces.append([v1, v3, v4])


def _prepare_sfmesh_geometry(geometry, cfg: StencilConfig, preserve_holes: bool):
    geometry = ensure_valid(geometry)
    geometry = orient_geometry(geometry)
    if geometry.is_empty:
        return geometry
    if cfg.sfmesh_simplify_tol_mm > 0:
        geometry = geometry.simplify(cfg.sfmesh_simplify_tol_mm, preserve_topology=True)
    geometry = ensure_valid(geometry)
    if geometry.is_empty:
        return geometry
    return _filter_polygon_noise(
        geometry,
        min_polygon_area=cfg.sfmesh_min_polygon_area_mm2,
        min_hole_area=cfg.sfmesh_min_hole_area_mm2 if preserve_holes else float("inf"),
    )


def _filter_polygon_noise(geometry, min_polygon_area: float, min_hole_area: float):
    if geometry.is_empty:
        return geometry
    polygons: list[Polygon] = []
    if isinstance(geometry, Polygon):
        polygons = [_clean_single_polygon(geometry, min_hole_area)]
    elif isinstance(geometry, MultiPolygon):
        polygons = [_clean_single_polygon(poly, min_hole_area) for poly in geometry.geoms]
    else:
        unioned = unary_union([geometry])
        if isinstance(unioned, Polygon):
            polygons = [_clean_single_polygon(unioned, min_hole_area)]
        elif isinstance(unioned, MultiPolygon):
            polygons = [_clean_single_polygon(poly, min_hole_area) for poly in unioned.geoms]
    kept = [poly for poly in polygons if poly is not None and not poly.is_empty and poly.area >= min_polygon_area]
    if not kept:
        return geometry
    if len(kept) == 1:
        return kept[0]
    return MultiPolygon(kept)


def _clean_single_polygon(poly: Polygon, min_hole_area: float) -> Polygon:
    shell = list(poly.exterior.coords)
    holes = []
    for ring in poly.interiors:
        ring_poly = Polygon(ring)
        if ring_poly.area >= min_hole_area:
            holes.append(list(ring.coords))
    cleaned = Polygon(shell, holes=holes)
    return ensure_valid(cleaned)


def _should_attempt_watertight(mesh: trimesh.Trimesh, cfg: StencilConfig) -> bool:
    if cfg.sfmesh_quality_mode == "fast":
        return False
    face_count = int(mesh.faces.shape[0]) if getattr(mesh, "faces", None) is not None else 0
    if face_count <= 0:
        return False
    if face_count > cfg.sfmesh_watertight_face_limit:
        return False
    watertight = bool(getattr(mesh, "is_watertight", False))
    if cfg.sfmesh_quality_mode == "auto":
        return not watertight
    return True


def _critical_hole_width_mm(geometry, max_width_mm: float) -> float | None:
    if geometry is None or geometry.is_empty:
        return None
    polygons: list[Polygon] = []
    if isinstance(geometry, Polygon):
        polygons = [geometry]
    elif isinstance(geometry, MultiPolygon):
        polygons = list(geometry.geoms)
    min_width = None
    for poly in polygons:
        for ring in poly.interiors:
            hole = Polygon(ring)
            if hole.is_empty:
                continue
            width = min(float(hole.bounds[2] - hole.bounds[0]), float(hole.bounds[3] - hole.bounds[1]))
            if width <= 0:
                continue
            if width > max_width_mm:
                continue
            min_width = width if min_width is None else min(min_width, width)
    return min_width


def _adaptive_voxel_pitch(mesh: trimesh.Trimesh, cfg: StencilConfig, critical_hole_width: float | None = None) -> float:
    pitch = float(cfg.sfmesh_voxel_pitch_mm)
    if not cfg.sfmesh_adaptive_pitch_enabled:
        return pitch
    bounds = getattr(mesh, "bounds", None)
    if bounds is None:
        return pitch
    extents = np.asarray(bounds[1]) - np.asarray(bounds[0])
    longest = float(np.max(extents)) if extents.size else 0.0
    if longest > 180:
        pitch *= 3.0
    elif longest > 120:
        pitch *= 2.4
    elif longest > 80:
        pitch *= 2.0
    elif longest > 50:
        pitch *= 1.6
    pitch = float(np.clip(pitch, cfg.sfmesh_adaptive_pitch_min_mm, cfg.sfmesh_adaptive_pitch_max_mm))
    if cfg.sfmesh_hole_protect_enabled and critical_hole_width is not None:
        cap = max(cfg.sfmesh_adaptive_pitch_min_mm, critical_hole_width / cfg.sfmesh_hole_pitch_divisor)
        if pitch > cap:
            logger.info(
                "sfmesh hole-protect pitch cap: %.4f -> %.4f (critical_hole=%.4f mm)",
                pitch,
                cap,
                critical_hole_width,
            )
            pitch = cap
    return pitch


def _maybe_decimate_mesh(mesh: trimesh.Trimesh, cfg: StencilConfig) -> trimesh.Trimesh:
    ratio = float(cfg.sfmesh_decimate_target_ratio)
    if ratio >= 1.0:
        return mesh
    face_count = int(mesh.faces.shape[0]) if getattr(mesh, "faces", None) is not None else 0
    if face_count < 2000:
        return mesh
    target_faces = max(500, int(face_count * ratio))
    try:
        decimated = mesh.simplify_quadric_decimation(target_faces)
    except Exception as exc:
        logger.warning("sfmesh decimation skipped: %s", exc)
        return mesh
    if decimated is None or decimated.is_empty or decimated.faces.size == 0:
        return mesh
    logger.info(
        "sfmesh decimation: faces %s -> %s (ratio=%.3f)",
        face_count,
        int(decimated.faces.shape[0]),
        ratio,
    )
    return decimated


def _repair_mesh_topology(mesh: trimesh.Trimesh) -> None:
    # Strengthen sfmesh output topology before export.
    try:
        trimesh.repair.fix_winding(mesh)
    except Exception:
        pass
    try:
        trimesh.repair.fix_normals(mesh)
    except Exception:
        pass
    try:
        trimesh.repair.fix_inversion(mesh)
    except Exception:
        pass
    try:
        trimesh.repair.fill_holes(mesh)
    except Exception:
        pass
    if hasattr(mesh, "merge_vertices"):
        mesh.merge_vertices(digits_vertex=6)
    if hasattr(mesh, "remove_duplicate_faces"):
        mesh.remove_duplicate_faces()
    if hasattr(mesh, "remove_degenerate_faces"):
        mesh.remove_degenerate_faces()
    if hasattr(mesh, "remove_unreferenced_vertices"):
        mesh.remove_unreferenced_vertices()
    # Snap tiny float noise after heavy operations.
    if mesh.vertices is not None and len(mesh.vertices) > 0:
        mesh.vertices = np.round(mesh.vertices, 6)


def _rebuild_watertight_voxel(mesh: trimesh.Trimesh, pitch_mm: float, cfg: StencilConfig) -> trimesh.Trimesh:
    if mesh.is_empty or mesh.faces.size == 0:
        return mesh
    if cfg.sfmesh_chunked_watertight_enabled:
        chunked = _rebuild_watertight_chunked(mesh, pitch_mm, cfg)
        if chunked is not None:
            return chunked
    return _rebuild_watertight_single(mesh, pitch_mm)


def _rebuild_watertight_single(mesh: trimesh.Trimesh, pitch_mm: float) -> trimesh.Trimesh:
    if mesh.is_empty or mesh.faces.size == 0:
        return mesh
    target_bounds = np.array(mesh.bounds, dtype=float) if mesh.bounds is not None else None
    try:
        voxel = mesh.voxelized(pitch=pitch_mm)
        try:
            voxel = voxel.fill()
        except Exception:
            pass
        rebuilt = voxel.marching_cubes
    except ModuleNotFoundError as exc:
        logger.warning("sfmesh watertight mode fallback (missing dependency): %s", exc)
        return mesh
    except Exception as exc:
        logger.warning("sfmesh watertight rebuild failed, fallback to fast mesh: %s", exc)
        return mesh
    if rebuilt is None or rebuilt.is_empty or rebuilt.faces.size == 0:
        return mesh
    # marching_cubes vertices are in voxel index coordinates; map them back.
    try:
        rebuilt.apply_transform(voxel.transform)
    except Exception:
        pass
    if target_bounds is not None:
        _fit_mesh_to_bounds(rebuilt, target_bounds)
    return rebuilt


def _rebuild_watertight_chunked(
    mesh: trimesh.Trimesh, pitch_mm: float, cfg: StencilConfig
) -> trimesh.Trimesh | None:
    bounds = np.array(mesh.bounds, dtype=float) if mesh.bounds is not None else None
    if bounds is None:
        return None
    min_x, min_y = float(bounds[0][0]), float(bounds[0][1])
    max_x, max_y = float(bounds[1][0]), float(bounds[1][1])
    chunk_size = float(cfg.sfmesh_chunk_size_mm)
    if (max_x - min_x) <= chunk_size and (max_y - min_y) <= chunk_size:
        return None

    overlap = float(cfg.sfmesh_chunk_overlap_mm)
    x_edges = list(np.arange(min_x, max_x, chunk_size))
    y_edges = list(np.arange(min_y, max_y, chunk_size))
    if not x_edges:
        x_edges = [min_x]
    if not y_edges:
        y_edges = [min_y]
    if x_edges[-1] < max_x:
        x_edges.append(max_x)
    if y_edges[-1] < max_y:
        y_edges.append(max_y)

    chunk_meshes: list[trimesh.Trimesh] = []
    chunk_total = 0
    chunk_ok = 0
    for xi in range(len(x_edges) - 1):
        for yi in range(len(y_edges) - 1):
            cx0 = x_edges[xi]
            cx1 = x_edges[xi + 1]
            cy0 = y_edges[yi]
            cy1 = y_edges[yi + 1]
            chunk_total += 1
            sx0 = max(min_x, cx0 - overlap)
            sx1 = min(max_x, cx1 + overlap)
            sy0 = max(min_y, cy0 - overlap)
            sy1 = min(max_y, cy1 + overlap)
            part = _clip_mesh_xy(mesh, sx0, sy0, sx1, sy1)
            if part is None:
                part = _submesh_xy_intersection(mesh, sx0, sy0, sx1, sy1)
            if part is None:
                continue
            rebuilt = _rebuild_watertight_single(part, pitch_mm)
            if rebuilt is None or rebuilt.is_empty or rebuilt.faces.size == 0:
                continue
            cropped = _clip_mesh_xy(rebuilt, cx0, cy0, cx1, cy1)
            if cropped is None:
                cropped = _submesh_xy_intersection(rebuilt, cx0, cy0, cx1, cy1)
            if cropped is None:
                continue
            chunk_meshes.append(cropped)
            chunk_ok += 1

    if not chunk_meshes:
        logger.warning("sfmesh chunked watertight produced no chunks, fallback to single")
        return None

    merged = trimesh.util.concatenate(chunk_meshes)
    _repair_mesh_topology(merged)
    if not bool(getattr(merged, "is_watertight", False)):
        # Chunk overlap may leave seam artifacts. Run a coarse global seal pass.
        seal_pitch = min(cfg.sfmesh_adaptive_pitch_max_mm, max(pitch_mm, pitch_mm * 1.25))
        logger.info(
            "sfmesh chunked seam-seal pass: pitch %.4f -> %.4f",
            pitch_mm,
            seal_pitch,
        )
        sealed = _rebuild_watertight_single(merged, seal_pitch)
        if sealed is not None and not sealed.is_empty and sealed.faces.size > 0:
            merged = sealed
            _repair_mesh_topology(merged)
    logger.info(
        "sfmesh chunked watertight: chunks=%s ok=%s size=%.1f overlap=%.3f",
        chunk_total,
        chunk_ok,
        chunk_size,
        overlap,
    )
    return merged


def _submesh_xy_intersection(
    mesh: trimesh.Trimesh, x0: float, y0: float, x1: float, y1: float
) -> trimesh.Trimesh | None:
    if mesh.is_empty or mesh.faces.size == 0:
        return None
    tris = mesh.vertices[mesh.faces]
    tri_min = tris[:, :, :2].min(axis=1)
    tri_max = tris[:, :, :2].max(axis=1)
    mask = (
        (tri_max[:, 0] >= x0)
        & (tri_min[:, 0] <= x1)
        & (tri_max[:, 1] >= y0)
        & (tri_min[:, 1] <= y1)
    )
    idx = np.nonzero(mask)[0]
    if idx.size == 0:
        return None
    sub = mesh.submesh([idx], append=True, repair=False)
    if sub is None or sub.is_empty or sub.faces.size == 0:
        return None
    return sub


def _clip_mesh_xy(mesh: trimesh.Trimesh, x0: float, y0: float, x1: float, y1: float) -> trimesh.Trimesh | None:
    if mesh.is_empty or mesh.faces.size == 0:
        return None
    clipped = mesh.copy()
    planes = [
        (np.array([1.0, 0.0, 0.0]), np.array([x0, 0.0, 0.0])),   # x >= x0
        (np.array([-1.0, 0.0, 0.0]), np.array([x1, 0.0, 0.0])),  # x <= x1
        (np.array([0.0, 1.0, 0.0]), np.array([0.0, y0, 0.0])),   # y >= y0
        (np.array([0.0, -1.0, 0.0]), np.array([0.0, y1, 0.0])),  # y <= y1
    ]
    try:
        for normal, origin in planes:
            clipped = trimesh.intersections.slice_mesh_plane(
                clipped,
                plane_normal=normal,
                plane_origin=origin,
                cap=False,
            )
            if clipped is None or clipped.is_empty or clipped.faces.size == 0:
                return None
    except Exception:
        return None
    return clipped


def _fit_mesh_to_bounds(mesh: trimesh.Trimesh, target_bounds: np.ndarray) -> None:
    if mesh.is_empty or mesh.vertices is None or len(mesh.vertices) == 0:
        return
    cur_bounds = np.array(mesh.bounds, dtype=float)
    cur_extents = cur_bounds[1] - cur_bounds[0]
    tgt_extents = target_bounds[1] - target_bounds[0]
    scale = np.ones(3, dtype=float)
    for i in range(3):
        if cur_extents[i] > 1e-12 and tgt_extents[i] > 0:
            scale[i] = tgt_extents[i] / cur_extents[i]
    mesh.vertices = (mesh.vertices - cur_bounds[0]) * scale + target_bounds[0]
