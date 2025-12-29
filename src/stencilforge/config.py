from __future__ import annotations

import json
import os
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
    stl_linear_deflection: float
    stl_angular_deflection: float
    arc_steps: int
    curve_resolution: int
    qfn_regen_enabled: bool
    qfn_min_feature_mm: float
    qfn_confidence_threshold: float
    qfn_max_pad_width_mm: float

    @staticmethod
    def default_path(project_root: Path) -> Path:
        return _user_config_dir() / "stencilforge.json"

    @staticmethod
    def load_default(project_root: Path) -> "StencilConfig":
        user_path = StencilConfig.default_path(project_root)
        if user_path.exists():
            return StencilConfig.from_json(user_path)
        bundled_path = project_root / "config" / "stencilforge.json"
        if bundled_path.exists():
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
        data = json.loads(path.read_text(encoding="utf-8"))
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
        stl_linear_deflection = float(data.get("stl_linear_deflection", 0.05))
        stl_angular_deflection = float(data.get("stl_angular_deflection", 0.1))
        arc_steps = int(data.get("arc_steps", 64))
        curve_resolution = int(data.get("curve_resolution", 16))
        qfn_regen_enabled = bool(data.get("qfn_regen_enabled", True))
        qfn_min_feature_mm = float(data.get("qfn_min_feature_mm", 0.6))
        qfn_confidence_threshold = float(data.get("qfn_confidence_threshold", 0.75))
        qfn_max_pad_width_mm = float(data.get("qfn_max_pad_width_mm", 1.2))
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
            stl_linear_deflection=stl_linear_deflection,
            stl_angular_deflection=stl_angular_deflection,
            arc_steps=arc_steps,
            curve_resolution=curve_resolution,
            qfn_regen_enabled=qfn_regen_enabled,
            qfn_min_feature_mm=qfn_min_feature_mm,
            qfn_confidence_threshold=qfn_confidence_threshold,
            qfn_max_pad_width_mm=qfn_max_pad_width_mm,
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
        if self.model_backend not in {"trimesh", "cadquery"}:
            raise ValueError("model_backend must be trimesh or cadquery")
        if self.stl_linear_deflection <= 0:
            raise ValueError("stl_linear_deflection must be > 0")
        if self.stl_angular_deflection <= 0:
            raise ValueError("stl_angular_deflection must be > 0")
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
