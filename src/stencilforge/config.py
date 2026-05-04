from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

DEFAULT_PASTE_PATTERNS = ["*gtp*", "*gbp*", "*paste*top*", "*paste*bottom*", "*cream*"]
DEFAULT_OUTLINE_PATTERNS = ["*gko*", "*gm1*", "*boardoutline*", "*outline*", "*edge*cuts*"]
FDM_EFFECTIVE_THICKNESS_MM = 0.20
DEFAULT_DRILL_PATTERNS = [
    "*.drl", "*.txt", "*.drd", "*.exc",
    "*drill*", "*hole*", "*pth*", "*npth*",
    "*thru*", "*round*",
]


@dataclass(frozen=True)
class StencilConfig:
    paste_patterns: list[str]
    paste_side: str
    printer_profile: str
    outline_patterns: list[str]
    drill_patterns: list[str]
    thickness_mm: float
    paste_offset_mm: float
    mask_opening_scale: float
    outline_margin_mm: float
    locator_enabled: bool
    locator_height_mm: float
    locator_width_mm: float
    locator_clearance_mm: float
    locator_step_height_mm: float
    locator_step_width_mm: float
    locator_mode: str
    locator_open_side: str
    locator_open_width_mm: float
    output_mode: str
    model_backend: str
    sfmesh_quality_mode: str
    sfmesh_voxel_pitch_mm: float
    sfmesh_adaptive_pitch_enabled: bool
    sfmesh_adaptive_pitch_min_mm: float
    sfmesh_adaptive_pitch_max_mm: float
    sfmesh_watertight_face_limit: int
    sfmesh_simplify_tol_mm: float
    sfmesh_min_polygon_area_mm2: float
    sfmesh_min_hole_area_mm2: float
    sfmesh_decimate_target_ratio: float
    sfmesh_hole_protect_enabled: bool
    sfmesh_hole_protect_max_width_mm: float
    sfmesh_hole_pitch_divisor: float
    sfmesh_chunked_watertight_enabled: bool
    sfmesh_chunk_size_mm: float
    sfmesh_chunk_overlap_mm: float
    stl_quality: str
    stl_linear_deflection: float
    stl_angular_deflection: float
    stl_tolerance: float
    arc_steps: int
    curve_resolution: int
    qfn_regen_enabled: bool
    qfn_min_feature_mm: float
    qfn_confidence_threshold: float
    qfn_max_pad_width_mm: float
    fdm_qfn_grouped_slots_enabled: bool
    fdm_qfn_min_slot_width_mm: float
    fdm_qfn_min_slot_gap_mm: float
    fdm_qfn_min_slot_length_mm: float
    fdm_qfn_max_pins_per_slot: int
    fdm_qfn_target_volume_ratio: float
    fdm_qfn_bridge_enabled: bool
    fdm_qfn_bridge_width_mm: float
    outline_fill_rule: str
    outline_close_strategy: str
    outline_merge_tol_mm: float
    outline_snap_eps_mm: float
    outline_arc_max_chord_error_mm: float
    outline_gap_bridge_mm: float
    cadquery_simplify_tol_mm: float
    cadquery_short_edge_min_mm: float
    cadquery_quantize_mm: float
    ui_debug_plot_outline: bool
    ui_debug_plot_max_segments: int
    ui_debug_plot_max_offset_vectors: int
    ui_debug_plot_offset_min_mm: float

    @staticmethod
    def default_path(project_root: Path) -> Path:
        return _user_config_dir() / "stencilforge.json"

    @staticmethod
    def load_default(project_root: Path) -> "StencilConfig":
        user_path = StencilConfig.default_path(project_root)
        if user_path.exists():
            return StencilConfig.from_json(user_path)
        bundled_path = _find_bundled_config(project_root)
        if bundled_path is not None:
            config = StencilConfig.from_json(bundled_path)
            try:
                user_path.parent.mkdir(parents=True, exist_ok=True)
                user_path.write_text(bundled_path.read_text(encoding="utf-8"), encoding="utf-8")
            except OSError:
                pass
            return config
        return StencilConfig.from_dict({})

    @staticmethod
    def from_json(path: Path) -> "StencilConfig":
        try:
            raw = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return StencilConfig.from_dict({})
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return StencilConfig.from_dict({})
        return StencilConfig.from_dict(data)

    @staticmethod
    def from_dict(data: dict) -> "StencilConfig":
        paste_patterns = _ensure_list(data.get("paste_patterns", [])) or list(DEFAULT_PASTE_PATTERNS)
        paste_side = str(data.get("paste_side", "top")).strip().lower()
        if paste_side not in ("top", "bottom", "both"):
            paste_side = "top"
        printer_profile = str(data.get("printer_profile", "generic")).strip().lower()
        if printer_profile in ("normal", "default", "non_fdm", "non-fdm"):
            printer_profile = "generic"
        if printer_profile in ("fsm",):
            printer_profile = "fdm"
        if printer_profile not in ("generic", "fdm"):
            printer_profile = "generic"
        outline_patterns = _ensure_list(data.get("outline_patterns", [])) or list(DEFAULT_OUTLINE_PATTERNS)
        drill_patterns = _ensure_list(data.get("drill_patterns", [])) or list(DEFAULT_DRILL_PATTERNS)
        thickness_mm = float(data.get("thickness_mm", 0.12))
        paste_offset_mm = float(data.get("paste_offset_mm", -0.05))
        mask_opening_scale = float(data.get("mask_opening_scale", 0.95))
        outline_margin_mm = float(data.get("outline_margin_mm", 5.0))
        locator_enabled = bool(data.get("locator_enabled", True))
        locator_height_mm = float(data.get("locator_height_mm", 2.0))
        locator_width_mm = float(data.get("locator_width_mm", 2.0))
        locator_clearance_mm = float(data.get("locator_clearance_mm", 0.2))
        locator_step_height_mm = float(data.get("locator_step_height_mm", 1.0))
        locator_step_width_mm = float(data.get("locator_step_width_mm", 1.5))
        locator_mode = str(data.get("locator_mode", "step"))
        locator_open_side = str(data.get("locator_open_side", "none"))
        locator_open_width_mm = float(data.get("locator_open_width_mm", 0.0))
        output_mode = str(data.get("output_mode", "solid_with_cutouts"))
        model_backend = str(data.get("model_backend", "trimesh")).strip().lower()
        if model_backend == "sfmesh":
            model_backend = "trimesh"
        sfmesh_quality_mode = str(data.get("sfmesh_quality_mode", "fast"))
        sfmesh_voxel_pitch_mm = float(data.get("sfmesh_voxel_pitch_mm", 0.08))
        sfmesh_adaptive_pitch_enabled = bool(data.get("sfmesh_adaptive_pitch_enabled", True))
        sfmesh_adaptive_pitch_min_mm = float(data.get("sfmesh_adaptive_pitch_min_mm", 0.08))
        sfmesh_adaptive_pitch_max_mm = float(data.get("sfmesh_adaptive_pitch_max_mm", 0.24))
        sfmesh_watertight_face_limit = int(data.get("sfmesh_watertight_face_limit", 250000))
        sfmesh_simplify_tol_mm = float(data.get("sfmesh_simplify_tol_mm", 0.0))
        sfmesh_min_polygon_area_mm2 = float(data.get("sfmesh_min_polygon_area_mm2", 0.0))
        sfmesh_min_hole_area_mm2 = float(data.get("sfmesh_min_hole_area_mm2", 0.0))
        sfmesh_decimate_target_ratio = float(data.get("sfmesh_decimate_target_ratio", 1.0))
        sfmesh_hole_protect_enabled = bool(data.get("sfmesh_hole_protect_enabled", True))
        sfmesh_hole_protect_max_width_mm = float(data.get("sfmesh_hole_protect_max_width_mm", 0.8))
        sfmesh_hole_pitch_divisor = float(data.get("sfmesh_hole_pitch_divisor", 3.0))
        sfmesh_chunked_watertight_enabled = bool(data.get("sfmesh_chunked_watertight_enabled", True))
        sfmesh_chunk_size_mm = float(data.get("sfmesh_chunk_size_mm", 70.0))
        sfmesh_chunk_overlap_mm = float(data.get("sfmesh_chunk_overlap_mm", 1.0))
        profile_defaults = _printer_profile_defaults(printer_profile)
        stl_quality = str(data.get("stl_quality", profile_defaults["stl_quality"]))
        stl_linear_deflection = float(data.get("stl_linear_deflection", profile_defaults["stl_linear_deflection"]))
        stl_angular_deflection = float(data.get("stl_angular_deflection", profile_defaults["stl_angular_deflection"]))
        stl_tolerance = float(data.get("stl_tolerance", 0.0))
        stl_presets = {
            "fast": (0.2, 0.35),
            "balanced": (0.05, 0.1),
            "high_quality": (0.02, 0.05),
        }
        if stl_quality in stl_presets:
            preset_linear, preset_angular = stl_presets[stl_quality]
            if "stl_linear_deflection" not in data:
                stl_linear_deflection = preset_linear
            if "stl_angular_deflection" not in data:
                stl_angular_deflection = preset_angular
        arc_steps = int(data.get("arc_steps", profile_defaults["arc_steps"]))
        curve_resolution = int(data.get("curve_resolution", profile_defaults["curve_resolution"]))
        qfn_regen_enabled = bool(data.get("qfn_regen_enabled", True))
        qfn_min_feature_mm = float(data.get("qfn_min_feature_mm", 0.6))
        qfn_confidence_threshold = float(data.get("qfn_confidence_threshold", 0.75))
        qfn_max_pad_width_mm = float(data.get("qfn_max_pad_width_mm", 1.2))
        fdm_qfn_grouped_slots_enabled = bool(data.get("fdm_qfn_grouped_slots_enabled", True))
        fdm_qfn_min_slot_width_mm = float(data.get("fdm_qfn_min_slot_width_mm", 0.4))
        fdm_qfn_min_slot_gap_mm = float(data.get("fdm_qfn_min_slot_gap_mm", 0.4))
        fdm_qfn_min_slot_length_mm = float(data.get("fdm_qfn_min_slot_length_mm", 0.8))
        fdm_qfn_max_pins_per_slot = int(data.get("fdm_qfn_max_pins_per_slot", 4))
        fdm_qfn_target_volume_ratio = float(data.get("fdm_qfn_target_volume_ratio", 1.0))
        fdm_qfn_bridge_enabled = bool(data.get("fdm_qfn_bridge_enabled", True))
        fdm_qfn_bridge_width_mm = float(data.get("fdm_qfn_bridge_width_mm", 0.9))
        outline_fill_rule = str(data.get("outline_fill_rule", "evenodd"))
        outline_close_strategy = str(data.get("outline_close_strategy", "robust_polygonize"))
        outline_merge_tol_mm = float(data.get("outline_merge_tol_mm", 0.01))
        outline_snap_eps_mm = float(data.get("outline_snap_eps_mm", 0.001))
        outline_arc_max_chord_error_mm = float(data.get("outline_arc_max_chord_error_mm", 0.01))
        outline_gap_bridge_mm = float(data.get("outline_gap_bridge_mm", 0.08))
        cadquery_simplify_tol_mm = float(data.get("cadquery_simplify_tol_mm", 0.0))
        cadquery_short_edge_min_mm = float(data.get("cadquery_short_edge_min_mm", 0.0001))
        cadquery_quantize_mm = float(data.get("cadquery_quantize_mm", 0.00001))
        ui_debug_plot_outline = bool(data.get("ui_debug_plot_outline", False))
        ui_debug_plot_max_segments = int(data.get("ui_debug_plot_max_segments", 20000))
        ui_debug_plot_max_offset_vectors = int(data.get("ui_debug_plot_max_offset_vectors", 800))
        ui_debug_plot_offset_min_mm = float(data.get("ui_debug_plot_offset_min_mm", 0.0))
        return StencilConfig(
            paste_patterns=paste_patterns,
            paste_side=paste_side,
            printer_profile=printer_profile,
            outline_patterns=outline_patterns,
            drill_patterns=drill_patterns,
            thickness_mm=thickness_mm,
            paste_offset_mm=paste_offset_mm,
            mask_opening_scale=mask_opening_scale,
            outline_margin_mm=outline_margin_mm,
            locator_enabled=locator_enabled,
            locator_height_mm=locator_height_mm,
            locator_width_mm=locator_width_mm,
            locator_clearance_mm=locator_clearance_mm,
            locator_step_height_mm=locator_step_height_mm,
            locator_step_width_mm=locator_step_width_mm,
            locator_mode=locator_mode,
            locator_open_side=locator_open_side,
            locator_open_width_mm=locator_open_width_mm,
            output_mode=output_mode,
            model_backend=model_backend,
            sfmesh_quality_mode=sfmesh_quality_mode,
            sfmesh_voxel_pitch_mm=sfmesh_voxel_pitch_mm,
            sfmesh_adaptive_pitch_enabled=sfmesh_adaptive_pitch_enabled,
            sfmesh_adaptive_pitch_min_mm=sfmesh_adaptive_pitch_min_mm,
            sfmesh_adaptive_pitch_max_mm=sfmesh_adaptive_pitch_max_mm,
            sfmesh_watertight_face_limit=sfmesh_watertight_face_limit,
            sfmesh_simplify_tol_mm=sfmesh_simplify_tol_mm,
            sfmesh_min_polygon_area_mm2=sfmesh_min_polygon_area_mm2,
            sfmesh_min_hole_area_mm2=sfmesh_min_hole_area_mm2,
            sfmesh_decimate_target_ratio=sfmesh_decimate_target_ratio,
            sfmesh_hole_protect_enabled=sfmesh_hole_protect_enabled,
            sfmesh_hole_protect_max_width_mm=sfmesh_hole_protect_max_width_mm,
            sfmesh_hole_pitch_divisor=sfmesh_hole_pitch_divisor,
            sfmesh_chunked_watertight_enabled=sfmesh_chunked_watertight_enabled,
            sfmesh_chunk_size_mm=sfmesh_chunk_size_mm,
            sfmesh_chunk_overlap_mm=sfmesh_chunk_overlap_mm,
            stl_quality=stl_quality,
            stl_linear_deflection=stl_linear_deflection,
            stl_angular_deflection=stl_angular_deflection,
            stl_tolerance=stl_tolerance,
            arc_steps=arc_steps,
            curve_resolution=curve_resolution,
            qfn_regen_enabled=qfn_regen_enabled,
            qfn_min_feature_mm=qfn_min_feature_mm,
            qfn_confidence_threshold=qfn_confidence_threshold,
            qfn_max_pad_width_mm=qfn_max_pad_width_mm,
            fdm_qfn_grouped_slots_enabled=fdm_qfn_grouped_slots_enabled,
            fdm_qfn_min_slot_width_mm=fdm_qfn_min_slot_width_mm,
            fdm_qfn_min_slot_gap_mm=fdm_qfn_min_slot_gap_mm,
            fdm_qfn_min_slot_length_mm=fdm_qfn_min_slot_length_mm,
            fdm_qfn_max_pins_per_slot=fdm_qfn_max_pins_per_slot,
            fdm_qfn_target_volume_ratio=fdm_qfn_target_volume_ratio,
            fdm_qfn_bridge_enabled=fdm_qfn_bridge_enabled,
            fdm_qfn_bridge_width_mm=fdm_qfn_bridge_width_mm,
            outline_fill_rule=outline_fill_rule,
            outline_close_strategy=outline_close_strategy,
            outline_merge_tol_mm=outline_merge_tol_mm,
            outline_snap_eps_mm=outline_snap_eps_mm,
            outline_arc_max_chord_error_mm=outline_arc_max_chord_error_mm,
            outline_gap_bridge_mm=outline_gap_bridge_mm,
            cadquery_simplify_tol_mm=cadquery_simplify_tol_mm,
            cadquery_short_edge_min_mm=cadquery_short_edge_min_mm,
            cadquery_quantize_mm=cadquery_quantize_mm,
            ui_debug_plot_outline=ui_debug_plot_outline,
            ui_debug_plot_max_segments=ui_debug_plot_max_segments,
            ui_debug_plot_max_offset_vectors=ui_debug_plot_max_offset_vectors,
            ui_debug_plot_offset_min_mm=ui_debug_plot_offset_min_mm,
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @property
    def effective_thickness_mm(self) -> float:
        if self.printer_profile == "fdm":
            return FDM_EFFECTIVE_THICKNESS_MM
        return self.thickness_mm

    @property
    def thickness_managed_by_printer_profile(self) -> bool:
        return self.printer_profile == "fdm"

    def validate(self) -> None:
        for desc, check in self._RULES:
            if not check(self):
                raise ValueError(f"Invalid config: {desc}")


StencilConfig._RULES = [
    ("paste_side in {top, bottom, both}", lambda s: s.paste_side in {"top", "bottom", "both"}),
    ("printer_profile in {generic, fdm}", lambda s: s.printer_profile in {"generic", "fdm"}),
    ("thickness_mm > 0", lambda s: s.thickness_mm > 0),
    ("mask_opening_scale > 0", lambda s: s.mask_opening_scale > 0),
    ("arc_steps >= 8", lambda s: s.arc_steps >= 8),
    ("curve_resolution >= 4", lambda s: s.curve_resolution >= 4),
    ("qfn_min_feature_mm > 0", lambda s: s.qfn_min_feature_mm > 0),
    ("qfn_confidence_threshold in (0, 1]", lambda s: 0.0 < s.qfn_confidence_threshold <= 1.0),
    ("qfn_max_pad_width_mm > 0", lambda s: s.qfn_max_pad_width_mm > 0),
    ("fdm_qfn_min_slot_width_mm > 0", lambda s: s.fdm_qfn_min_slot_width_mm > 0),
    ("fdm_qfn_min_slot_gap_mm >= 0", lambda s: s.fdm_qfn_min_slot_gap_mm >= 0),
    ("fdm_qfn_min_slot_length_mm > 0", lambda s: s.fdm_qfn_min_slot_length_mm > 0),
    ("fdm_qfn_max_pins_per_slot >= 2", lambda s: s.fdm_qfn_max_pins_per_slot >= 2),
    ("fdm_qfn_target_volume_ratio > 0", lambda s: s.fdm_qfn_target_volume_ratio > 0),
    ("fdm_qfn_bridge_width_mm > 0", lambda s: s.fdm_qfn_bridge_width_mm > 0),
    ("output_mode in {holes_only, solid_with_cutouts}", lambda s: s.output_mode in {"holes_only", "solid_with_cutouts"}),
    ("model_backend in {trimesh, cadquery}", lambda s: s.model_backend in {"trimesh", "cadquery"}),
    ("sfmesh_quality_mode in {fast, auto, watertight}", lambda s: s.sfmesh_quality_mode in {"fast", "auto", "watertight"}),
    ("sfmesh_voxel_pitch_mm > 0", lambda s: s.sfmesh_voxel_pitch_mm > 0),
    ("sfmesh_adaptive_pitch_min_mm > 0", lambda s: s.sfmesh_adaptive_pitch_min_mm > 0),
    ("sfmesh_adaptive_pitch_max_mm > 0", lambda s: s.sfmesh_adaptive_pitch_max_mm > 0),
    ("sfmesh_adaptive_pitch_min_mm <= sfmesh_adaptive_pitch_max_mm", lambda s: s.sfmesh_adaptive_pitch_min_mm <= s.sfmesh_adaptive_pitch_max_mm),
    ("sfmesh_watertight_face_limit > 0", lambda s: s.sfmesh_watertight_face_limit > 0),
    ("sfmesh_simplify_tol_mm >= 0", lambda s: s.sfmesh_simplify_tol_mm >= 0),
    ("sfmesh_min_polygon_area_mm2 >= 0", lambda s: s.sfmesh_min_polygon_area_mm2 >= 0),
    ("sfmesh_min_hole_area_mm2 >= 0", lambda s: s.sfmesh_min_hole_area_mm2 >= 0),
    ("sfmesh_decimate_target_ratio in (0, 1]", lambda s: 0 < s.sfmesh_decimate_target_ratio <= 1),
    ("sfmesh_hole_protect_max_width_mm > 0", lambda s: s.sfmesh_hole_protect_max_width_mm > 0),
    ("sfmesh_hole_pitch_divisor > 1", lambda s: s.sfmesh_hole_pitch_divisor > 1),
    ("sfmesh_chunk_size_mm > 0", lambda s: s.sfmesh_chunk_size_mm > 0),
    ("sfmesh_chunk_overlap_mm >= 0", lambda s: s.sfmesh_chunk_overlap_mm >= 0),
    ("stl_linear_deflection > 0", lambda s: s.stl_linear_deflection > 0),
    ("stl_angular_deflection > 0", lambda s: s.stl_angular_deflection > 0),
    ("stl_tolerance >= 0", lambda s: s.stl_tolerance >= 0),
    ("stl_quality in {fast, balanced, high_quality} or empty", lambda s: not s.stl_quality or s.stl_quality in ("fast", "balanced", "high_quality")),
    ("locator_height_mm >= 0", lambda s: s.locator_height_mm >= 0),
    ("locator_width_mm >= 0", lambda s: s.locator_width_mm >= 0),
    ("locator_clearance_mm >= 0", lambda s: s.locator_clearance_mm >= 0),
    ("locator_step_height_mm >= 0", lambda s: s.locator_step_height_mm >= 0),
    ("locator_step_width_mm >= 0", lambda s: s.locator_step_width_mm >= 0),
    ("locator_mode in {step, wall}", lambda s: s.locator_mode in {"step", "wall"}),
    ("locator_step_height_mm <= locator_height_mm when both > 0", lambda s: not (s.locator_step_height_mm > 0 and s.locator_height_mm > 0) or s.locator_step_height_mm <= s.locator_height_mm),
    ("locator_open_width_mm >= 0", lambda s: s.locator_open_width_mm >= 0),
    ("locator_open_side in {none, top, right, bottom, left}", lambda s: s.locator_open_side in {"none", "top", "right", "bottom", "left"}),
    ("outline_fill_rule in {legacy, evenodd}", lambda s: s.outline_fill_rule in {"legacy", "evenodd"}),
    ("outline_close_strategy in {legacy, graph, robust_polygonize}", lambda s: s.outline_close_strategy in {"legacy", "graph", "robust_polygonize"}),
    ("outline_merge_tol_mm >= 0", lambda s: s.outline_merge_tol_mm >= 0),
    ("outline_snap_eps_mm > 0", lambda s: s.outline_snap_eps_mm > 0),
    ("outline_arc_max_chord_error_mm > 0", lambda s: s.outline_arc_max_chord_error_mm > 0),
    ("outline_gap_bridge_mm >= 0", lambda s: s.outline_gap_bridge_mm >= 0),
    ("cadquery_simplify_tol_mm >= 0", lambda s: s.cadquery_simplify_tol_mm >= 0),
    ("cadquery_short_edge_min_mm >= 0", lambda s: s.cadquery_short_edge_min_mm >= 0),
    ("cadquery_quantize_mm >= 0", lambda s: s.cadquery_quantize_mm >= 0),
    ("ui_debug_plot_max_segments >= 0", lambda s: s.ui_debug_plot_max_segments >= 0),
    ("ui_debug_plot_max_offset_vectors >= 0", lambda s: s.ui_debug_plot_max_offset_vectors >= 0),
    ("ui_debug_plot_offset_min_mm >= 0", lambda s: s.ui_debug_plot_offset_min_mm >= 0),
]


def _ensure_list(value: Iterable[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _printer_profile_defaults(profile: str) -> dict[str, float | int | str]:
    if profile == "fdm":
        return {
            "stl_quality": "high_quality",
            "stl_linear_deflection": 0.02,
            "stl_angular_deflection": 0.05,
            "arc_steps": 96,
            "curve_resolution": 24,
        }
    return {
        "stl_quality": "balanced",
        "stl_linear_deflection": 0.05,
        "stl_angular_deflection": 0.1,
        "arc_steps": 64,
        "curve_resolution": 16,
    }


def _user_config_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("USERPROFILE")
        if base:
            return Path(base) / "StencilForge"
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "stencilforge"
    return Path.home() / ".config" / "stencilforge"


def _find_bundled_config(project_root: Path) -> Path | None:
    candidates = [
        project_root / "config" / "stencilforge.json",
    ]
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", project_root))
        exe_dir = Path(sys.executable).resolve().parent
        candidates.extend(
            [
                base / "config" / "stencilforge.json",
                exe_dir / "config" / "stencilforge.json",
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
