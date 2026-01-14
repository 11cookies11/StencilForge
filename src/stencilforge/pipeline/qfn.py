from __future__ import annotations

import logging
import math

from shapely import affinity
from shapely.geometry import MultiPoint, box
from shapely.ops import unary_union

from ..config import StencilConfig

logger = logging.getLogger(__name__)


def regenerate_qfn_paste(geometry, config: StencilConfig):
    polys = _flatten_polygons(geometry)
    if not polys:
        return geometry
    pads = _detect_qfn_pads(polys, config)
    if pads is None:
        return geometry
    qfn, score = _build_qfn_group(pads, polys, config)
    if qfn is None or score < config.qfn_confidence_threshold:
        return geometry
    logger.info("QFN detect: pads=%s score=%.2f", len(qfn["pads"]), score)
    regenerated = _regenerate_qfn_geometry(qfn, polys, config)
    if regenerated is None:
        return geometry
    return regenerated


def _flatten_polygons(geometry):
    if geometry is None or geometry.is_empty:
        return []
    if geometry.geom_type == "Polygon":
        return [geometry]
    if geometry.geom_type == "MultiPolygon":
        return list(geometry.geoms)
    polygons = []
    if hasattr(geometry, "geoms"):
        for geom in geometry.geoms:
            if geom.geom_type == "Polygon":
                polygons.append(geom)
            elif geom.geom_type == "MultiPolygon":
                polygons.extend(list(geom.geoms))
    return polygons


def _detect_qfn_pads(polys, config: StencilConfig):
    pads = []
    for poly in polys:
        metrics = _polygon_rect_metrics(poly)
        if metrics is None:
            continue
        rect_area, long_side, short_side, angle = metrics
        if rect_area <= 0:
            continue
        rectangularity = poly.area / rect_area
        aspect = long_side / short_side if short_side > 0 else 0
        if rectangularity < 0.85:
            continue
        if not 1.2 <= aspect <= 6.0:
            continue
        if short_side > config.qfn_max_pad_width_mm:
            continue
        pads.append(
            {
                "poly": poly,
                "center": (poly.centroid.x, poly.centroid.y),
                "angle": angle,
                "long": long_side,
                "short": short_side,
            }
        )
    if len(pads) < 12:
        return None
    return pads


def _polygon_rect_metrics(poly):
    try:
        rect = poly.minimum_rotated_rectangle
    except Exception:
        return None
    coords = list(rect.exterior.coords)
    if len(coords) < 4:
        return None
    edges = []
    for i in range(4):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % 4]
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        edges.append((length, dx, dy))
    edges.sort(key=lambda e: e[0], reverse=True)
    long_len, long_dx, long_dy = edges[0]
    short_len = edges[-1][0]
    angle = math.degrees(math.atan2(long_dy, long_dx))
    angle = _normalize_angle(angle)
    return rect.area, long_len, short_len, angle


def _normalize_angle(angle_deg: float) -> float:
    angle = angle_deg % 180.0
    if angle < 0:
        angle += 180.0
    return angle


def _rotate_point(point, angle_deg: float):
    x, y = point
    radians = math.radians(angle_deg)
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    return (x * cos_a - y * sin_a, x * sin_a + y * cos_a)


def _build_qfn_group(pads, polys, config: StencilConfig):
    centers = [p["center"] for p in pads]
    rect = MultiPoint(centers).minimum_rotated_rectangle
    rect_metrics = _polygon_rect_metrics(rect)
    if rect_metrics is None:
        return None, 0.0
    _, _, _, global_angle = rect_metrics
    for pad in pads:
        pad["center_norm"] = _rotate_point(pad["center"], -global_angle)
        pad["angle_norm"] = _normalize_angle(pad["angle"] - global_angle)

    horizontal = []
    vertical = []
    for pad in pads:
        angle = pad["angle_norm"]
        if angle <= 30 or angle >= 150:
            horizontal.append(pad)
        elif 60 <= angle <= 120:
            vertical.append(pad)
    if len(horizontal) < 6 or len(vertical) < 6:
        return None, 0.0

    horiz_rows = _cluster_rows(horizontal, axis="y", config=config)
    vert_rows = _cluster_rows(vertical, axis="x", config=config)
    if not horiz_rows or not vert_rows:
        return None, 0.0

    center = _estimate_center(pads)
    qfn = _pick_qfn_sides(horiz_rows, vert_rows, center)
    if qfn is None:
        return None, 0.0

    center_pad = _detect_center_pad(polys, center, pads, global_angle)
    qfn["center_pad"] = center_pad
    qfn["global_angle"] = global_angle
    score = _score_qfn(qfn)
    return qfn, score


