from __future__ import annotations

import importlib.util
from dataclasses import fields

import pytest

from stencilforge.config import StencilConfig


def test_default_config_values() -> None:
    cfg = StencilConfig.from_dict({})
    assert cfg.thickness_mm == 0.12
    assert cfg.output_mode == "solid_with_cutouts"
    assert cfg.model_backend == "trimesh"
    assert "*gko*" in cfg.outline_patterns
    assert "*gtp*" in cfg.paste_patterns
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
    assert cfg.sfmesh_chunked_watertight_enabled is True
    assert cfg.sfmesh_chunk_size_mm == 70.0
    assert cfg.sfmesh_chunk_overlap_mm == 1.0
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


def test_sfmesh_backend_maps_to_trimesh() -> None:
    cfg = StencilConfig.from_dict({"model_backend": "sfmesh"})
    assert cfg.model_backend == "trimesh"
    cfg.validate()


def test_ui_entry_point_modules_exist() -> None:
    assert importlib.util.find_spec("stencilforge.ui.app") is not None
    assert importlib.util.find_spec("stencilforge.ui.preview") is not None
    assert importlib.util.find_spec("stencilforge.ui.vtk_app") is not None
    assert importlib.util.find_spec("stencilforge.ui_vtk_app") is not None


def test_config_to_dict_round_trips_all_fields() -> None:
    cfg = StencilConfig.from_dict(
        {
            "paste_patterns": ["*abc*"],
            "outline_patterns": ["*def*"],
            "thickness_mm": 0.2,
            "paste_offset_mm": -0.02,
            "outline_margin_mm": 4.2,
            "locator_enabled": False,
            "locator_height_mm": 3.0,
            "locator_width_mm": 2.5,
            "locator_clearance_mm": 0.3,
            "locator_step_height_mm": 1.2,
            "locator_step_width_mm": 1.7,
            "locator_mode": "wall",
            "locator_open_side": "top",
            "locator_open_width_mm": 0.4,
            "output_mode": "holes_only",
            "model_backend": "cadquery",
            "sfmesh_quality_mode": "auto",
            "sfmesh_voxel_pitch_mm": 0.1,
            "sfmesh_adaptive_pitch_enabled": False,
            "sfmesh_adaptive_pitch_min_mm": 0.09,
            "sfmesh_adaptive_pitch_max_mm": 0.22,
            "sfmesh_watertight_face_limit": 123456,
            "sfmesh_simplify_tol_mm": 0.01,
            "sfmesh_min_polygon_area_mm2": 0.02,
            "sfmesh_min_hole_area_mm2": 0.03,
            "sfmesh_decimate_target_ratio": 0.8,
            "sfmesh_hole_protect_enabled": False,
            "sfmesh_hole_protect_max_width_mm": 0.7,
            "sfmesh_hole_pitch_divisor": 4.0,
            "sfmesh_chunked_watertight_enabled": False,
            "sfmesh_chunk_size_mm": 60.0,
            "sfmesh_chunk_overlap_mm": 0.5,
            "stl_quality": "high_quality",
            "stl_linear_deflection": 0.03,
            "stl_angular_deflection": 0.04,
            "stl_tolerance": 0.001,
            "arc_steps": 72,
            "curve_resolution": 18,
            "qfn_regen_enabled": False,
            "qfn_min_feature_mm": 0.7,
            "qfn_confidence_threshold": 0.8,
            "qfn_max_pad_width_mm": 1.1,
            "outline_fill_rule": "legacy",
            "outline_close_strategy": "graph",
            "outline_merge_tol_mm": 0.02,
            "outline_snap_eps_mm": 0.002,
            "outline_arc_max_chord_error_mm": 0.015,
            "outline_gap_bridge_mm": 0.06,
            "cadquery_simplify_tol_mm": 0.01,
            "cadquery_short_edge_min_mm": 0.0002,
            "cadquery_quantize_mm": 0.00002,
            "ui_debug_plot_outline": True,
            "ui_debug_plot_max_segments": 1234,
            "ui_debug_plot_max_offset_vectors": 456,
            "ui_debug_plot_offset_min_mm": 0.05,
        }
    )

    data = cfg.to_dict()
    assert set(data) == {field.name for field in fields(StencilConfig)}
    assert data["outline_gap_bridge_mm"] == 0.06
    assert data["cadquery_quantize_mm"] == 0.00002
    assert StencilConfig.from_dict(data) == cfg


@pytest.mark.parametrize(
    ("patch", "message"),
    [
        ({"thickness_mm": 0}, r"Invalid config: thickness_mm > 0"),
        ({"output_mode": "bad_mode"}, r"Invalid config: output_mode in \{holes_only, solid_with_cutouts\}"),
        ({"model_backend": "bad_backend"}, r"Invalid config: model_backend in \{trimesh, cadquery\}"),
        ({"sfmesh_quality_mode": "bad_mode"}, r"Invalid config: sfmesh_quality_mode in \{fast, auto, watertight\}"),
        ({"sfmesh_voxel_pitch_mm": 0}, r"Invalid config: sfmesh_voxel_pitch_mm > 0"),
        ({"sfmesh_adaptive_pitch_min_mm": 0}, r"Invalid config: sfmesh_adaptive_pitch_min_mm > 0"),
        ({"sfmesh_adaptive_pitch_max_mm": 0}, r"Invalid config: sfmesh_adaptive_pitch_max_mm > 0"),
        (
            {"sfmesh_adaptive_pitch_min_mm": 0.2, "sfmesh_adaptive_pitch_max_mm": 0.1},
            r"Invalid config: sfmesh_adaptive_pitch_min_mm <= sfmesh_adaptive_pitch_max_mm",
        ),
        ({"sfmesh_watertight_face_limit": 0}, r"Invalid config: sfmesh_watertight_face_limit > 0"),
        ({"sfmesh_simplify_tol_mm": -1}, r"Invalid config: sfmesh_simplify_tol_mm >= 0"),
        ({"sfmesh_min_polygon_area_mm2": -1}, r"Invalid config: sfmesh_min_polygon_area_mm2 >= 0"),
        ({"sfmesh_min_hole_area_mm2": -1}, r"Invalid config: sfmesh_min_hole_area_mm2 >= 0"),
        ({"sfmesh_decimate_target_ratio": 0}, r"Invalid config: sfmesh_decimate_target_ratio in \(0, 1\]"),
        ({"sfmesh_hole_protect_max_width_mm": 0}, r"Invalid config: sfmesh_hole_protect_max_width_mm > 0"),
        ({"sfmesh_hole_pitch_divisor": 1}, r"Invalid config: sfmesh_hole_pitch_divisor > 1"),
        ({"sfmesh_chunk_size_mm": 0}, r"Invalid config: sfmesh_chunk_size_mm > 0"),
        ({"sfmesh_chunk_overlap_mm": -0.1}, r"Invalid config: sfmesh_chunk_overlap_mm >= 0"),
        ({"stl_quality": "ultra"}, r"Invalid config: stl_quality in \{fast, balanced, high_quality\} or empty"),
        ({"locator_open_side": "middle"}, r"Invalid config: locator_open_side in \{none, top, right, bottom, left\}"),
    ],
)
def test_validation_errors(patch: dict, message: str) -> None:
    cfg = StencilConfig.from_dict(patch)
    with pytest.raises(ValueError, match=message):
        cfg.validate()
