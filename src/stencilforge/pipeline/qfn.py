from __future__ import annotations

"""QFN 再生成：识别 QFN 引脚阵列并重建锡膏开窗。"""

import logging
import math

from shapely import affinity
from shapely.geometry import MultiPoint, box
from shapely.ops import unary_union

from ..config import StencilConfig
from ..geometry import flatten_to_polygons

logger = logging.getLogger(__name__)

# --- detection thresholds ---
QFN_RECTANGULARITY_MIN = 0.85    # minimum area / min-rotated-rectangle ratio
QFN_ASPECT_RATIO_MIN = 1.2       # long_side / short_side lower bound
QFN_ASPECT_RATIO_MAX = 6.0       # long_side / short_side upper bound
QFN_MIN_CANDIDATE_COUNT = 12     # minimum pad count to consider as potential QFN

# --- orientation classification ---
QFN_HORIZONTAL_ANGLE_MAX = 30    # degrees: |angle| <= this → horizontal
QFN_VERTICAL_ANGLE_MIN = 60      # degrees: angle >= this (and <= 120) → vertical
QFN_VERTICAL_ANGLE_MAX = 120

# --- scoring weights ---
QFN_SCORE_PITCH_BONUS = 1.0      # base score offset when pitch consistency is good
QFN_SCORE_CENTER_PAD_BONUS = 0.05  # bonus for detecting a center thermal pad
QFN_SYMMETRY_TOLERANCE = 0.3     # fraction of max side count for symmetry check
QFN_MIN_SIDES_FOR_SYMMETRY = 2   # minimum rows/cols in each axis

# --- slot generation ---
QFN_SLOT_PAD_THRESHOLD_6 = 6     # pads per side threshold for short slots
QFN_SLOT_PAD_THRESHOLD_12 = 12   # pads per side threshold for long slots
QFN_SLOT_SEGMENT_OFFSET = 0.3    # fraction of slot_width for end-offset
QFN_SLOT_SEGMENT_COUNT_LONG = 3  # segments per pad when side is large

# --- windowpane ---
QFN_WINDOWPANE_ROWS_MIN = 3      # minimum rows in center pad windowpane
QFN_WINDOWPANE_COLS_MIN = 6      # minimum columns in center pad windowpane
QFN_WINDOWPANE_SPACING = 3.0     # mm between pane centres


def regenerate_qfn_paste(geometry, config: StencilConfig):
    # 主入口：识别 QFN、重建开窗；失败则回退原几何
    polys = flatten_to_polygons(geometry)
    if not polys:
        return geometry
    pads = _detect_qfn_pads(polys, config)
    if pads is None:
        return geometry
    qfn, score = _build_qfn_group(pads, polys, config)
    if qfn is None or score < config.qfn_confidence_threshold:
        return geometry
    logger.info("QFN detect: pads=%s score=%.2f", len(qfn["pads"]), score)
    if config.printer_profile == "fsm" and config.fsm_qfn_grouped_slots_enabled:
        if qfn.get("center_pad") is None:
            logger.info("FSM QFN grouped slots skipped: no center thermal pad detected")
            return geometry
        regenerated = _regenerate_fsm_qfn_geometry(qfn, polys, config)
    else:
        regenerated = _regenerate_qfn_geometry(qfn, polys, config)
    if regenerated is None:
        return geometry
    return regenerated


def _detect_qfn_pads(polys, config: StencilConfig):
    # 通过矩形度/长宽比筛选焊盘候选
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
        if rectangularity < QFN_RECTANGULARITY_MIN:
            continue
        if not QFN_ASPECT_RATIO_MIN <= aspect <= QFN_ASPECT_RATIO_MAX:
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
    if len(pads) < QFN_MIN_CANDIDATE_COUNT:
        return None
    return pads


def _polygon_rect_metrics(poly):
    # 计算最小外接矩形的长宽与角度
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
    best_qfn = None
    best_score = 0.0
    for component in _candidate_pad_components(pads, config):
        qfn, score = _build_qfn_group_from_component(component, polys, config)
        if qfn is not None and score > best_score:
            best_qfn = qfn
            best_score = score
    return best_qfn, best_score


