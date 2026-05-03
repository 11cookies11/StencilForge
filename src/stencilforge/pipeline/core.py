from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
import logging
import time

from shapely.affinity import scale as scale_geometry
from shapely.geometry import box
from shapely.ops import unary_union

from ..aperture_workspace import resolve_aperture_workspace_effect
from ..config import StencilConfig
from ..geometry import GerberGeometryService
from ..geometry.service import flatten_to_polygons
from .engine import EngineExportInput, ModelEngine, get_model_engine
from .geometry import count_holes
from .locator import build_locator_bridge, build_locator_ring, build_locator_step
from .pad_classifier import classify_pads
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

_BOTTOM_PASTE_MARKERS = ["gbp", "bottom", "bcream"]

_MASK_FALLBACK_PATTERNS = [
    "*gts*",
    "*.gts",
    "*gbs*",
    "*.gbs",
    "*soldermask*top*",
    "*top*soldermask*",
    "*soldermask*bottom*",
    "*bottom*soldermask*",
    "*solder*mask*top*",
    "*top*solder*mask*",
    "*solder*mask*bottom*",
    "*bottom*solder*mask*",
]

_BOTTOM_MASK_MARKERS = ["gbs", "bottom", "bmask"]

_OUTLINE_FALLBACK_PATTERNS = [
    "*gko*",
    "*.gko",
    "*gm1*",
    "*.gm1",
    "*boardoutline*",
    "*outline*",
    "*edge*cuts*",
    "*edge-cuts*",
    "*edgecuts*",
]


def generate_stencil(
    input_dir: Path,
    output_path: Path,
    config: StencilConfig,
    aperture_workspace: dict | None = None,
    *,
    geometry_service: GerberGeometryService | None = None,
    model_engine: ModelEngine | None = None,
) -> dict | None:
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    config.validate()
    if geometry_service is None:
        geometry_service = GerberGeometryService(config)
    if model_engine is None:
        model_engine = get_model_engine(config.model_backend)

    sides = ["top", "bottom"] if config.paste_side == "both" else [config.paste_side]
    last_debug = None
    for side in sides:
        stem = output_path.stem
        suffix = f"_{side}" if len(sides) > 1 else ""
        side_path = output_path.with_stem(f"{stem}{suffix}")
        _generate_stencil_side(
            input_dir=input_dir,
            output_path=side_path,
            config=config,
            side=side,
            geometry_service=geometry_service,
            model_engine=model_engine,
            aperture_workspace=aperture_workspace,
        )
    return last_debug


