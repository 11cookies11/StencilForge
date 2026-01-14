from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
import logging
import shutil

from shapely.geometry import box
from shapely.ops import unary_union
import trimesh

from ..config import StencilConfig
from ..geometry import GerberGeometryService
from .cadquery import export_cadquery_stl
from .debug import (
    dump_geometry,
    dump_gko_paths_png,
    geometry_png_with_markers,
    log_geometry,
    resolve_debug_dir,
    write_debug_svg,
)
from .geometry import count_holes, extrude_geometry
from .locator import build_locator_bridge, build_locator_ring, build_locator_step
from .mesh import cleanup_mesh, translate_to_origin
from .qfn import regenerate_qfn_paste

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
    debug_dir = resolve_debug_dir(output_path, config)
    paste_files = _find_files(input_dir, config.paste_patterns)
    if not paste_files:
        raise FileNotFoundError("No paste layer files found in input directory.")
    if config.debug_enabled and config.debug_log_detail:
        logger.info("Paste files: %s", ", ".join(p.name for p in paste_files))
    logger.info("Paste layers: %s", ", ".join([p.name for p in paste_files]))
    paste_geom = geometry_service.load_paste_geometry(paste_files)
    if paste_geom is None or paste_geom.is_empty:
        raise ValueError("Paste layer produced empty geometry.")
    log_geometry("paste", paste_geom, config.debug_enabled and config.debug_log_detail)
    dump_geometry(debug_dir, "step2_paste", paste_geom)
    if config.qfn_regen_enabled:
        try:
            paste_geom = regenerate_qfn_paste(paste_geom, config)
        except Exception as exc:
            logger.warning("QFN regeneration skipped: %s", exc)

    paste_geom = paste_geom.buffer(
        config.paste_offset_mm, resolution=config.curve_resolution
    )
    if paste_geom.is_empty:
        raise ValueError("Paste offset produced empty geometry.")
    logger.info("Paste offset: %s mm", config.paste_offset_mm)
    log_geometry("paste_offset", paste_geom, config.debug_enabled and config.debug_log_detail)
    dump_geometry(debug_dir, "step2_paste_offset", paste_geom)

    outline_geom = None
    outline_files = _find_files(input_dir, config.outline_patterns)
    if outline_files:
        if debug_dir is not None:
            try:
                shutil.copy2(outline_files[0], debug_dir / "outline_source.gko")
            except OSError:
                logger.warning("Failed to copy outline source to debug dir.")
            try:
                dump_gko_paths_png(outline_files[0], debug_dir)
            except Exception as exc:
                logger.warning("Failed to render GKO paths: %s", exc)
        if debug_dir is not None and config.debug_enabled:
            try:
                outline_geom, outline_debug = geometry_service.load_outline_geometry_debug(outline_files[0])
                outline_segments = outline_debug.get("segments_geom")
                if outline_segments is not None:
                    dump_geometry(debug_dir, "step2_outline_segments", outline_segments)
                outline_loops = outline_debug.get("loops_geom")
                if outline_loops is not None:
                    dump_geometry(debug_dir, "step2_outline_segments_closed", outline_loops)
                max_gap = outline_debug.get("max_gap_pair")
                if outline_segments is not None and max_gap is not None:
                    points = [max_gap[0], max_gap[1]]
                    image = geometry_png_with_markers(
                        outline_segments,
                        points,
                        stroke="#1f2937",
                        marker="#dc2626",
                    )
                    if image is not None:
                        image.save(debug_dir / "step2_outline_segments_gap.png")
                snapped_segments = outline_debug.get("snapped_geom")
                if snapped_segments is not None:
                    dump_geometry(debug_dir, "step2_outline_segments_snapped", snapped_segments)
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
        outline_geom = _outline_from_paste(paste_geom, config.outline_margin_mm)
        logger.info("Outline fallback margin: %s mm", config.outline_margin_mm)
    else:
        log_geometry("outline", outline_geom, config.debug_enabled and config.debug_log_detail)
    dump_geometry(debug_dir, "step2_outline", outline_geom)
    dump_geometry(debug_dir, "step5_outline", outline_geom)

    logger.info("Output mode: %s", config.output_mode)
    if config.output_mode == "holes_only":
        stencil_2d = paste_geom
    else:
        stencil_2d = outline_geom.difference(paste_geom)
        hole_count = count_holes(stencil_2d)
        logger.info(
            "Stencil 2D: type=%s area=%.6f bounds=%s holes=%s",
            stencil_2d.geom_type,
            stencil_2d.area,
            stencil_2d.bounds if not stencil_2d.is_empty else None,
            hole_count,
        )
        write_debug_svg(output_path, outline_geom, paste_geom, stencil_2d)
        log_geometry("stencil_2d", stencil_2d, config.debug_enabled and config.debug_log_detail)
        dump_geometry(debug_dir, "step6_stencil_2d", stencil_2d)
    locator_bridge_geom = None
    if (
        config.locator_enabled
        and config.locator_mode == "step"
        and outline_geom is not None
        and not outline_geom.is_empty
        and config.locator_clearance_mm > 0
    ):
        locator_bridge_geom = build_locator_bridge(
            outline_geom,
            config.locator_clearance_mm,
            config.locator_open_side,
            config.locator_open_width_mm,
        )
        if locator_bridge_geom is not None and not locator_bridge_geom.is_empty:
            stencil_2d = unary_union([stencil_2d, locator_bridge_geom])
            logger.info(
                "Locator bridge: clearance=%s open=%s(%s)",
                config.locator_clearance_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )
            dump_geometry(debug_dir, "locator_bridge", locator_bridge_geom)

    logger.info("Base thickness: %s mm", config.thickness_mm)

    locator_geom = None
    locator_step_geom = None
    if config.locator_enabled and outline_geom is not None and not outline_geom.is_empty:
        if config.locator_mode == "step":
            locator_step_geom = build_locator_step(
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
                locator_geom = build_locator_ring(
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
            locator_geom = build_locator_ring(
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
        dump_geometry(debug_dir, "locator_step", locator_step_geom)
    if locator_geom is not None and not locator_geom.is_empty:
        dump_geometry(debug_dir, "locator_wall", locator_geom)

    if config.model_backend == "cadquery":
        export_cadquery_stl(stencil_2d, locator_geom, locator_step_geom, output_path, config)
        return

    mesh = extrude_geometry(stencil_2d, config.thickness_mm)
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_mesh = extrude_geometry(locator_geom, config.locator_height_mm)
        locator_mesh.apply_translation((0, 0, config.thickness_mm))
        mesh = trimesh.util.concatenate([mesh, locator_mesh])
    if locator_step_geom is not None and not locator_step_geom.is_empty and config.locator_step_height_mm > 0:
        step_mesh = extrude_geometry(locator_step_geom, config.locator_step_height_mm)
        step_mesh.apply_translation((0, 0, -config.locator_step_height_mm))
        mesh = trimesh.util.concatenate([mesh, step_mesh])

    logger.info("Cleaning mesh...")
    try:
        cleanup_mesh(mesh)
    except Exception as exc:
        logger.warning("Mesh cleanup failed: %s", exc)
    logger.info("Translating mesh to origin...")
    try:
        translate_to_origin(mesh)
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
