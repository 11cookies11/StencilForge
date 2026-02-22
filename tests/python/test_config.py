from __future__ import annotations

import pytest

from stencilforge.config import StencilConfig


def test_default_config_values() -> None:
    cfg = StencilConfig.from_dict({})
    assert cfg.thickness_mm == 0.12
    assert cfg.output_mode == "solid_with_cutouts"
    assert cfg.model_backend == "cadquery"
    assert cfg.stl_quality == "balanced"
    assert cfg.stl_linear_deflection == 0.05
    assert cfg.stl_angular_deflection == 0.1


def test_stl_quality_preset_applies_when_not_overridden() -> None:
    cfg = StencilConfig.from_dict({"stl_quality": "fast"})
    assert cfg.stl_linear_deflection == 0.2
    assert cfg.stl_angular_deflection == 0.35


def test_stl_quality_preset_does_not_override_explicit_values() -> None:
    cfg = StencilConfig.from_dict(
        {
            "stl_quality": "fast",
            "stl_linear_deflection": 0.5,
            "stl_angular_deflection": 0.6,
        }
    )
    assert cfg.stl_linear_deflection == 0.5
    assert cfg.stl_angular_deflection == 0.6


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"thickness_mm": 0}, "thickness_mm must be > 0"),
        ({"output_mode": "bad_mode"}, "output_mode must be holes_only or solid_with_cutouts"),
        ({"model_backend": "bad_backend"}, "model_backend must be trimesh or cadquery"),
        ({"stl_quality": "ultra"}, "stl_quality must be fast, balanced, or high_quality"),
        ({"locator_open_side": "middle"}, "locator_open_side must be none/top/right/bottom/left"),
    ],
)
def test_validation_errors(patch: dict, message: str) -> None:
    cfg = StencilConfig.from_dict(patch)
    with pytest.raises(ValueError, match=message):
        cfg.validate()