def _generate_stencil_side(
    *,
    input_dir: Path,
    output_path: Path,
    config: StencilConfig,
    side: str,
    geometry_service: GerberGeometryService,
    model_engine: ModelEngine,
    aperture_workspace: dict | None,
) -> dict | None:
    logger.info("Generating stencil from %s", input_dir)
    logger.info("Output STL: %s", output_path)
    logger.info("Paste side: %s", side)
    overall_start = time.perf_counter()

    opening_files = _find_files(input_dir, _MASK_FALLBACK_PATTERNS)
    opening_files = _filter_mask_side(opening_files, side)
    opening_source = "solder_mask"
    other_side_info = _side_availability_note(
        _find_files(input_dir, _MASK_FALLBACK_PATTERNS),
        side,
        _filter_mask_side,
        "mask",
    )

    if not opening_files:
        paste_files = _find_files(input_dir, config.paste_patterns)
        if not paste_files:
            paste_files = _find_files(input_dir, _PASTE_FALLBACK_PATTERNS)
            if paste_files:
                logger.warning(
                    "Paste layer fallback matched %s file(s) using builtin patterns.",
                    len(paste_files),
                )
        opening_files = _filter_paste_side(paste_files, side)
        opening_source = "paste"
        other_side_info = _side_availability_note(
            paste_files,
            side,
            _filter_paste_side,
            "paste",
        )

    if not opening_files:
        seen = [p.name for p in sorted(input_dir.rglob("*")) if p.is_file()]
        preview = ", ".join(seen[:20]) if seen else "(no files)"
        raise FileNotFoundError(
            f"No solder mask or paste files found for side '{side}'. Seen: {preview}"
        )

    logger.info("Opening source: %s", opening_source)
    logger.info("Opening layers: %s", ", ".join([p.name for p in opening_files]))
    if other_side_info:
        logger.info("Opening side note: %s", other_side_info)

    t0 = time.perf_counter()
    geometry_label = "solder mask" if opening_source == "solder_mask" else "paste"
    paste_geom = geometry_service.load_paste_geometry(opening_files, label=geometry_label)
    logger.info("Opening geometry loaded in %.3fs", time.perf_counter() - t0)

    if paste_geom is None or paste_geom.is_empty:
        raise ValueError("No pad geometry found.")

    if opening_source == "solder_mask" and config.mask_opening_scale != 1.0:
        paste_geom = scale_geometry(
            paste_geom,
            xfact=config.mask_opening_scale,
            yfact=config.mask_opening_scale,
            origin="centroid",
        )
        logger.info("Mask opening scale: %.3f", config.mask_opening_scale)

    if config.qfn_regen_enabled:
        try:
            paste_geom = regenerate_qfn_paste(paste_geom, config)
        except Exception as exc:
            logger.warning("QFN regeneration skipped: %s", exc)

    # --- drill detection & per-pad classification ---
    drill_files = _find_files(input_dir, config.drill_patterns)
    if drill_files:
        logger.info("Drill files: %s", ", ".join([p.name for p in drill_files]))
    drill_holes = geometry_service.load_drill_holes(drill_files) if drill_files else []

    paste_polygons = flatten_to_polygons(paste_geom)
    pad_infos = classify_pads(paste_polygons, drill_holes)
    pad_summary: dict[str, int] = {}
    if pad_infos:
        from .pad_classifier import classification_summary
        pad_summary = classification_summary(pad_infos)
        logger.info("Pad classification: %s", pad_summary)

    if aperture_workspace is not None:
        if pad_infos:
            # Per-class rule application
            _apply_per_class_aperture(
                pad_infos, aperture_workspace, config
            )
            paste_geom = unary_union([pi.polygon for pi in pad_infos])
            logger.info("Aperture workspace applied per pad type.")
        else:
            # Global fallback: apply one rule to the entire merged geometry
            paste_geom = _apply_global_aperture(
                paste_geom, aperture_workspace, config
            )

    t0 = time.perf_counter()
    paste_geom = paste_geom.buffer(config.paste_offset_mm, resolution=config.curve_resolution)
    logger.info("Paste offset geometry in %.3fs", time.perf_counter() - t0)
    if paste_geom.is_empty:
        raise ValueError("Paste offset produced empty geometry.")
    logger.info("Paste offset: %s mm", config.paste_offset_mm)

    outline_geom = None
    outline_debug: dict | None = None
    logger.info("Outline patterns: %s", ", ".join(config.outline_patterns) if config.outline_patterns else "(none)")
    outline_files = _find_files(input_dir, config.outline_patterns)
    if not outline_files:
        outline_files = _find_files(input_dir, _OUTLINE_FALLBACK_PATTERNS)
        if outline_files:
            logger.warning(
                "Outline fallback matched %s file(s) using builtin patterns.",
                len(outline_files),
            )
    if outline_files:
        logger.info(
            "Outline matches (%s): %s",
            len(outline_files),
            ", ".join(path.name for path in outline_files),
        )
    else:
        scanned = [p.name for p in sorted(input_dir.rglob("*")) if p.is_file()]
        logger.warning(
            "No outline files matched patterns. scanned=%s sample=%s",
            len(scanned),
            ", ".join(scanned[:20]) if scanned else "(no files)",
        )
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

    logger.info("Base thickness: %s mm", config.effective_thickness_mm)
    if config.thickness_managed_by_printer_profile:
        logger.info(
            "FSM profile manages thickness: user=%s mm effective=%s mm",
            config.thickness_mm,
            config.effective_thickness_mm,
        )

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

    t0 = time.perf_counter()
    model_engine.export(
        EngineExportInput(
            stencil_2d=stencil_2d,
            locator_geom=locator_geom,
            locator_step_geom=locator_step_geom,
            output_path=output_path,
            config=config,
        )
    )
    export_elapsed = time.perf_counter() - t0
    total_elapsed = time.perf_counter() - overall_start
    logger.info("Backend '%s' export in %.3fs", model_engine.name, export_elapsed)
    logger.info("Total pipeline time: %.3fs", total_elapsed)

    report = _build_stencil_report(
        input_dir=input_dir,
        output_path=output_path,
        side=side,
        opening_source=opening_source,
        config=config,
        opening_files=opening_files,
        paste_geom=paste_geom,
        pad_summary=pad_summary,
        outline_files=outline_files,
        outline_geom=outline_geom,
        drill_count=len(drill_holes),
        has_outline_fallback=(outline_geom is not None and not outline_files),
        model_backend=model_engine.name,
        elapsed_s=total_elapsed,
        other_side_info=other_side_info,
    )
    _write_stencil_report(output_path, report)
    return outline_debug