def _candidate_pad_components(pads, config: StencilConfig):
    if len(pads) < QFN_MIN_CANDIDATE_COUNT:
        return []
    widths = [p["short"] for p in pads if p["short"] > 0]
    longs = [p["long"] for p in pads if p["long"] > 0]
    width_median = _median(widths) if widths else config.qfn_min_feature_mm
    long_median = _median(longs) if longs else config.qfn_min_feature_mm
    link_distance = max(config.qfn_min_feature_mm * 4.0, width_median * 5.0, long_median * 2.2)

    remaining = set(range(len(pads)))
    components = []
    while remaining:
        start = remaining.pop()
        stack = [start]
        component_indices = [start]
        while stack:
            current = stack.pop()
            cx, cy = pads[current]["center"]
            linked = []
            for idx in list(remaining):
                px, py = pads[idx]["center"]
                if math.hypot(px - cx, py - cy) <= link_distance:
                    linked.append(idx)
            for idx in linked:
                remaining.remove(idx)
                stack.append(idx)
                component_indices.append(idx)
        if len(component_indices) >= QFN_MIN_CANDIDATE_COUNT:
            components.append([pads[idx] for idx in component_indices])
    components.sort(key=len, reverse=True)
    return components


def _build_qfn_group_from_component(pads, polys, config: StencilConfig):
    # 通过旋转归一化 + 行列聚类，尝试构建 QFN 四边
    centers = [p["center"] for p in pads]
    rect = MultiPoint(centers).minimum_rotated_rectangle
    rect_metrics = _polygon_rect_metrics(rect)
    if rect_metrics is None:
        return None, 0.0
    _, rect_long, rect_short, global_angle = rect_metrics
    if rect_short > 0 and rect_long / rect_short < 1.15:
        global_angle = _estimate_square_qfn_angle(pads, global_angle)
    for pad in pads:
        pad["center_norm"] = _rotate_point(pad["center"], -global_angle)
        pad["angle_norm"] = _normalize_angle(pad["angle"] - global_angle)

    horizontal = []
    vertical = []
    for pad in pads:
        angle = pad["angle_norm"]
        if angle <= QFN_HORIZONTAL_ANGLE_MAX or angle >= 180 - QFN_HORIZONTAL_ANGLE_MAX:
            vertical.append(pad)
        elif QFN_VERTICAL_ANGLE_MIN <= angle <= QFN_VERTICAL_ANGLE_MAX:
            horizontal.append(pad)
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


def _estimate_square_qfn_angle(pads, fallback_angle: float) -> float:
    angle_offsets = []
    for pad in pads:
        angle = pad["angle"] % 90.0
        if angle > 45.0:
            angle -= 90.0
        angle_offsets.append(angle)
    if not angle_offsets:
        return fallback_angle
    return _normalize_angle(_median(angle_offsets))


def _cluster_rows(pads, axis: str, config: StencilConfig):
    # 在指定轴上聚类为行（容差与焊盘尺寸相关）
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
    # 从上下左右行中选出四边并做对称性检查
    if len(horiz_rows) < QFN_MIN_SIDES_FOR_SYMMETRY or len(vert_rows) < QFN_MIN_SIDES_FOR_SYMMETRY:
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
    if max(counts) - min(counts) > max(QFN_MIN_SIDES_FOR_SYMMETRY, int(QFN_SYMMETRY_TOLERANCE * max(counts))):
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
    # 根据面积与中心距离尝试识别中心焊盘
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
    # 根据间距一致性、宽度一致性、对称性评分
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
    scores.append(QFN_SCORE_PITCH_BONUS)
    base = _average(scores)
    if qfn.get("center_pad") is not None:
        base = min(1.0, base + QFN_SCORE_CENTER_PAD_BONUS)
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
    # 按四边焊盘生成 slots 或保持原焊盘
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


