from __future__ import annotations

import math
from dataclasses import dataclass, field

from shapely.geometry import Point, Polygon


@dataclass
class ShapeMetrics:
    area_mm2: float = 0.0
    rectangularity: float = 0.0
    circularity: float = 0.0
    aspect_ratio: float = 1.0
    short_side_mm: float = 0.0
    long_side_mm: float = 0.0


@dataclass
class PadInfo:
    polygon: Polygon
    pad_type: str  # "THT", "Thermal", "BGA", "SMD"
    shape: ShapeMetrics = field(default_factory=ShapeMetrics)


# ---------------------------------------------------------------------------
# shape feature extraction
# ---------------------------------------------------------------------------

def compute_shape_metrics(poly: Polygon) -> ShapeMetrics:
    """Compute geometric fingerprint for a single polygon."""
    if poly.is_empty or poly.area <= 0:
        return ShapeMetrics()

    area = poly.area
    perimeter = poly.length
    try:
        min_rect = poly.minimum_rotated_rectangle
    except Exception:
        min_rect = poly.envelope.projected.cast_to_geometry()

    mbr_area = min_rect.area
    rectangularity = area / mbr_area if mbr_area > 0 else 0.0
    circularity = (4 * math.pi * area) / (perimeter ** 2) if perimeter > 0 else 0.0

    # side lengths from MBR
    coords = list(min_rect.exterior.coords)
    if len(coords) >= 4:
        side1 = math.hypot(coords[1][0] - coords[0][0], coords[1][1] - coords[0][1])
        side2 = math.hypot(coords[2][0] - coords[1][0], coords[2][1] - coords[1][1])
        short = min(side1, side2)
        long = max(side1, side2)
    else:
        short = long = math.sqrt(area)

    aspect = long / short if short > 0 else 1.0

    return ShapeMetrics(
        area_mm2=area,
        rectangularity=rectangularity,
        circularity=circularity,
        aspect_ratio=aspect,
        short_side_mm=short,
        long_side_mm=long,
    )


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

def classify_pads(
    polygons: list[Polygon],
    drill_holes: list[tuple[float, float, float]],
) -> list[PadInfo]:
    """Classify each paste polygon by pad type using a shape-aware rule chain.

    Rule chain (first match wins):
    1. Contains drill hole 鈫?THT
    2. Area 鈮?thermal_area_threshold 鈫?Thermal
    3. Small + nearly circular + compact 鈫?BGA
    4. All others 鈫?SMD
    """
    if not polygons:
        return []

    hole_points = [Point(x, y) for x, y, _d in drill_holes]
    shapes = [compute_shape_metrics(p) for p in polygons]
    areas = [s.area_mm2 for s in shapes if s.area_mm2 > 0]

    if areas:
        median_area = sorted(areas)[len(areas) // 2]
    else:
        median_area = 0.0

    thermal_threshold = _thermal_threshold(areas, median_area)

    result: list[PadInfo] = []
    for poly, shape in zip(polygons, shapes):
        pad_type = _classify_single(poly, shape, hole_points, thermal_threshold)
        result.append(PadInfo(polygon=poly, pad_type=pad_type, shape=shape))

    return result


def _thermal_threshold(areas: list[float], median: float) -> float:
    """Compute adaptive thermal pad area threshold."""
    absolute = 2.0  # mm虏
    relative = max(median * 5.0, 0.5) if median > 0 else absolute
    return max(absolute, relative)


def _classify_single(
    poly: Polygon,
    shape: ShapeMetrics,
    hole_points: list[Point],
    thermal_threshold: float,
) -> str:
    if poly.is_empty or shape.area_mm2 <= 0:
        return "SMD"

    # 1 鈫?THT
    for pt in hole_points:
        if poly.contains(pt) or poly.touches(pt):
            return "THT"

    # 2 鈫?Thermal
    if shape.area_mm2 >= thermal_threshold:
        return "Thermal"

    # 3 鈫?BGA
    if (
        shape.circularity > 0.82
        and shape.rectangularity > 0.70
        and shape.aspect_ratio < 1.6
        and shape.short_side_mm <= 0.8
    ):
        return "BGA"

    # 4 鈫?SMD (catch-all: IC pins, discretes, connectors, etc.)
    return "SMD"


# ---------------------------------------------------------------------------
# classification summaries
# ---------------------------------------------------------------------------

def classification_summary(pad_infos: list[PadInfo]) -> dict[str, int]:
    """Return counts per pad type."""
    counts: dict[str, int] = {}
    for pi in pad_infos:
        counts[pi.pad_type] = counts.get(pi.pad_type, 0) + 1
    return counts