def _apply_per_class_aperture(
    pad_infos,
    aperture_workspace: dict,
    config: StencilConfig,
) -> None:
    """Apply aperture effects per pad type, using actual polygon dimensions
    to drive the solder-volume calculator and rule engine."""
    from copy import deepcopy
    from .pad_classifier import aggregate_pad_metrics

    metrics = aggregate_pad_metrics(pad_infos)

    for pad_type, dims in sorted(metrics.items()):
        ws_for_type = deepcopy(aperture_workspace)
        ws_for_type["padType"] = pad_type
        ws_for_type["padWidthMm"] = dims["padWidthMm"]
        ws_for_type["padHeightMm"] = dims["padHeightMm"]
        ws_for_type["padAreaMm2"] = dims["padAreaMm2"]
        ws_for_type["targetVolumeMm3"] = 0.0  # let calculator derive from actual dimensions

        effect_info = resolve_aperture_workspace_effect(ws_for_type, config.effective_thickness_mm)
        effect = effect_info["effect"]
        snapshot = effect_info["snapshot"]

        # Detect fallback: the matched rule doesn't actually target this pad type
        matched_rule = snapshot.get("matchedRule") or {}
        matched_pad_type = str(matched_rule.get("match", {}).get("padType", ""))
        rule_genuinely_matches = (
            matched_pad_type.casefold() in ("any", pad_type.casefold())
        )

        if rule_genuinely_matches and effect["enabled"]:
            mode = effect["mode"]
            scale_factor = float(effect.get("scale", 1.0) or 1.0)
            delta_mm = float(effect.get("deltaMm", 0.0) or 0.0)
            source = f"rule: {effect_info['matchSummary']} -> {effect_info['actionSummary']}"
        else:
            # No rule targets this pad type; use volume-calculator recommendation
            mode = "scale"
            scale_factor = float(snapshot.get("recommendedScale", 1.0) or 1.0)
            delta_mm = float(snapshot.get("recommendedDeltaMm", 0.0) or 0.0)
            if effect["enabled"]:
                source = (
                    f"calculator ({effect_info['matchSummary']} inapplicable, "
                    f"using recommended scale={scale_factor:.3f})"
                )
            else:
                source = (
                    f"calculator (rule disabled, using recommended "
                    f"scale={scale_factor:.3f})"
                )

        if not effect["enabled"] and not rule_genuinely_matches:
            pass  # fall through to apply calculator recommendation
        elif not effect["enabled"]:
            logger.info(
                "Aperture [%s] (%s pads, %.3f mm²): %s (inactive)",
                pad_type, int(dims["count"]), dims["padAreaMm2"], source,
            )
            continue

        logger.info(
            "Aperture [%s] (%s pads, %.3f mm², %.3f x %.3f mm): "
            "theoretical=%.3f mm³ recommended=%.3f mm³ "
            "target_area=%.3f mm² | %s",
            pad_type,
            int(dims["count"]),
            dims["padAreaMm2"],
            dims["padWidthMm"],
            dims["padHeightMm"],
            snapshot.get("theoreticalVolumeMm3", 0),
            snapshot.get("recommendedVolumeMm3", 0),
            snapshot.get("targetOpenAreaMm2", 0),
            source,
        )

        if mode == "scale":
            if scale_factor != 1.0:
                for pi in pad_infos:
                    if pi.pad_type == pad_type:
                        pi.polygon = scale_geometry(
                            pi.polygon,
                            xfact=scale_factor,
                            yfact=scale_factor,
                            origin="centroid",
                        )
        else:
            if delta_mm != 0.0:
                for pi in pad_infos:
                    if pi.pad_type == pad_type:
                        pi.polygon = pi.polygon.buffer(
                            delta_mm, resolution=config.curve_resolution
                        )


