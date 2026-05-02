"""Integration tests using real Gerber fixtures through the full pipeline."""

from __future__ import annotations

import tempfile
import zipfile
from pathlib import Path

import pytest
import trimesh

from stencilforge.aperture_workspace import (
    default_aperture_workspace,
    normalize_aperture_workspace,
)
from stencilforge.config import StencilConfig
from stencilforge.pipeline import generate_stencil

pytestmark = pytest.mark.integration


# ── helper ──────────────────────────────────────────────────────────────────


def _extract_and_generate(case_name: str, tmp_path: Path, **config_overrides) -> Path:
    """Extract the first ZIP from a fixture case and run generate_stencil."""
    fixtures_dir = Path(__file__).resolve().parents[1] / "fixtures" / "gerber"
    case_dir = fixtures_dir / case_name / "input"
    zips = sorted(case_dir.glob("*.zip"))
    if not zips:
        pytest.skip(f"No ZIP fixture in {case_dir}")

    extract_dir = tmp_path / "gerber"
    with zipfile.ZipFile(zips[0], "r") as zf:
        zf.extractall(extract_dir)

    output_path = tmp_path / "output.stl"
    config_dict = {}
    config_dict.update(config_overrides)
    config = StencilConfig.from_dict(config_dict)
    generate_stencil(extract_dir, output_path, config)
    return output_path


# ── basic generation ───────────────────────────────────────────────────────


class TestBasicGeneration:
    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_produces_stl_file(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        generate_stencil(gerber_fixture, output, StencilConfig.from_dict({}))
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_stl_has_faces(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        generate_stencil(gerber_fixture, output, StencilConfig.from_dict({}))
        mesh = trimesh.load_mesh(str(output), file_type="stl")
        assert len(mesh.faces) > 1000

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_stl_is_valid_mesh(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        generate_stencil(gerber_fixture, output, StencilConfig.from_dict({}))
        mesh = trimesh.load_mesh(str(output), file_type="stl")
        assert mesh.is_volume or len(mesh.faces) > 0
        bounds = mesh.bounds
        assert bounds is not None
        assert bounds.shape == (2, 3)


# ── config variations ──────────────────────────────────────────────────────


class TestConfigVariations:
    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    @pytest.mark.parametrize("thickness_mm", [0.10, 0.12, 0.15, 0.20])
    def test_varying_thickness(self, gerber_fixture, tmp_path, thickness_mm) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({"thickness_mm": thickness_mm})
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    @pytest.mark.parametrize("output_mode", ["solid_with_cutouts", "holes_only"])
    def test_output_modes(self, gerber_fixture, tmp_path, output_mode) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({"output_mode": output_mode})
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    @pytest.mark.parametrize("model_backend", ["trimesh"])
    def test_model_backend_trimesh(self, gerber_fixture, tmp_path, model_backend) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({"model_backend": model_backend})
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()
        mesh = trimesh.load_mesh(str(output), file_type="stl")
        assert len(mesh.faces) > 0


# ── aperture workspace ──────────────────────────────────────────────────────


class TestApertureWorkspace:
    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_with_default_workspace(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        ws = default_aperture_workspace()
        generate_stencil(gerber_fixture, output, config, ws)
        assert output.exists()

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_with_qfn_rule_enabled(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        ws = normalize_aperture_workspace({"selectedRuleId": "rule_qfn"})
        generate_stencil(gerber_fixture, output, config, ws)
        assert output.exists()

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_with_bga_rule_enabled(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        ws = normalize_aperture_workspace({"selectedRuleId": "rule_bga"})
        generate_stencil(gerber_fixture, output, config, ws)
        assert output.exists()

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_with_all_rules_disabled(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        ws = default_aperture_workspace()
        for rule in ws.get("rules", []):
            rule["enabled"] = False
        generate_stencil(gerber_fixture, output, config, ws)
        assert output.exists()


# ── edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    @pytest.mark.parametrize("gerber_fixture", ["case_002_no_outline"], indirect=True)
    def test_no_outline_layer_fallback(self, gerber_fixture, tmp_path) -> None:
        """Pipeline should succeed even when no GKO/outline layer exists."""
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()
        assert output.stat().st_size > 0

    @pytest.mark.parametrize("gerber_fixture", ["case_003_qfn"], indirect=True)
    def test_qfn_board(self, gerber_fixture, tmp_path) -> None:
        """QFN boards should produce valid STL output."""
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()
        mesh = trimesh.load_mesh(str(output), file_type="stl")
        assert len(mesh.faces) > 0

    @pytest.mark.parametrize("gerber_fixture", ["case_004_zip_input"], indirect=True)
    def test_zip_extraction_works(self, gerber_fixture, tmp_path) -> None:
        """Verify Gerber data is extractable — the fixture itself should load."""
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()

    @pytest.mark.parametrize("gerber_fixture", ["case_005_large_board"], indirect=True)
    def test_large_board(self, gerber_fixture, tmp_path) -> None:
        """Large boards should not hang or crash."""
        import time
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({})
        start = time.time()
        generate_stencil(gerber_fixture, output, config)
        elapsed = time.time() - start
        assert output.exists()
        assert elapsed < 300  # should complete within 5 minutes


# ── locator variations ─────────────────────────────────────────────────────


class TestLocatorVariations:
    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    def test_locator_disabled(self, gerber_fixture, tmp_path) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({"locator_enabled": False})
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()

    @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    @pytest.mark.parametrize("open_side", ["none", "top", "right", "bottom", "left"])
    def test_locator_open_sides(self, gerber_fixture, tmp_path, open_side) -> None:
        output = tmp_path / "output.stl"
        config = StencilConfig.from_dict({
            "locator_enabled": True,
            "locator_open_side": open_side,
        })
        generate_stencil(gerber_fixture, output, config)
        assert output.exists()
