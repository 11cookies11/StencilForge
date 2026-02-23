from __future__ import annotations

import pytest

from stencilforge.config import StencilConfig


def test_default_config_values() -> None:
    cfg = StencilConfig.from_dict({})
    assert cfg.thickness_mm == 0.12
    assert cfg.output_mode == "solid_with_cutouts"
    assert cfg.model_backend == "cadquery"
    assert cfg.sfmesh_quality_mode == "fast"
    assert cfg.sfmesh_voxel_pitch_mm == 0.08
    assert cfg.sfmesh_adaptive_pitch_enabled is True
    assert cfg.sfmesh_adaptive_pitch_min_mm == 0.08
    assert cfg.sfmesh_adaptive_pitch_max_mm == 0.24
    assert cfg.sfmesh_watertight_face_limit == 250000
    assert cfg.sfmesh_simplify_tol_mm == 0.0
    assert cfg.sfmesh_min_polygon_area_mm2 == 0.0
    assert cfg.sfmesh_min_hole_area_mm2 == 0.0
    assert cfg.sfmesh_decimate_target_ratio == 1.0
    assert cfg.sfmesh_hole_protect_enabled is True
    assert cfg.sfmesh_hole_protect_max_width_mm == 0.8
    assert cfg.sfmesh_hole_pitch_divisor == 3.0
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


def test_sfmesh_backend_is_valid() -> None:
    cfg = StencilConfig.from_dict({"model_backend": "sfmesh"})
    cfg.validate()


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"thickness_mm": 0}, "thickness_mm must be > 0"),
        ({"output_mode": "bad_mode"}, "output_mode must be holes_only or solid_with_cutouts"),
        ({"model_backend": "bad_backend"}, "model_backend must be trimesh, cadquery, or sfmesh"),
        ({"sfmesh_quality_mode": "bad_mode"}, "sfmesh_quality_mode must be fast, auto, or watertight"),
        ({"sfmesh_voxel_pitch_mm": 0}, "sfmesh_voxel_pitch_mm must be > 0"),
        ({"sfmesh_adaptive_pitch_min_mm": 0}, "sfmesh_adaptive_pitch_min_mm must be > 0"),
        ({"sfmesh_adaptive_pitch_max_mm": 0}, "sfmesh_adaptive_pitch_max_mm must be > 0"),
        (
            {"sfmesh_adaptive_pitch_min_mm": 0.2, "sfmesh_adaptive_pitch_max_mm": 0.1},
            "sfmesh_adaptive_pitch_min_mm must be <= sfmesh_adaptive_pitch_max_mm",
        ),
        ({"sfmesh_watertight_face_limit": 0}, "sfmesh_watertight_face_limit must be > 0"),
        ({"sfmesh_simplify_tol_mm": -1}, "sfmesh_simplify_tol_mm must be >= 0"),
        ({"sfmesh_min_polygon_area_mm2": -1}, "sfmesh_min_polygon_area_mm2 must be >= 0"),
        ({"sfmesh_min_hole_area_mm2": -1}, "sfmesh_min_hole_area_mm2 must be >= 0"),
        ({"sfmesh_decimate_target_ratio": 0}, "sfmesh_decimate_target_ratio must be in \\(0, 1\\]"),
        ({"sfmesh_hole_protect_max_width_mm": 0}, "sfmesh_hole_protect_max_width_mm must be > 0"),
        ({"sfmesh_hole_pitch_divisor": 1}, "sfmesh_hole_pitch_divisor must be > 1"),
        ({"stl_quality": "ultra"}, "stl_quality must be fast, balanced, or high_quality"),
        ({"locator_open_side": "middle"}, "locator_open_side must be none/top/right/bottom/left"),
    ],
)
def test_validation_errors(patch: dict, message: str) -> None:
    cfg = StencilConfig.from_dict(patch)
    with pytest.raises(ValueError, match=message):
        cfg.validate()
