from __future__ import annotations

from pathlib import Path

import pytest
from shapely.geometry import Polygon
import trimesh

from stencilforge.config import StencilConfig
from stencilforge.pipeline.engine import EngineExportInput, _adaptive_voxel_pitch, get_model_engine


def test_sfmesh_engine_exports_stl_binary(tmp_path: Path) -> None:
    cfg = StencilConfig.from_dict({"model_backend": "sfmesh", "thickness_mm": 0.12})
    cfg.validate()

    polygon = Polygon([(0, 0), (10, 0), (10, 5), (0, 5)])
    out = tmp_path / "sfmesh.stl"

    engine = get_model_engine("sfmesh")
    engine.export(
        EngineExportInput(
            stencil_2d=polygon,
            locator_geom=None,
            locator_step_geom=None,
            output_path=out,
            config=cfg,
        )
    )

    assert out.exists()
    assert out.stat().st_size > 0

    mesh = trimesh.load_mesh(out, force="mesh")
    assert mesh.faces is not None
    assert int(mesh.faces.shape[0]) > 0


def test_sfmesh_engine_handles_polygon_with_hole(tmp_path: Path) -> None:
    cfg = StencilConfig.from_dict({"model_backend": "sfmesh", "thickness_mm": 0.12})
    cfg.validate()

    polygon = Polygon(
        shell=[(0, 0), (20, 0), (20, 10), (0, 10)],
        holes=[[(5, 3), (15, 3), (15, 7), (5, 7)]],
    )
    out = tmp_path / "sfmesh_hole.stl"

    engine = get_model_engine("sfmesh")
    engine.export(
        EngineExportInput(
            stencil_2d=polygon,
            locator_geom=None,
            locator_step_geom=None,
            output_path=out,
            config=cfg,
        )
    )

    assert out.exists()
    mesh = trimesh.load_mesh(out, force="mesh")
    assert int(mesh.faces.shape[0]) > 0


def test_sfmesh_watertight_mode_exports_mesh(tmp_path: Path) -> None:
    cfg = StencilConfig.from_dict(
        {
            "model_backend": "sfmesh",
            "sfmesh_quality_mode": "watertight",
            "sfmesh_voxel_pitch_mm": 0.05,
            "thickness_mm": 0.12,
        }
    )
    cfg.validate()

    polygon = Polygon([(0, 0), (10, 0), (10, 5), (0, 5)])
    out = tmp_path / "sfmesh_watertight.stl"

    engine = get_model_engine("sfmesh")
    engine.export(
        EngineExportInput(
            stencil_2d=polygon,
            locator_geom=None,
            locator_step_geom=None,
            output_path=out,
            config=cfg,
        )
    )

    assert out.exists()
    mesh = trimesh.load_mesh(out, force="mesh")
    assert int(mesh.faces.shape[0]) > 0
    bounds = mesh.bounds
    assert bounds is not None
    extents = bounds[1] - bounds[0]
    assert float(extents[0]) == pytest.approx(10.0, rel=0.05, abs=0.2)
    assert float(extents[1]) == pytest.approx(5.0, rel=0.05, abs=0.2)
    assert float(extents[2]) == pytest.approx(0.12, rel=0.2, abs=0.1)


def test_sfmesh_auto_mode_exports_mesh(tmp_path: Path) -> None:
    cfg = StencilConfig.from_dict(
        {
            "model_backend": "sfmesh",
            "sfmesh_quality_mode": "auto",
            "sfmesh_voxel_pitch_mm": 0.2,
            "sfmesh_watertight_face_limit": 1000000,
            "thickness_mm": 0.12,
        }
    )
    cfg.validate()

    polygon = Polygon([(0, 0), (12, 0), (12, 6), (0, 6)])
    out = tmp_path / "sfmesh_auto.stl"

    engine = get_model_engine("sfmesh")
    engine.export(
        EngineExportInput(
            stencil_2d=polygon,
            locator_geom=None,
            locator_step_geom=None,
            output_path=out,
            config=cfg,
        )
    )

    assert out.exists()
    mesh = trimesh.load_mesh(out, force="mesh")
    assert int(mesh.faces.shape[0]) > 0


def test_sfmesh_hole_protect_caps_pitch() -> None:
    cfg = StencilConfig.from_dict(
        {
            "model_backend": "sfmesh",
            "sfmesh_voxel_pitch_mm": 0.24,
            "sfmesh_adaptive_pitch_enabled": True,
            "sfmesh_hole_protect_enabled": True,
            "sfmesh_hole_pitch_divisor": 3.0,
            "sfmesh_hole_protect_max_width_mm": 0.8,
        }
    )
    cfg.validate()
    mesh = trimesh.creation.box(extents=(100, 100, 1.0))
    pitch = _adaptive_voxel_pitch(mesh, cfg, critical_hole_width=0.6)
    assert pitch <= 0.2


def test_sfmesh_chunked_watertight_exports_mesh(tmp_path: Path) -> None:
    cfg = StencilConfig.from_dict(
        {
            "model_backend": "sfmesh",
            "sfmesh_quality_mode": "watertight",
            "sfmesh_voxel_pitch_mm": 0.2,
            "sfmesh_chunked_watertight_enabled": True,
            "sfmesh_chunk_size_mm": 8.0,
            "sfmesh_chunk_overlap_mm": 1.0,
            "thickness_mm": 0.12,
        }
    )
    cfg.validate()
    polygon = Polygon(shell=[(0, 0), (30, 0), (30, 20), (0, 20)], holes=[[(10, 7), (20, 7), (20, 13), (10, 13)]])
    out = tmp_path / "sfmesh_chunked_watertight.stl"
    engine = get_model_engine("sfmesh")
    engine.export(
        EngineExportInput(
            stencil_2d=polygon,
            locator_geom=None,
            locator_step_geom=None,
            output_path=out,
            config=cfg,
        )
    )
    assert out.exists()
    mesh = trimesh.load_mesh(out, force="mesh")
    assert int(mesh.faces.shape[0]) > 0