def _cluster_rows(pads, axis: str, config: StencilConfig):
    widths = [p["short"] for p in pads if p["short"] > 0]
    if not widths:
        return []
    width_median = _median(widths)
    tol = max(width_median * 1.5, config.qfn_min_feature_mm * 0.5)
    key_index = 1 if axis == "y" else 0
    sorted_pads = sorted(pads, key=lambda p: p["center_norm"][key_index])
    rows = []
    current = []
    last_value = None
    for pad in sorted_pads:
        value = pad["center_norm"][key_index]
        if last_value is None or abs(value - last_value) <= tol:
            current.append(pad)
        else:
            if len(current) >= 3:
                rows.append(_make_row(current, axis))
            current = [pad]
        last_value = value
    if len(current) >= 3:
        rows.append(_make_row(current, axis))
    return rows


def _make_row(pads, axis: str):
    direction_axis = "x" if axis == "y" else "y"
    if direction_axis == "x":
        pads_sorted = sorted(pads, key=lambda p: p["center_norm"][0])
        coord = _median([p["center_norm"][1] for p in pads])
    else:
        pads_sorted = sorted(pads, key=lambda p: p["center_norm"][1])
        coord = _median([p["center_norm"][0] for p in pads])
    return {
        "pads": pads_sorted,
        "axis": axis,
        "coord": coord,
    }


def _estimate_center(pads):
    xs = [p["center_norm"][0] for p in pads]
    ys = [p["center_norm"][1] for p in pads]
    return (_median(xs), _median(ys))


def _pick_qfn_sides(horiz_rows, vert_rows, center):
    if len(horiz_rows) < 2 or len(vert_rows) < 2:
        return None
    horiz_rows = sorted(horiz_rows, key=lambda r: r["coord"])
    vert_rows = sorted(vert_rows, key=lambda r: r["coord"])
    bottom = horiz_rows[0]
    top = horiz_rows[-1]
    left = vert_rows[0]
    right = vert_rows[-1]
    sides = [top, right, bottom, left]
    if any(len(side["pads"]) < 3 for side in sides):
        return None
    counts = [len(side["pads"]) for side in sides]
    if max(counts) - min(counts) > max(2, int(0.3 * max(counts))):
        return None
    pads = []
    for side in sides:
        pads.extend(side["pads"])
    return {
        "top": top,
        "bottom": bottom,
        "left": left,
        "right": right,
        "pads": pads,
        "center_norm": center,
    }


def _detect_center_pad(polys, center_norm, pads, global_angle):
    pad_areas = [p["poly"].area for p in pads]
    if not pad_areas:
        return None
    area_median = _median(pad_areas)
    max_poly = None
    max_area = 0.0
    for poly in polys:
        if poly.area < area_median * 4.0:
            continue
        center = (poly.centroid.x, poly.centroid.y)
        center_rot = _rotate_point(center, -global_angle)
        dx = center_rot[0] - center_norm[0]
        dy = center_rot[1] - center_norm[1]
        distance = math.hypot(dx, dy)
        if distance > max(1.0, area_median ** 0.5 * 4.0):
            continue
        if poly.area > max_area:
            max_area = poly.area
            max_poly = poly
    return max_poly


def _score_qfn(qfn):
    scores = []
    spacing_scores = []
    for side in (qfn["top"], qfn["bottom"], qfn["left"], qfn["right"]):
        pitches = _side_pitches(side)
        spacing_scores.append(_score_variation(pitches, target_cv=0.2))
    scores.append(_average(spacing_scores))
    pad_widths = [p["short"] for p in qfn["pads"]]
    scores.append(_score_variation(pad_widths, target_cv=0.25))
    counts = [
        len(qfn["top"]["pads"]),
        len(qfn["bottom"]["pads"]),
        len(qfn["left"]["pads"]),
        len(qfn["right"]["pads"]),
    ]
    symmetry = 1.0 - (max(counts) - min(counts)) / max(counts)
    scores.append(max(0.0, symmetry))
    scores.append(1.0)
    base = _average(scores)
    if qfn.get("center_pad") is not None:
        base = min(1.0, base + 0.05)
    return base


def _side_pitches(side):
    pads = side["pads"]
    if len(pads) < 2:
        return []
    if side["axis"] == "y":
        coords = [p["center_norm"][0] for p in pads]
    else:
        coords = [p["center_norm"][1] for p in pads]
    coords = sorted(coords)
    return [coords[i + 1] - coords[i] for i in range(len(coords) - 1)]


def _score_variation(values, target_cv: float):
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    if mean <= 0:
        return 0.0
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    cv = math.sqrt(variance) / mean
    return max(0.0, 1.0 - cv / target_cv)


def _average(values):
    if not values:
        return 0.0
    return sum(values) / len(values)


def _median(values):
    values = sorted(values)
    if not values:
        return 0.0
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) / 2.0