def _regenerate_fsm_qfn_geometry(qfn, polys, config: StencilConfig):
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

    original_area = 0.0
    slot_area = 0.0
    slot_count = 0
    replaced_pads = 0
    for side in (qfn["top"], qfn["bottom"], qfn["left"], qfn["right"]):
        pad_width = _median([p["short"] for p in side["pads"]])
        pitches = _side_pitches(side)
        web = _median(pitches) - pad_width if pitches else 0.0
        should_replace = (
            pad_width < config.fsm_qfn_min_slot_width_mm
            or web < config.fsm_qfn_min_slot_gap_mm
        )
        if not should_replace:
            kept.extend([p["poly"] for p in side["pads"]])
            continue

        side_original = sum(p["poly"].area for p in side["pads"])
        side_slots = _generate_fsm_grouped_slots_for_side(side, qfn, config, side_original)
        if not side_slots:
            kept.extend([p["poly"] for p in side["pads"]])
            continue
        slots.extend(side_slots)
        original_area += side_original
        slot_area += sum(slot.area for slot in side_slots)
        slot_count += len(side_slots)
        replaced_pads += len(side["pads"])

    if center_pad is not None:
        windows = _generate_center_windowpane(center_pad, qfn, config.fsm_qfn_min_slot_width_mm)
        if windows:
            kept.extend(windows)
        else:
            kept.append(center_pad)

    if slots:
        target_area = original_area * config.fsm_qfn_target_volume_ratio
        error = (slot_area - target_area) / target_area if target_area > 0 else 0.0
        logger.info(
            "FSM QFN grouped slots: pads=%s slots=%s target_area=%.4f actual_area=%.4f error=%+.1f%%",
            replaced_pads,
            slot_count,
            target_area,
            slot_area,
            error * 100.0,
        )
    return unary_union(kept + slots)


def _generate_fsm_grouped_slots_for_side(side, qfn, config: StencilConfig, target_area: float | None = None):
    groups = _group_side_pads_for_fsm(side["pads"], config.fsm_qfn_max_pins_per_slot)
    if not groups:
        return []
    while True:
        intervals = [_fsm_group_interval(group, side, config) for group in groups]
        merged_groups, _merged_intervals = _merge_groups_until_gap_ok(
            groups,
            intervals,
            config.fsm_qfn_min_slot_gap_mm,
        )
        if len(merged_groups) == len(groups):
            break
        groups = merged_groups
    intervals = [_fsm_group_interval(group, side, config) for group in groups]

    slots = _make_fsm_slots_from_intervals(side, qfn, intervals, config.fsm_qfn_min_slot_width_mm)
    slots = _apply_fsm_qfn_corner_bridges(slots, qfn, config)
    if target_area is None:
        return slots

    target_area *= config.fsm_qfn_target_volume_ratio
    current_area = sum(slot.area for slot in slots)
    if current_area <= 0 or current_area >= target_area:
        return slots
    compensated_width = config.fsm_qfn_min_slot_width_mm * (target_area / current_area)
    compensated_slots = _make_fsm_slots_from_intervals(side, qfn, intervals, compensated_width)
    compensated_slots = _apply_fsm_qfn_corner_bridges(compensated_slots, qfn, config)
    return compensated_slots


def _make_fsm_slots_from_intervals(side, qfn, intervals, slot_width: float):
    slots = []
    outward = _outward_sign(side, qfn["center_norm"])
    bias = min(QFN_SLOT_SEGMENT_OFFSET * slot_width, 0.25)
    for low, high, center in intervals:
        slot_length = high - low
        if slot_length <= 0:
            continue
        if side["axis"] == "y":
            cx, cy = center, side["coord"] + outward * bias
            slot = box(
                cx - slot_length / 2.0,
                cy - slot_width / 2.0,
                cx + slot_length / 2.0,
                cy + slot_width / 2.0,
            )
        else:
            cx, cy = side["coord"] + outward * bias, center
            slot = box(
                cx - slot_width / 2.0,
                cy - slot_length / 2.0,
                cx + slot_width / 2.0,
                cy + slot_length / 2.0,
            )
        slots.append(affinity.rotate(slot, qfn["global_angle"], origin=(0, 0)))
    return slots


def _group_side_pads_for_fsm(pads, max_pins_per_slot: int):
    max_pins = max(2, int(max_pins_per_slot))
    groups = []
    for start in range(0, len(pads), max_pins):
        group = pads[start:start + max_pins]
        if len(group) == 1 and groups:
            groups[-1].extend(group)
        else:
            groups.append(list(group))
    return groups


