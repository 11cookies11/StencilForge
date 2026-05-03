from __future__ import annotations

import pytest
from shapely.geometry import box
from shapely.ops import unary_union

from stencilforge.config import StencilConfig
from stencilforge.geometry import flatten_to_polygons
from stencilforge.pipeline.qfn import regenerate_qfn_paste


def _qfn_fixture():
    pads = []
    coords = [-1.5, -0.5, 0.5, 1.5]
    for x in coords:
        pads.append(box(x - 0.25, 3.0 - 0.10, x + 0.25, 3.0 + 0.10))
        pads.append(box(x - 0.25, -3.0 - 0.10, x + 0.25, -3.0 + 0.10))
    for y in coords:
        pads.append(box(3.0 - 0.10, y - 0.25, 3.0 + 0.10, y + 0.25))
        pads.append(box(-3.0 - 0.10, y - 0.25, -3.0 + 0.10, y + 0.25))
    pads.append(box(-1.0, -1.0, 1.0, 1.0))
    return unary_union(pads)


def test_fsm_qfn_grouped_slots_replace_thin_pins() -> None:
    original = _qfn_fixture()
    cfg = StencilConfig.from_dict(
        {
            "printer_profile": "fsm",
            "qfn_confidence_threshold": 0.6,
            "fsm_qfn_min_slot_width_mm": 0.4,
            "fsm_qfn_min_slot_gap_mm": 0.4,
            "fsm_qfn_min_slot_length_mm": 0.8,
            "fsm_qfn_max_pins_per_slot": 4,
            "fsm_qfn_target_volume_ratio": 1.0,
        }
    )

    regenerated = regenerate_qfn_paste(original, cfg)
    polygons = flatten_to_polygons(regenerated)
    small_pins = [p for p in polygons if p.area == pytest.approx(0.10)]
    grouped_slots = [
        p for p in polygons
        if min(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]) >= 0.39
        and max(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]) >= 0.79
        and p.area < 2.0
    ]

    assert len(small_pins) == 0
    assert len(grouped_slots) == 4
    assert sum(p.area for p in grouped_slots) >= 16 * 0.10


def test_generic_qfn_regeneration_keeps_printable_existing_strategy() -> None:
    original = _qfn_fixture()
    cfg = StencilConfig.from_dict(
        {
            "printer_profile": "generic",
            "qfn_confidence_threshold": 0.6,
        }
    )

    regenerated = regenerate_qfn_paste(original, cfg)
    polygons = flatten_to_polygons(regenerated)

    assert len(polygons) >= 5
