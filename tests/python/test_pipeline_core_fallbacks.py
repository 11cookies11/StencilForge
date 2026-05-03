from __future__ import annotations

from pathlib import Path

from shapely.geometry import box
import pytest

from stencilforge.config import StencilConfig
from stencilforge.pipeline.core import generate_stencil


class _DummyEngine:
    name = "dummy"

    def __init__(self) -> None:
        self.called = False
        self.last_input = None

    def export(self, data) -> None:
        self.called = True
        self.last_input = data


class _DummyGeometryService:
    def __init__(self, config: StencilConfig) -> None:
        self.config = config
        self.outline_loaded: Path | None = None

    def load_paste_geometry(self, _files):
        return box(0, 0, 10, 8)

    def load_outline_geometry(self, path: Path):
        self.outline_loaded = path
        return box(-1, -1, 11, 9)

    def get_last_outline_debug(self) -> dict:
        return {"ok": True}


def test_outline_builtin_fallback_matches_gko(tmp_path: Path) -> None:
    (tmp_path / "Gerber_TopPasteMaskLayer.GTP").write_text("G04 paste*\n", encoding="utf-8")
    (tmp_path / "Gerber_BoardOutlineLayer.GKO").write_text("G04 outline*\n", encoding="utf-8")

    service = _DummyGeometryService(StencilConfig.from_dict({}))
    engine = _DummyEngine()

    cfg = StencilConfig.from_dict(
        {
            "paste_patterns": ["*no_match*"],
            "outline_patterns": ["*not_found*"],
            "output_mode": "holes_only",
        }
    )
    generate_stencil(tmp_path, tmp_path / "out.stl", cfg,
                     geometry_service=service, model_engine=engine)

    assert engine.called is True
    assert service.outline_loaded is not None
    assert service.outline_loaded.name.lower().endswith(".gko")


def test_outline_falls_back_to_margin_when_no_outline_match(tmp_path: Path) -> None:
    (tmp_path / "Gerber_TopPasteMaskLayer.GTP").write_text("G04 paste*\n", encoding="utf-8")

    service = _DummyGeometryService(StencilConfig.from_dict({}))
    engine = _DummyEngine()

    cfg = StencilConfig.from_dict(
        {
            "paste_patterns": ["*no_match*"],
            "outline_patterns": ["*not_found*"],
            "output_mode": "solid_with_cutouts",
            "outline_margin_mm": 5.0,
        }
    )
    generate_stencil(tmp_path, tmp_path / "out.stl", cfg,
                     geometry_service=service, model_engine=engine)

    assert engine.called is True
    assert service.outline_loaded is None
    assert engine.last_input is not None
    min_x, min_y, max_x, max_y = engine.last_input.stencil_2d.bounds
    assert min_x <= -4.9
    assert min_y <= -4.9
    assert max_x >= 14.9
    assert max_y >= 12.9


def test_aperture_workspace_rule_changes_paste_geometry(tmp_path: Path) -> None:
    (tmp_path / "Gerber_TopPasteMaskLayer.GTP").write_text("G04 paste*\n", encoding="utf-8")

    service = _DummyGeometryService(StencilConfig.from_dict({}))
    engine = _DummyEngine()

    cfg = StencilConfig.from_dict(
        {
            "paste_patterns": ["*no_match*"],
            "outline_patterns": ["*not_found*"],
            "output_mode": "holes_only",
            "paste_offset_mm": 0.0,
            "locator_enabled": False,
            "qfn_regen_enabled": False,
        }
    )
    workspace = {
        "selectedRuleId": "rule_scale",
        "rules": [
            {
                "id": "rule_scale",
                "name": "Scale rule",
                "enabled": True,
                "priority": 100,
                "match": {"package": "Any", "padType": "Any", "layer": "Top", "padSize": ""},
                "action": {"mode": "scale", "deltaMm": 0.0, "scale": 0.5},
                "note": "",
            }
        ],
    }

    generate_stencil(tmp_path, tmp_path / "out.stl", cfg, workspace,
                     geometry_service=service, model_engine=engine)

    assert engine.called is True
    assert engine.last_input is not None
    assert engine.last_input.stencil_2d.bounds == pytest.approx((2.5, 2.0, 7.5, 6.0))
