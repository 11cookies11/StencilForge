from __future__ import annotations

from pathlib import Path

import gerber.am_statements as am_statements
from gerber import primitives as gprim

from stencilforge.config import StencilConfig
from stencilforge.geometry.primitives import PrimitiveGeometryBuilder
from stencilforge.geometry.service import GerberGeometryService


class _DummyCamSource:
    units = "mm"


class _DummyLayer:
    cam_source = _DummyCamSource()
    primitives = []


def test_load_layer_accepts_legacy_rU_mode(monkeypatch, tmp_path: Path) -> None:
    probe = tmp_path / "probe.gbr"
    probe.write_text("G04 test*", encoding="utf-8")

    def fake_load_layer(path: str):
        with open(path, "rU", encoding="utf-8") as fp:
            _ = fp.read()
        return _DummyLayer()

    monkeypatch.setattr("stencilforge.geometry.service.load_layer", fake_load_layer)

    layer = GerberGeometryService._load_layer(probe, "paste")
    assert layer is not None
    assert layer.cam_source.units == "mm"
    assert isinstance(layer.primitives, list)


def test_load_layer_accepts_unclosed_outline_primitive(monkeypatch, tmp_path: Path) -> None:
    probe = tmp_path / "probe.gbr"
    probe.write_text("G04 test*", encoding="utf-8")

    def fake_load_layer(path: str):
        _ = path
        prim = am_statements.AMOutlinePrimitive(
            4,
            "on",
            (0.0, 0.0),
            [(1.0, 0.0), (1.0, 1.0)],
            0.0,
        )
        layer = _DummyLayer()
        layer.primitives = [prim]
        return layer

    monkeypatch.setattr("stencilforge.geometry.service.load_layer", fake_load_layer)
    layer = GerberGeometryService._load_layer(probe, "paste")
    assert len(layer.primitives) == 1


def test_load_layer_patches_am_macro_subtraction(monkeypatch, tmp_path: Path) -> None:
    probe = tmp_path / "probe.gbr"
    probe.write_text("G04 test*", encoding="utf-8")

    def fake_load_layer(path: str):
        _ = path
        from gerber.gerber_statements import eval_macro, read_macro

        primitives = list(eval_macro(read_macro("20,1,0.1,0-$1,0,$1,0,0"), [0.7]))
        layer = _DummyLayer()
        layer.primitives = primitives
        return layer

    monkeypatch.setattr("stencilforge.geometry.service.load_layer", fake_load_layer)
    layer = GerberGeometryService._load_layer(probe, "paste")

    assert layer.primitives == ["20,1.0,0.1,-0.7,0,0.7,0,0"]


def test_outline_primitive_builds_polygon() -> None:
    aperture = gprim.Circle((0.0, 0.0), 0.1)
    outline = gprim.Outline(
        [
            gprim.Line((0.0, 0.0), (1.0, 0.0), aperture),
            gprim.Line((1.0, 0.0), (1.0, 1.0), aperture),
            gprim.Line((1.0, 1.0), (0.0, 1.0), aperture),
            gprim.Line((0.0, 1.0), (0.0, 0.0), aperture),
        ]
    )

    geom = PrimitiveGeometryBuilder(StencilConfig.from_dict({})).build([outline])

    assert geom is not None
    assert geom.area == 1.0
    assert geom.bounds == (0.0, 0.0, 1.0, 1.0)
