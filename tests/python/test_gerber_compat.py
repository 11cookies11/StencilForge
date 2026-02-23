from __future__ import annotations

from pathlib import Path

import gerber.am_statements as am_statements

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
