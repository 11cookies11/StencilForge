from __future__ import annotations

import io
import tempfile
import zipfile
from pathlib import Path

import pytest

from stencilforge.config import StencilConfig
from stencilforge.geometry.outline import OutlineBuilder
from stencilforge.geometry.service import _legacy_open_mode_compat
from gerber import load_layer


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "gerber"


def _find_gerber_file(extracted_dir: Path, patterns: list[str]) -> Path | None:
    for path in extracted_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        for pat in patterns:
            if pat.lower() in name:
                return path
    return None


@pytest.mark.parametrize("case_name", ["case_001_basic", "case_003_qfn"])
def test_outline_extraction_produces_valid_polygon(case_name: str) -> None:
    """OutlineBuilder should produce a non-empty geometry from real Gerber layers."""
    case_dir = FIXTURES / case_name / "input"
    zip_files = list(case_dir.glob("*.zip"))
    if not zip_files:
        pytest.skip(f"No ZIP fixture in {case_dir}")

    with tempfile.TemporaryDirectory(prefix="stencilforge_test_") as tmp:
        tmp_path = Path(tmp)
        with zipfile.ZipFile(zip_files[0], "r") as zf:
            zf.extractall(tmp)

        outline_path = _find_gerber_file(
            tmp_path,
            ["gko", "gm1", "boardoutline", "outline", "edge_cuts"],
        )
        if outline_path is None:
            pytest.skip(f"No outline layer found in {case_name} fixture")

        config = StencilConfig.from_dict({})
        builder = OutlineBuilder(config)
        with _legacy_open_mode_compat():
            layer = load_layer(str(outline_path))
        geom = builder.build(layer.primitives, layer.cam_source.units)

        assert geom is not None, "OutlineBuilder returned None"
        assert not geom.is_empty, "OutlineBuilder returned empty geometry"
        assert geom.geom_type in ("Polygon", "MultiPolygon"), (
            f"Expected Polygon or MultiPolygon, got {geom.geom_type}"
        )