def _apply_global_aperture(paste_geom, aperture_workspace: dict, config: StencilConfig):
    """Apply a single workspace rule to the entire geometry (legacy path)."""
    aperture_effect = resolve_aperture_workspace_effect(aperture_workspace, config.effective_thickness_mm)
    effect = aperture_effect["effect"]
    if not effect["enabled"]:
        logger.info(
            "Aperture rule inactive: %s",
            aperture_effect["ruleName"] or aperture_effect["matchSummary"] or "(none)",
        )
        return paste_geom
    logger.info(
        "Aperture rule active: %s -> %s",
        aperture_effect["matchSummary"] or "(any)",
        aperture_effect["actionSummary"] or "(none)",
    )
    if aperture_effect.get("groupSummary"):
        logger.info(
            "Aperture rule group: %s (%s rule(s))",
            aperture_effect["groupSummary"],
            aperture_effect.get("groupRuleCount", 0),
        )
    if effect["mode"] == "scale":
        scale_factor = float(effect.get("scale", 1.0) or 1.0)
        if scale_factor != 1.0:
            paste_geom = scale_geometry(
                paste_geom, xfact=scale_factor, yfact=scale_factor, origin="centroid",
            )
    else:
        delta_mm = float(effect.get("deltaMm", 0.0) or 0.0)
        if delta_mm != 0.0:
            paste_geom = paste_geom.buffer(delta_mm, resolution=config.curve_resolution)
    return paste_geom


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


def _filter_paste_side(paste_files: list[Path], side: str) -> list[Path]:
    """Filter paste files by board side (top/bottom)."""
    filtered = []
    for f in paste_files:
        name = f.name.lower()
        is_bottom = any(marker in name for marker in _BOTTOM_PASTE_MARKERS)
        if side == "top" and not is_bottom:
            filtered.append(f)
        elif side == "bottom" and is_bottom:
            filtered.append(f)
    return filtered


def _filter_mask_side(mask_files: list[Path], side: str) -> list[Path]:
    """Filter solder mask files by board side (top/bottom)."""
    filtered = []
    for f in mask_files:
        name = f.name.lower()
        if any(marker in name for marker in ("paste", "cream")):
            continue
        is_bottom = any(marker in name for marker in _BOTTOM_MASK_MARKERS)
        if side == "top" and not is_bottom:
            filtered.append(f)
        elif side == "bottom" and is_bottom:
            filtered.append(f)
    return filtered


def _side_availability_note(
    files: list[Path],
    side: str,
    side_filter,
    layer_name: str,
) -> str:
    if side == "both":
        return ""
    other = "bottom" if side == "top" else "top"
    other_files = side_filter(files, other)
    if not other_files:
        return f"no '{other}' {layer_name} layer in input"
    return f"{len(other_files)} '{other}' {layer_name} file(s) found but not selected"


def _outline_from_paste(paste_geom, margin_mm: float):
    min_x, min_y, max_x, max_y = paste_geom.bounds
    return box(min_x - margin_mm, min_y - margin_mm, max_x + margin_mm, max_y + margin_mm)


