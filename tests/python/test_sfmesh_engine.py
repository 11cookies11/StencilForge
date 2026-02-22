from __future__ import annotations

from pathlib import Path

from shapely.geometry import Polygon
import trimesh

from stencilforge.config import StencilConfig
from stencilforge.pipeline.engine import EngineExportInput, get_model_engine


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
