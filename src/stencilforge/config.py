from __future__ import annotations

import json
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
    locator_open_side: str
    locator_open_width_mm: float
    output_mode: str
    arc_steps: int
    curve_resolution: int

    @staticmethod
    def default_path(project_root: Path) -> Path:
        return project_root / "config" / "stencilforge.json"

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
        locator_enabled = bool(data.get("locator_enabled", False))
        locator_height_mm = float(data.get("locator_height_mm", 2.0))
        locator_width_mm = float(data.get("locator_width_mm", 2.0))
        locator_clearance_mm = float(data.get("locator_clearance_mm", 0.2))
        locator_open_side = str(data.get("locator_open_side", "none"))
        locator_open_width_mm = float(data.get("locator_open_width_mm", 0.0))
        output_mode = str(data.get("output_mode", "solid_with_cutouts"))
        arc_steps = int(data.get("arc_steps", 64))
        curve_resolution = int(data.get("curve_resolution", 16))
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
            locator_open_side=locator_open_side,
            locator_open_width_mm=locator_open_width_mm,
            output_mode=output_mode,
            arc_steps=arc_steps,
            curve_resolution=curve_resolution,
        )

    def validate(self) -> None:
        if self.thickness_mm <= 0:
            raise ValueError("thickness_mm must be > 0")
        if self.arc_steps < 8:
            raise ValueError("arc_steps must be >= 8")
        if self.curve_resolution < 4:
            raise ValueError("curve_resolution must be >= 4")
        if self.output_mode not in {"holes_only", "solid_with_cutouts"}:
            raise ValueError("output_mode must be holes_only or solid_with_cutouts")
        if self.locator_height_mm < 0:
            raise ValueError("locator_height_mm must be >= 0")
        if self.locator_width_mm < 0:
            raise ValueError("locator_width_mm must be >= 0")
        if self.locator_clearance_mm < 0:
            raise ValueError("locator_clearance_mm must be >= 0")
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