def _build_stencil_report(
    *,
    input_dir: Path,
    output_path: Path,
    side: str,
    opening_source: str,
    config: StencilConfig,
    opening_files: list[Path],
    paste_geom,
    pad_summary: dict[str, int],
    outline_files: list[Path],
    outline_geom,
    drill_count: int,
    has_outline_fallback: bool,
    model_backend: str,
    elapsed_s: float,
    other_side_info: str = "",
) -> str:
    lines = []
    lines.append("=" * 60)
    lines.append("  StencilForge — Generation Report")
    lines.append("=" * 60)
    lines.append(f"  Input       : {input_dir}")
    lines.append(f"  Output      : {output_path}")
    lines.append(f"  Date        : {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")

    # Opening info
    lines.append("── Opening Layers ──")
    lines.append(f"  Side         : {side}")
    lines.append(f"  Source       : {opening_source}")
    for f in opening_files:
        lines.append(f"  File         : {f.name} ({f.stat().st_size:,} bytes)")
    if other_side_info:
        lines.append(f"  Note         : {other_side_info}")
    lines.append(f"  Total pads   : {sum(pad_summary.values()) if pad_summary else 'N/A'}")
    if pad_summary:
        lines.append(f"  Breakdown    : {', '.join(f'{v} {k}' for k, v in sorted(pad_summary.items()))}")
    lines.append(f"  Opening area : {paste_geom.area:.2f} mm² (before offset)")
    if opening_source == "solder_mask":
        lines.append(f"  Mask scale   : {config.mask_opening_scale:.3f}")
    lines.append(f"  Offset       : {config.paste_offset_mm:+.2f} mm")
    lines.append("")

    # Outline info
    lines.append("── Board Outline ──")
    if outline_files:
        outlines = ", ".join(f.name for f in outline_files)
        lines.append(f"  Layer        : {outlines}")
    else:
        lines.append(f"  Layer        : (none found)")
    if has_outline_fallback:
        lines.append(f"  Method       : paste bounding box + margin ({config.outline_margin_mm} mm)")
    else:
        lines.append(f"  Method       : {config.outline_close_strategy}")
        if outline_geom is not None and not outline_geom.is_empty:
            lines.append(f"  Area         : {outline_geom.area:.2f} mm²")
            b = outline_geom.bounds
            lines.append(f"  Dimensions   : {b[2]-b[0]:.1f} × {b[3]-b[1]:.1f} mm")
    lines.append("")

    # Drill
    lines.append("── Drill Holes ──")
    lines.append(f"  Loaded       : {drill_count}")
    lines.append("")

    # Output
    lines.append("── Output ──")
    lines.append(f"  Backend      : {model_backend}")
    lines.append(f"  Printer      : {config.printer_profile}")
    lines.append(f"  Resolution   : arc_steps={config.arc_steps}, curve_resolution={config.curve_resolution}")
    if config.thickness_managed_by_printer_profile:
        lines.append(f"  Thickness    : {config.effective_thickness_mm} mm (FSM managed)")
        lines.append(f"  User thickness: {config.thickness_mm} mm (ignored)")
    else:
        lines.append(f"  Thickness    : {config.thickness_mm} mm")
    lines.append(f"  Locator      : {'enabled' if config.locator_enabled else 'disabled'}")
    try:
        size_bytes = output_path.stat().st_size
        lines.append(f"  File size    : {size_bytes:,} bytes ({size_bytes/1024:.0f} KB)")
    except OSError:
        pass
    lines.append(f"  Duration     : {elapsed_s:.1f}s")
    lines.append("")
    lines.append("=" * 60)

    return "\n".join(lines)


def _write_stencil_report(output_path: Path, report: str) -> None:
    report_path = output_path.with_suffix(".txt")
    try:
        report_path.write_text(report, encoding="utf-8")
    except OSError:
        logger.warning("Failed to write stencil report: %s", report_path)
    for line in report.splitlines():
        if line.strip() and not line.startswith("="):
            logger.info(line.strip())
