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
        self.loaded_layers: list[tuple[list[str], str]] = []

    def load_paste_geometry(self, files, label: str = "paste"):
        self.loaded_layers.append(([f.name for f in files], label))
        return box(0, 0, 10, 8)

    def load_outline_geometry(self, path: Path):
        self.outline_loaded = path
        return box(-1, -1, 11, 9)

    def get_last_outline_debug(self) -> dict:
        return {"ok": True}


class _AsymmetricGeometryService(_DummyGeometryService):
    def load_paste_geometry(self, files, label: str = "paste"):
        self.loaded_layers.append(([f.name for f in files], label))
        return box(1, 2, 3, 4)

    def load_outline_geometry(self, path: Path):
        self.outline_loaded = path
        return box(0, 0, 10, 10)


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


def test_solder_mask_source_excludes_paste_mask_filename(tmp_path: Path) -> None:
    (tmp_path / "Gerber_TopPasteMaskLayer.GTP").write_text("G04 paste*\n", encoding="utf-8")
    (tmp_path / "Gerber_TopSolderMaskLayer.GTS").write_text("G04 mask*\n", encoding="utf-8")

    service = _DummyGeometryService(StencilConfig.from_dict({}))
    engine = _DummyEngine()

    cfg = StencilConfig.from_dict(
        {
            "outline_patterns": ["*not_found*"],
            "output_mode": "holes_only",
            "locator_enabled": False,
        }
    )
    generate_stencil(tmp_path, tmp_path / "out.stl", cfg,
                     geometry_service=service, model_engine=engine)

    assert engine.called is True
    assert service.loaded_layers[0] == (["Gerber_TopSolderMaskLayer.GTS"], "solder mask")


@pytest.mark.parametrize(
    ("side", "layer_name"),
    [
        ("top", "Gerber_TopSolderMaskLayer.GTS"),
        ("bottom", "Gerber_BottomSolderMaskLayer.GBS"),
    ],
)
def test_output_mirrors_for_physical_stencil_use(tmp_path: Path, side: str, layer_name: str) -> None:
    (tmp_path / layer_name).write_text("G04 mask*\n", encoding="utf-8")
    (tmp_path / "Gerber_BoardOutlineLayer.GKO").write_text("G04 outline*\n", encoding="utf-8")

    service = _AsymmetricGeometryService(StencilConfig.from_dict({}))
    engine = _DummyEngine()
    cfg = StencilConfig.from_dict(
        {
            "paste_side": side,
            "output_mode": "holes_only",
            "locator_enabled": False,
            "paste_offset_mm": 0.0,
            "mask_opening_scale": 1.0,
        }
    )

    generate_stencil(tmp_path, tmp_path / "out.stl", cfg,
                     geometry_service=service, model_engine=engine)

    assert engine.last_input is not None
    assert engine.last_input.stencil_2d.bounds == pytest.approx((7, 2, 9, 4))


def test_mask_opening_scale_applies_only_to_solder_mask_source(tmp_path: Path) -> None:
    (tmp_path / "Gerber_TopSolderMaskLayer.GTS").write_text("G04 mask*\n", encoding="utf-8")

    service = _DummyGeometryService(StencilConfig.from_dict({}))
    engine = _DummyEngine()
    cfg = StencilConfig.from_dict(
        {
            "outline_patterns": ["*not_found*"],
            "output_mode": "holes_only",
            "locator_enabled": False,
            "paste_offset_mm": 0.0,
            "mask_opening_scale": 0.5,
        }
    )

    generate_stencil(tmp_path, tmp_path / "out.stl", cfg,
                     geometry_service=service, model_engine=engine)

    assert engine.last_input is not None
    assert engine.last_input.stencil_2d.bounds == pytest.approx((2.5, 2.0, 7.5, 6.0))


def test_fdm_profile_uses_managed_effective_thickness(tmp_path: Path) -> None:
    (tmp_path / "Gerber_TopSolderMaskLayer.GTS").write_text("G04 mask*\n", encoding="utf-8")

    service = _DummyGeometryService(StencilConfig.from_dict({}))
    engine = _DummyEngine()
    cfg = StencilConfig.from_dict(
        {
            "printer_profile": "fdm",
            "thickness_mm": 0.12,
            "outline_patterns": ["*not_found*"],
            "output_mode": "holes_only",
            "locator_enabled": False,
            "paste_offset_mm": 0.0,
        }
    )

    generate_stencil(tmp_path, tmp_path / "out.stl", cfg,
                     geometry_service=service, model_engine=engine)

    assert engine.last_input is not None
    assert engine.last_input.config.thickness_mm == 0.12
    assert engine.last_input.config.effective_thickness_mm == pytest.approx(0.20)


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
