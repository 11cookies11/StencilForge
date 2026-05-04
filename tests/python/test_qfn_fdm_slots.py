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
        pads.append(box(x - 0.10, 3.0 - 0.25, x + 0.10, 3.0 + 0.25))
        pads.append(box(x - 0.10, -3.0 - 0.25, x + 0.10, -3.0 + 0.25))
    for y in coords:
        pads.append(box(3.0 - 0.25, y - 0.10, 3.0 + 0.25, y + 0.10))
        pads.append(box(-3.0 - 0.25, y - 0.10, -3.0 + 0.25, y + 0.10))
    pads.append(box(-1.0, -1.0, 1.0, 1.0))
    return unary_union(pads)


def _qfn_fixture_with_distractors():
    pads = [box(10, 0, 11.2, 0.6), box(10, 1, 11.2, 1.6)]
    coords = [-1.5, -0.5, 0.5, 1.5]
    for x in coords:
        pads.append(box(x - 0.10, 3.0 - 0.25, x + 0.10, 3.0 + 0.25))
        pads.append(box(x - 0.10, -3.0 - 0.25, x + 0.10, -3.0 + 0.25))
    for y in coords:
        pads.append(box(3.0 - 0.25, y - 0.10, 3.0 + 0.25, y + 0.10))
        pads.append(box(-3.0 - 0.25, y - 0.10, -3.0 + 0.25, y + 0.10))
    pads.append(box(-1.0, -1.0, 1.0, 1.0))
    return unary_union(pads)


def _qfn_like_fixture_without_center_pad():
    pads = []
    coords = [-3.0, -2.2, -1.4, -0.6, 0.6, 1.4, 2.2, 3.0]
    for x in coords:
        pads.append(box(x - 0.10, 3.0 - 0.25, x + 0.10, 3.0 + 0.25))
        pads.append(box(x - 0.10, -3.0 - 0.25, x + 0.10, -3.0 + 0.25))
    for y in coords:
        pads.append(box(3.0 - 0.25, y - 0.10, 3.0 + 0.25, y + 0.10))
        pads.append(box(-3.0 - 0.25, y - 0.10, -3.0 + 0.25, y + 0.10))
    return unary_union(pads)


def _outer_qfn_slot_segments(polygons):
    return [
        p for p in polygons
        if max(abs(p.centroid.x), abs(p.centroid.y)) > 2.0
        and min(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]) >= 0.39
        and max(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]) >= 0.79
        and p.area < 2.0
    ]


def test_fdm_qfn_grouped_slots_replace_thin_pins() -> None:
    original = _qfn_fixture()
    cfg = StencilConfig.from_dict(
        {
            "printer_profile": "fdm",
            "qfn_confidence_threshold": 0.6,
            "fdm_qfn_min_slot_width_mm": 0.4,
            "fdm_qfn_min_slot_gap_mm": 0.4,
            "fdm_qfn_min_slot_length_mm": 0.8,
            "fdm_qfn_max_pins_per_slot": 4,
            "fdm_qfn_target_volume_ratio": 1.0,
        }
    )

    regenerated = regenerate_qfn_paste(original, cfg)
    polygons = flatten_to_polygons(regenerated)
    small_pins = [p for p in polygons if p.area == pytest.approx(0.10)]
    grouped_segments = _outer_qfn_slot_segments(polygons)

    assert len(small_pins) == 0
    assert len(grouped_segments) >= 4
    assert sum(p.area for p in grouped_segments) >= 16 * 0.10


def test_fdm_qfn_grouped_slots_can_disable_support_bridges() -> None:
    original = _qfn_fixture()
    cfg = StencilConfig.from_dict(
        {
            "printer_profile": "fdm",
            "qfn_confidence_threshold": 0.6,
            "fdm_qfn_min_slot_width_mm": 0.4,
            "fdm_qfn_min_slot_gap_mm": 0.4,
            "fdm_qfn_min_slot_length_mm": 0.8,
            "fdm_qfn_max_pins_per_slot": 4,
            "fdm_qfn_target_volume_ratio": 1.0,
            "fdm_qfn_bridge_enabled": False,
        }
    )

    regenerated = regenerate_qfn_paste(original, cfg)
    polygons = flatten_to_polygons(regenerated)
    grouped_slots = _outer_qfn_slot_segments(polygons)

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


def test_fdm_qfn_detection_ignores_nearby_distractor_pads() -> None:
    original = _qfn_fixture_with_distractors()
    cfg = StencilConfig.from_dict(
        {
            "printer_profile": "fdm",
            "qfn_confidence_threshold": 0.6,
            "fdm_qfn_min_slot_width_mm": 0.4,
            "fdm_qfn_min_slot_gap_mm": 0.4,
            "fdm_qfn_min_slot_length_mm": 0.8,
            "fdm_qfn_max_pins_per_slot": 4,
        }
    )

    regenerated = regenerate_qfn_paste(original, cfg)
    polygons = flatten_to_polygons(regenerated)
    grouped_slots = [
        p for p in polygons
        if min(p.bounds[2] - p.bounds[0], p.bounds[3] - p.bounds[1]) >= 0.39
        and p.area < 3.0
    ]

    assert len(polygons) < len(flatten_to_polygons(original))
    assert len(grouped_slots) >= 4


def test_fdm_qfn_grouped_slots_requires_center_pad() -> None:
    original = _qfn_like_fixture_without_center_pad()
    cfg = StencilConfig.from_dict(
        {
            "printer_profile": "fdm",
            "qfn_confidence_threshold": 0.6,
            "fdm_qfn_min_slot_width_mm": 0.4,
            "fdm_qfn_min_slot_gap_mm": 0.4,
        }
    )

    regenerated = regenerate_qfn_paste(original, cfg)

    assert regenerated.equals(original)