def _regenerate_qfn_geometry(qfn, polys, config: StencilConfig):
    min_feature = config.qfn_min_feature_mm
    slots = []
    kept = []
    pad_set = {id(p["poly"]) for p in qfn["pads"]}
    center_pad = qfn.get("center_pad")
    for poly in polys:
        if id(poly) in pad_set:
            continue
        if center_pad is not None and poly.equals(center_pad):
            continue
        kept.append(poly)

    for side in (qfn["top"], qfn["bottom"], qfn["left"], qfn["right"]):
        pitch, pad_width = _estimate_pitch_and_width(side)
        if pitch is None or pad_width is None:
            return None
        web = pitch - pad_width
        if web < min_feature:
            side_slots = _generate_slots_for_side(side, qfn, min_feature)
            if not side_slots:
                return None
            slots.extend(side_slots)
        else:
            kept.extend([p["poly"] for p in side["pads"]])

    if center_pad is not None:
        windows = _generate_center_windowpane(center_pad, qfn, min_feature)
        if windows:
            kept.extend(windows)
        else:
            kept.append(center_pad)

    merged = unary_union(kept + slots)
    return merged


def _estimate_pitch_and_width(side):
    pitches = _side_pitches(side)
    if not pitches:
        return None, None
    pitch = _median(pitches)
    widths = [p["short"] for p in side["pads"]]
    pad_width = _median(widths)
    return pitch, pad_width


def _generate_slots_for_side(side, qfn, min_feature):
    pads = side["pads"]
    count = len(pads)
    if count <= 6:
        slots_count = 2
    elif count <= 12:
        slots_count = 3
    else:
        slots_count = 4

    if side["axis"] == "y":
        coords = [p["center_norm"][0] for p in pads]
        row_coord = side["coord"]
        direction = "x"
    else:
        coords = [p["center_norm"][1] for p in pads]
        row_coord = side["coord"]
        direction = "y"

    coord_min = min(coords)
    coord_max = max(coords)
    span = coord_max - coord_min
    if span <= 0:
        return []

    pad_width = _median([p["short"] for p in pads])
    slot_width = max(min_feature, pad_width)
    slot_length = max(2 * slot_width, min(span * 0.8, span))
    slot_length = max(slot_length, span * 0.6)

    centers = []
    for i in range(slots_count):
        t = (i + 0.5) / slots_count
        center = coord_min + t * span
        low = coord_min + slot_length / 2.0
        high = coord_max - slot_length / 2.0
        if high < low:
            center = (coord_min + coord_max) / 2.0
        else:
            center = max(low, min(high, center))
        centers.append(center)

    outward = _outward_sign(side, qfn["center_norm"])
    bias = min(0.3 * slot_width, 0.25)
    slots = []
    for center in centers:
        if direction == "x":
            cx, cy = center, row_coord + outward * bias
            slot = box(
                cx - slot_length / 2.0,
                cy - slot_width / 2.0,
                cx + slot_length / 2.0,
                cy + slot_width / 2.0,
            )
        else:
            cx, cy = row_coord + outward * bias, center
            slot = box(
                cx - slot_width / 2.0,
                cy - slot_length / 2.0,
                cx + slot_width / 2.0,
                cy + slot_length / 2.0,
            )
        slot = affinity.rotate(slot, qfn["global_angle"], origin=(0, 0))
        slots.append(slot)
    return slots


def _outward_sign(side, center_norm):
    if side["axis"] == "y":
        return 1.0 if side["coord"] > center_norm[1] else -1.0
    return 1.0 if side["coord"] > center_norm[0] else -1.0


def _generate_center_windowpane(center_pad, qfn, min_feature):
    rotated = affinity.rotate(center_pad, -qfn["global_angle"], origin=(0, 0))
    bounds = rotated.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= min_feature * 2 or height <= min_feature * 2:
        return None
    if min(width, height) < 3.0:
        rows = cols = 2
    elif min(width, height) < 6.0:
        rows = cols = 3
    else:
        rows = cols = 4

    web = min_feature
    cell_w_max = (width - (cols + 1) * web) / cols
    cell_h_max = (height - (rows + 1) * web) / rows
    if cell_w_max < min_feature or cell_h_max < min_feature:
        return None

    target_area = rotated.area * 0.5
    max_area = cell_w_max * cell_h_max * rows * cols
    scale = math.sqrt(min(1.0, target_area / max_area))
    cell_w = max(min_feature, cell_w_max * scale)
    cell_h = max(min_feature, cell_h_max * scale)

    total_w = cols * cell_w + (cols - 1) * web
    total_h = rows * cell_h + (rows - 1) * web
    start_x = (bounds[0] + bounds[2]) / 2.0 - total_w / 2.0
    start_y = (bounds[1] + bounds[3]) / 2.0 - total_h / 2.0

    windows = []
    for r in range(rows):
        for c in range(cols):
            x0 = start_x + c * (cell_w + web)
            y0 = start_y + r * (cell_h + web)
            rect = box(x0, y0, x0 + cell_w, y0 + cell_h)
            rect = rect.intersection(rotated)
            if rect.is_empty or rect.area < min_feature * min_feature * 0.5:
                continue
            rect = affinity.rotate(rect, qfn["global_angle"], origin=(0, 0))
            windows.append(rect)
    return windows if windows else None
