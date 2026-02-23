from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
import logging
import time

from shapely.geometry import box
from shapely.ops import unary_union

from ..config import StencilConfig
from ..geometry import GerberGeometryService
from .engine import EngineExportInput, get_model_engine
from .geometry import count_holes
from .locator import build_locator_bridge, build_locator_ring, build_locator_step
from .qfn import regenerate_qfn_paste

logger = logging.getLogger(__name__)

_PASTE_FALLBACK_PATTERNS = [
    "*gtp*",
    "*.gtp",
    "*gbp*",
    "*.gbp",
    "*paste*top*",
    "*top*paste*",
    "*paste*bottom*",
    "*bottom*paste*",
    "*tcream*",
    "*bcream*",
    "*cream*top*",
    "*cream*bottom*",
    "*smt*top*",
    "*smt*bottom*",
]


def generate_stencil(input_dir: Path, output_path: Path, config: StencilConfig) -> dict | None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    config.validate()
    geometry_service = GerberGeometryService(config)
    logger.info("Generating stencil from %s", input_dir)
    logger.info("Output STL: %s", output_path)
    overall_start = time.perf_counter()

    paste_files = _find_files(input_dir, config.paste_patterns)
    if not paste_files:
        paste_files = _find_files(input_dir, _PASTE_FALLBACK_PATTERNS)
        if paste_files:
            logger.warning(
                "Paste layer fallback matched %s file(s) using builtin patterns.",
                len(paste_files),
            )
    if not paste_files:
        seen = [p.name for p in sorted(input_dir.rglob("*")) if p.is_file()]
        preview = ", ".join(seen[:20]) if seen else "(no files)"
        raise FileNotFoundError(
            f"No paste layer files found in input directory. Seen: {preview}"
        )
    logger.info("Paste layers: %s", ", ".join([p.name for p in paste_files]))

    t0 = time.perf_counter()
    paste_geom = geometry_service.load_paste_geometry(paste_files)
    logger.info("Paste geometry loaded in %.3fs", time.perf_counter() - t0)
    if paste_geom is None or paste_geom.is_empty:
        raise ValueError("Paste layer produced empty geometry.")

    if config.qfn_regen_enabled:
        try:
            paste_geom = regenerate_qfn_paste(paste_geom, config)
        except Exception as exc:
            logger.warning("QFN regeneration skipped: %s", exc)

    t0 = time.perf_counter()
    paste_geom = paste_geom.buffer(config.paste_offset_mm, resolution=config.curve_resolution)
    logger.info("Paste offset geometry in %.3fs", time.perf_counter() - t0)
    if paste_geom.is_empty:
        raise ValueError("Paste offset produced empty geometry.")
    logger.info("Paste offset: %s mm", config.paste_offset_mm)

    outline_geom = None
    outline_debug: dict | None = None
    outline_files = _find_files(input_dir, config.outline_patterns)
    if outline_files:
        t0 = time.perf_counter()
        outline_geom = geometry_service.load_outline_geometry(outline_files[0])
        logger.info("Outline geometry loaded in %.3fs", time.perf_counter() - t0)
        outline_debug = geometry_service.get_last_outline_debug()
        logger.info("Outline layer: %s", outline_files[0].name)

    if outline_geom is None or outline_geom.is_empty:
        outline_geom = _outline_from_paste(paste_geom, config.outline_margin_mm)
        logger.info("Outline fallback margin: %s mm", config.outline_margin_mm)

    logger.info("Output mode: %s", config.output_mode)
    if config.output_mode == "holes_only":
        stencil_2d = paste_geom
    else:
        t0 = time.perf_counter()
        stencil_2d = outline_geom.difference(paste_geom)
        logger.info("Stencil 2D difference in %.3fs", time.perf_counter() - t0)
        hole_count = count_holes(stencil_2d)
        logger.info(
            "Stencil 2D: type=%s area=%.6f bounds=%s holes=%s",
            stencil_2d.geom_type,
            stencil_2d.area,
            stencil_2d.bounds if not stencil_2d.is_empty else None,
            hole_count,
        )

    locator_bridge_geom = None
    if (
        config.locator_enabled
        and config.locator_mode == "step"
        and outline_geom is not None
        and not outline_geom.is_empty
        and config.locator_clearance_mm > 0
    ):
        t0 = time.perf_counter()
        locator_bridge_geom = build_locator_bridge(
            outline_geom,
            config.locator_clearance_mm,
            config.locator_open_side,
            config.locator_open_width_mm,
        )
        logger.info("Locator bridge geometry in %.3fs", time.perf_counter() - t0)
        if locator_bridge_geom is not None and not locator_bridge_geom.is_empty:
            t0 = time.perf_counter()
            stencil_2d = unary_union([stencil_2d, locator_bridge_geom])
            logger.info("Locator bridge union in %.3fs", time.perf_counter() - t0)
            logger.info(
                "Locator bridge: clearance=%s open=%s(%s)",
                config.locator_clearance_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )

    logger.info("Base thickness: %s mm", config.thickness_mm)

    locator_geom = None
    locator_step_geom = None
    if config.locator_enabled and outline_geom is not None and not outline_geom.is_empty:
        if config.locator_mode == "step":
            t0 = time.perf_counter()
            locator_step_geom = build_locator_step(
                outline_geom,
                config.locator_clearance_mm,
                config.locator_step_width_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )
            logger.info("Locator step geometry in %.3fs", time.perf_counter() - t0)
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
                t0 = time.perf_counter()
                locator_geom = build_locator_ring(
                    outline_geom,
                    config.locator_clearance_mm,
                    config.locator_width_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )
                logger.info("Locator ring geometry in %.3fs", time.perf_counter() - t0)
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
            t0 = time.perf_counter()
            locator_geom = build_locator_ring(
                outline_geom,
                config.locator_clearance_mm,
                config.locator_width_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )
            logger.info("Locator ring geometry in %.3fs", time.perf_counter() - t0)
            if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
                logger.info(
                    "Locator wall: height=%s width=%s clearance=%s open=%s(%s)",
                    config.locator_height_mm,
                    config.locator_width_mm,
                    config.locator_clearance_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )

    backend = get_model_engine(config.model_backend)
    t0 = time.perf_counter()
    backend.export(
        EngineExportInput(
            stencil_2d=stencil_2d,
            locator_geom=locator_geom,
            locator_step_geom=locator_step_geom,
            output_path=output_path,
            config=config,
        )
    )
    logger.info("Backend '%s' export in %.3fs", backend.name, time.perf_counter() - t0)
    logger.info("Total pipeline time: %.3fs", time.perf_counter() - overall_start)
    return outline_debug


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
