from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class StencilConfig:
    paste_patterns: list[str]
    outline_patterns: list[str]
    thickness_mm: float
    paste_offset_mm: float
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
        paste_patterns = _ensure_list(data.get("paste_patterns", []))
        outline_patterns = _ensure_list(data.get("outline_patterns", []))
        thickness_mm = float(data.get("thickness_mm", 0.12))
        paste_offset_mm = float(data.get("paste_offset_mm", -0.05))
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
        model_backend = str(data.get("model_backend", "cadquery"))
        sfmesh_quality_mode = str(data.get("sfmesh_quality_mode", "fast"))
        sfmesh_voxel_pitch_mm = float(data.get("sfmesh_voxel_pitch_mm", 0.08))
        stl_quality = str(data.get("stl_quality", "balanced"))
        stl_linear_deflection = float(data.get("stl_linear_deflection", 0.05))
        stl_angular_deflection = float(data.get("stl_angular_deflection", 0.1))
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
        arc_steps = int(data.get("arc_steps", 64))
        curve_resolution = int(data.get("curve_resolution", 16))
        qfn_regen_enabled = bool(data.get("qfn_regen_enabled", True))
        qfn_min_feature_mm = float(data.get("qfn_min_feature_mm", 0.6))
        qfn_confidence_threshold = float(data.get("qfn_confidence_threshold", 0.75))
        qfn_max_pad_width_mm = float(data.get("qfn_max_pad_width_mm", 1.2))
        outline_fill_rule = str(data.get("outline_fill_rule", "evenodd"))
        outline_close_strategy = str(data.get("outline_close_strategy", "legacy"))
        outline_merge_tol_mm = float(data.get("outline_merge_tol_mm", 0.01))
        outline_snap_eps_mm = float(data.get("outline_snap_eps_mm", 0.001))
        outline_arc_max_chord_error_mm = float(data.get("outline_arc_max_chord_error_mm", 0.01))
        outline_gap_bridge_mm = float(data.get("outline_gap_bridge_mm", 0.05))
        cadquery_simplify_tol_mm = float(data.get("cadquery_simplify_tol_mm", 0.0))
        cadquery_short_edge_min_mm = float(data.get("cadquery_short_edge_min_mm", 0.0001))
        cadquery_quantize_mm = float(data.get("cadquery_quantize_mm", 0.00001))
        ui_debug_plot_outline = bool(data.get("ui_debug_plot_outline", False))
        ui_debug_plot_max_segments = int(data.get("ui_debug_plot_max_segments", 20000))
        ui_debug_plot_max_offset_vectors = int(data.get("ui_debug_plot_max_offset_vectors", 800))
        ui_debug_plot_offset_min_mm = float(data.get("ui_debug_plot_offset_min_mm", 0.0))
        return StencilConfig(
            paste_patterns=paste_patterns,
            outline_patterns=outline_patterns,
            thickness_mm=thickness_mm,
            paste_offset_mm=paste_offset_mm,
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

    def validate(self) -> None:
        if self.thickness_mm <= 0:
            raise ValueError("thickness_mm must be > 0")
        if self.arc_steps < 8:
            raise ValueError("arc_steps must be >= 8")
        if self.curve_resolution < 4:
            raise ValueError("curve_resolution must be >= 4")
        if self.qfn_min_feature_mm <= 0:
            raise ValueError("qfn_min_feature_mm must be > 0")
        if not 0.0 < self.qfn_confidence_threshold <= 1.0:
            raise ValueError("qfn_confidence_threshold must be in (0, 1]")
        if self.qfn_max_pad_width_mm <= 0:
            raise ValueError("qfn_max_pad_width_mm must be > 0")
        if self.output_mode not in {"holes_only", "solid_with_cutouts"}:
            raise ValueError("output_mode must be holes_only or solid_with_cutouts")
        if self.model_backend not in {"trimesh", "cadquery", "sfmesh"}:
            raise ValueError("model_backend must be trimesh, cadquery, or sfmesh")
        if self.sfmesh_quality_mode not in {"fast", "watertight"}:
            raise ValueError("sfmesh_quality_mode must be fast or watertight")
        if self.sfmesh_voxel_pitch_mm <= 0:
            raise ValueError("sfmesh_voxel_pitch_mm must be > 0")
        if self.stl_linear_deflection <= 0:
            raise ValueError("stl_linear_deflection must be > 0")
        if self.stl_angular_deflection <= 0:
            raise ValueError("stl_angular_deflection must be > 0")
        if self.stl_tolerance < 0:
            raise ValueError("stl_tolerance must be >= 0")
        if self.stl_quality and self.stl_quality not in ("fast", "balanced", "high_quality"):
            raise ValueError("stl_quality must be fast, balanced, or high_quality")
        if self.locator_height_mm < 0:
            raise ValueError("locator_height_mm must be >= 0")
        if self.locator_width_mm < 0:
            raise ValueError("locator_width_mm must be >= 0")
        if self.locator_clearance_mm < 0:
            raise ValueError("locator_clearance_mm must be >= 0")
        if self.locator_step_height_mm < 0:
            raise ValueError("locator_step_height_mm must be >= 0")
        if self.locator_step_width_mm < 0:
            raise ValueError("locator_step_width_mm must be >= 0")
        if self.locator_mode not in {"step", "wall"}:
            raise ValueError("locator_mode must be step or wall")
        if self.locator_step_height_mm > 0 and self.locator_height_mm > 0:
            if self.locator_step_height_mm > self.locator_height_mm:
                raise ValueError("locator_step_height_mm must be <= locator_height_mm")
        if self.locator_open_width_mm < 0:
            raise ValueError("locator_open_width_mm must be >= 0")
        if self.locator_open_side not in {"none", "top", "right", "bottom", "left"}:
            raise ValueError("locator_open_side must be none/top/right/bottom/left")
        if self.outline_fill_rule not in {"legacy", "evenodd"}:
            raise ValueError("outline_fill_rule must be legacy or evenodd")
        if self.outline_close_strategy not in {"legacy", "graph", "robust_polygonize"}:
            raise ValueError("outline_close_strategy must be legacy, graph, or robust_polygonize")
        if self.outline_merge_tol_mm < 0:
            raise ValueError("outline_merge_tol_mm must be >= 0")
        if self.outline_snap_eps_mm <= 0:
            raise ValueError("outline_snap_eps_mm must be > 0")
        if self.outline_arc_max_chord_error_mm <= 0:
            raise ValueError("outline_arc_max_chord_error_mm must be > 0")
        if self.outline_gap_bridge_mm < 0:
            raise ValueError("outline_gap_bridge_mm must be >= 0")
        if self.cadquery_simplify_tol_mm < 0:
            raise ValueError("cadquery_simplify_tol_mm must be >= 0")
        if self.cadquery_short_edge_min_mm < 0:
            raise ValueError("cadquery_short_edge_min_mm must be >= 0")
        if self.cadquery_quantize_mm < 0:
            raise ValueError("cadquery_quantize_mm must be >= 0")
        if self.ui_debug_plot_max_segments < 0:
            raise ValueError("ui_debug_plot_max_segments must be >= 0")
        if self.ui_debug_plot_max_offset_vectors < 0:
            raise ValueError("ui_debug_plot_max_offset_vectors must be >= 0")
        if self.ui_debug_plot_offset_min_mm < 0:
            raise ValueError("ui_debug_plot_offset_min_mm must be >= 0")


def _ensure_list(value: Iterable[str] | str | None) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


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