def _fsm_group_interval(group, side, config: StencilConfig):
    axis_index = 0 if side["axis"] == "y" else 1
    coords = [p["center_norm"][axis_index] for p in group]
    center = sum(coords) / len(coords)
    coord_span = max(coords) - min(coords) if len(coords) > 1 else 0.0
    local_pad_width = _median([p["short"] for p in group])
    target_area = sum(p["poly"].area for p in group) * config.fsm_qfn_target_volume_ratio
    length_from_volume = target_area / config.fsm_qfn_min_slot_width_mm
    slot_length = max(
        config.fsm_qfn_min_slot_length_mm,
        coord_span + local_pad_width,
        length_from_volume,
    )
    return (center - slot_length / 2.0, center + slot_length / 2.0, center)


def _apply_fsm_qfn_corner_bridges(slots, qfn, config: StencilConfig):
    if not config.fsm_qfn_bridge_enabled:
        return slots
    bridge_width = max(
        config.fsm_qfn_bridge_width_mm,
        config.fsm_qfn_min_slot_width_mm * 2.0,
        config.fsm_qfn_min_slot_gap_mm * 2.0,
    )
    x_values = [qfn["left"]["coord"], qfn["right"]["coord"]]
    y_values = [qfn["bottom"]["coord"], qfn["top"]["coord"]]
    bridges = []
    for x in x_values:
        for y in y_values:
            bridge = box(
                x - bridge_width / 2.0,
                y - bridge_width / 2.0,
                x + bridge_width / 2.0,
                y + bridge_width / 2.0,
            )
            bridges.append(affinity.rotate(bridge, qfn["global_angle"], origin=(0, 0)))
    keepouts = unary_union(bridges)
    bridged_slots = []
    for slot in slots:
        bridged = slot.difference(keepouts)
        if not bridged.is_empty:
            bridged_slots.append(bridged)
    return bridged_slots or slots


def _merge_groups_until_gap_ok(groups, intervals, min_gap: float):
    if len(groups) <= 1 or min_gap <= 0:
        return groups, intervals
    merged_groups = [list(groups[0])]
    merged_intervals = [intervals[0]]
    for group, interval in zip(groups[1:], intervals[1:]):
        prev_low, prev_high, _prev_center = merged_intervals[-1]
        low, high, center = interval
        if low - prev_high < min_gap:
            merged_groups[-1].extend(group)
            new_low = min(prev_low, low)
            new_high = max(prev_high, high)
            merged_intervals[-1] = (new_low, new_high, (new_low + new_high) / 2.0)
        else:
            merged_groups.append(list(group))
            merged_intervals.append((low, high, center))
    return merged_groups, merged_intervals


def _estimate_pitch_and_width(side):
    pitches = _side_pitches(side)
    if not pitches:
        return None, None
    pitch = _median(pitches)
    widths = [p["short"] for p in side["pads"]]
    pad_width = _median(widths)
    return pitch, pad_width


def _generate_slots_for_side(side, qfn, min_feature):
    # 根据焊盘数量生成若干条 slot（减少锡膏）
    pads = side["pads"]
    count = len(pads)
    if count <= QFN_SLOT_PAD_THRESHOLD_6:
        slots_count = 2
    elif count <= QFN_SLOT_PAD_THRESHOLD_12:
        slots_count = QFN_SLOT_SEGMENT_COUNT_LONG
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
    bias = min(QFN_SLOT_SEGMENT_OFFSET * slot_width, 0.25)
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
    # 对中心焊盘进行分窗，改善回流焊空洞
    rotated = affinity.rotate(center_pad, -qfn["global_angle"], origin=(0, 0))
    bounds = rotated.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= min_feature * 2 or height <= min_feature * 2:
        return None
    if min(width, height) < QFN_WINDOWPANE_SPACING:
        rows = cols = 2
    elif min(width, height) < QFN_WINDOWPANE_SPACING * 2:
        rows = cols = QFN_WINDOWPANE_ROWS_MIN
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
