from __future__ import annotations

"""调试输出：几何统计、PNG/SVG 渲染、GKO 路径可视化。"""

import logging
import math
from pathlib import Path

from PIL import Image, ImageDraw
from shapely.geometry import LineString
from shapely.ops import linemerge, unary_union
from shapely.validation import explain_validity

from ..config import StencilConfig
from .geometry import count_holes, count_polygons

logger = logging.getLogger(__name__)


def resolve_debug_dir(output_path: Path, config: StencilConfig) -> Path | None:
    # 根据配置解析调试输出目录（支持相对路径）
    if not config.debug_enabled:
        return None
    if not config.debug_dump_dir:
        return None
    base = Path(config.debug_dump_dir)
    if not base.is_absolute():
        base = Path.cwd() / base
    try:
        base.mkdir(parents=True, exist_ok=True)
        return base
    except OSError:
        logger.warning("Failed to create debug dump dir: %s", base)
        return None


def log_geometry(label: str, geom, detail: bool) -> None:
    # 统一输出几何统计信息，便于诊断异常
    if geom is None:
        logger.info("%s geometry: None", label)
        return
    if geom.is_empty:
        logger.info("%s geometry: empty", label)
        return
    poly_count = count_polygons(geom)
    hole_count = count_holes(geom)
    logger.info(
        "%s geometry: type=%s area=%.6f bounds=%s polygons=%s holes=%s",
        label,
        geom.geom_type,
        geom.area,
        geom.bounds,
        poly_count,
        hole_count,
    )
    if detail:
        try:
            valid = geom.is_valid
        except Exception:
            valid = None
        if valid is False:
            try:
                reason = explain_validity(geom)
            except Exception:
                reason = "unknown"
            logger.info("%s geometry validity: invalid (%s)", label, reason)
        elif valid is True:
            logger.info("%s geometry validity: ok", label)


def dump_geometry(out_dir: Path | None, name: str, geom) -> None:
    # 同时输出 WKT/SVG/PNG，便于对比中间产物
    if out_dir is None or geom is None or geom.is_empty:
        return
    safe = name.replace(" ", "_").lower()
    try:
        (out_dir / f"{safe}.wkt").write_text(geom.wkt, encoding="utf-8")
    except OSError:
        pass
    try:
        svg = geometry_svg(geom, stroke="#1f2937")
        if svg:
            (out_dir / f"{safe}.svg").write_text(svg, encoding="utf-8")
    except OSError:
        pass
    try:
        png = geometry_png(geom, stroke="#1f2937")
        if png is not None:
            png.save(out_dir / f"{safe}.png")
    except OSError:
        pass


def geometry_svg(geom, stroke: str) -> str:
    # 使用 shapely.svg 生成基础 SVG，并重设 viewBox
    if geom is None or geom.is_empty:
        return ""
    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= 0 or height <= 0:
        return ""
    padding = 2.0
    view = (
        bounds[0] - padding,
        bounds[1] - padding,
        width + padding * 2,
        height + padding * 2,
    )
    svg = geom.svg(scale_factor=1.0)
    svg = svg.replace(
        "<svg ",
        f"<svg viewBox=\"{view[0]} {view[1]} {view[2]} {view[3]}\" ",
    )
    svg = svg.replace(
        "fill=\"none\"",
        f"fill=\"none\" stroke=\"{stroke}\" stroke-width=\"0.1\"",
    )
    return svg


def geometry_png(geom, stroke: str, target_size: int = 1024) -> Image.Image | None:
    # 将几何按比例映射到画布，并绘制边线
    if geom is None or geom.is_empty:
        return None
    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= 0 or height <= 0:
        return None
    scale = float(target_size) / max(width, height)
    padding = 10
    img_w = max(int(width * scale) + padding * 2, 1)
    img_h = max(int(height * scale) + padding * 2, 1)
    image = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(image)

    def map_point(point) -> tuple[float, float]:
        x, y = point
        px = (x - bounds[0]) * scale + padding
        py = (bounds[3] - y) * scale + padding
        return (px, py)

    def draw_poly(poly) -> None:
        exterior = [map_point(p) for p in poly.exterior.coords]
        if len(exterior) >= 2:
            draw.line(exterior, fill=stroke, width=2)
        for interior in poly.interiors:
            ring = [map_point(p) for p in interior.coords]
            if len(ring) >= 2:
                draw.line(ring, fill=stroke, width=1)

    def draw_line(line) -> None:
        coords = [map_point(p) for p in line.coords]
        if len(coords) >= 2:
            draw.line(coords, fill=stroke, width=1)

    def draw_geom(item) -> None:
        if item is None or item.is_empty:
            return
        if item.geom_type == "Polygon":
            draw_poly(item)
        elif item.geom_type == "MultiPolygon":
            for poly in item.geoms:
                draw_poly(poly)
        elif item.geom_type == "LineString":
            draw_line(item)
        elif item.geom_type == "MultiLineString":
            for line in item.geoms:
                draw_line(line)
        elif item.geom_type == "GeometryCollection":
            for sub in item.geoms:
                draw_geom(sub)

    draw_geom(geom)
    return image


def geometry_png_with_markers(geom, points, stroke: str, marker: str) -> Image.Image | None:
    # 在几何渲染图上额外标注端点或断点
    if geom is None or geom.is_empty:
        return None
    image = geometry_png(geom, stroke=stroke)
    if image is None:
        return None
    draw = ImageDraw.Draw(image)
    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= 0 or height <= 0:
        return image
    scale = float(1024) / max(width, height)
    padding = 10

    def map_point(point) -> tuple[float, float]:
        x, y = point
        px = (x - bounds[0]) * scale + padding
        py = (bounds[3] - y) * scale + padding
        return (px, py)

    for point in points:
        px, py = map_point(point)
        draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline=marker, width=2)
    return image


def dump_colored_segments_png(out_dir: Path | None, name: str, geom, target_size: int = 1024) -> None:
    # DEBUG: 线段按序着色，并用偏移实心圆标注端点。
    if out_dir is None or geom is None or geom.is_empty:
        return
    bounds = geom.bounds
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    if width <= 0 or height <= 0:
        return
    scale = float(target_size) / max(width, height)
    padding = 10
    img_w = max(int(width * scale) + padding * 2, 1)
    img_h = max(int(height * scale) + padding * 2, 1)
    image = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(image)
    colors = [
        "#1f2937",
        "#0f766e",
        "#7c2d12",
        "#1d4ed8",
        "#6d28d9",
        "#9f1239",
        "#15803d",
    ]
    lines = []

    def map_point(point) -> tuple[float, float]:
        x, y = point
        px = (x - bounds[0]) * scale + padding
        py = (bounds[3] - y) * scale + padding
        return (px, py)

    def collect_lines(item) -> None:
        if item is None or item.is_empty:
            return
        if item.geom_type == "LineString":
            lines.append(item)
        elif item.geom_type == "MultiLineString":
            lines.extend(item.geoms)
        elif item.geom_type == "GeometryCollection":
            for sub in item.geoms:
                collect_lines(sub)

    collect_lines(geom)
    if not lines:
        return
    for idx, line in enumerate(lines):
        coords = [map_point(p) for p in line.coords]
        if len(coords) < 2:
            continue
        color = colors[idx % len(colors)]
        draw.line(coords, fill=color, width=2)
        sx, sy = coords[0]
        ex, ey = coords[-1]
        jitter = 4.0
        angle = (idx * 0.61803398875) % (2 * math.pi)
        ox = math.cos(angle) * jitter
        oy = math.sin(angle) * jitter
        radius = 4
        draw.ellipse(
            (sx + ox - radius, sy + oy - radius, sx + ox + radius, sy + oy + radius),
            fill=color,
            outline=color,
        )
        draw.ellipse(
            (ex - ox - radius, ey - oy - radius, ex - ox + radius, ey - oy + radius),
            fill=color,
            outline=color,
        )
    safe = name.replace(" ", "_").lower()
    image.save(out_dir / f"{safe}.png")


def dump_gko_paths_png(path: Path, out_dir: Path, px_per_mm: float = 10.0) -> None:
    # 将 GKO 线段按“路径索引”上色，便于检查路径连续性
    segments = _parse_gko_paths(path)
    if not segments:
        return
    segments = _merge_colinear_segments(segments, tol=1e-6)
    points = []
    for segment, _ in segments:
        points.extend(segment)
    min_x = min(p[0] for p in points)
    min_y = min(p[1] for p in points)
    max_x = max(p[0] for p in points)
    max_y = max(p[1] for p in points)
    width = max_x - min_x
    height = max_y - min_y
    if width <= 0 or height <= 0:
        return
    padding = 10
    img_w = max(int(width * px_per_mm) + padding * 2, 1)
    img_h = max(int(height * px_per_mm) + padding * 2, 1)
    image = Image.new("RGB", (img_w, img_h), "white")
    draw = ImageDraw.Draw(image)
    colors = [
        "#1f2937",
        "#0f766e",
        "#7c2d12",
        "#1d4ed8",
        "#6d28d9",
        "#9f1239",
        "#15803d",
    ]

    def map_point(point):
        x, y = point
        px = (x - min_x) * px_per_mm + padding
        py = (max_y - y) * px_per_mm + padding
        return (px, py)

    for seg_idx, (segment, color_idx) in enumerate(segments):
        coords = [map_point(p) for p in segment]
        if len(coords) >= 2:
            draw.line(coords, fill=colors[color_idx % len(colors)], width=2)
            sx, sy = coords[0]
            ex, ey = coords[-1]
            color = colors[color_idx % len(colors)]
            jitter = 4.0
            angle = (seg_idx * 0.61803398875) % (2 * math.pi)
            ox = math.cos(angle) * jitter
            oy = math.sin(angle) * jitter
            draw.ellipse((sx + ox - 3, sy + oy - 3, sx + ox + 3, sy + oy + 3), fill=color, outline=color)
            draw.ellipse((ex - ox - 3, ey - oy - 3, ex - ox + 3, ey - oy + 3), fill=color, outline=color)
    gap = _max_gap_pair_from_segments(segments)
    if gap is not None:
        p1, p2, _ = gap
        for point in (p1, p2):
            px, py = map_point(point)
            draw.ellipse((px - 6, py - 6, px + 6, py + 6), outline="#dc2626", width=2)
    image.save(out_dir / "step2_outline_segments_paths.png")
    image.save(out_dir / "step2_outline_segments_paths_deduped.png")


def _parse_gko_paths(path: Path):
    # 只解析常见的 G01/G02/G03 + D01/D02 指令，足够用于调试
    text = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    scale = 1e5
    for line in text:
        if line.startswith("%FSLAX"):
            digits = line.strip("%*")
            parts = digits.replace("FSLAX", "").split("Y")
            if len(parts) == 2 and len(parts[0]) == 2:
                try:
                    scale = 10 ** int(parts[0][1])
                except ValueError:
                    pass
            break

    mode = "G01"
    current = None
    segments = []
    path_index = 0

    def parse_coord(line, key):
        if key not in line:
            return None
        idx = line.find(key) + 1
        num = []
        while idx < len(line) and (line[idx].isdigit() or line[idx] in "+-"):
            num.append(line[idx])
            idx += 1
        if not num:
            return None
        return int("".join(num)) / scale

    for raw in text:
        line = raw.strip()
        if not line or line.startswith("G04") or line.startswith("%") or line.startswith("M02"):
            continue
        if "G01" in line:
            mode = "G01"
        elif "G02" in line:
            mode = "G02"
        elif "G03" in line:
            mode = "G03"

        d01 = "D01" in line
        d02 = "D02" in line

        x = parse_coord(line, "X")
        y = parse_coord(line, "Y")
        i = parse_coord(line, "I")
        j = parse_coord(line, "J")
        if x is None and y is None and not d02 and not d01:
            continue
        if x is None and current is not None:
            x = current[0]
        if y is None and current is not None:
            y = current[1]
        if x is None or y is None:
            continue
        next_point = (x, y)
        if d02:
            current = next_point
            path_index += 1
            continue
        if d01 and current is not None:
            if mode in ("G02", "G03") and i is not None and j is not None:
                center = (current[0] + i, current[1] + j)
                arc = _arc_points_raw(current, next_point, center, mode == "G03", steps=64)
                segments.append((arc, path_index))
            else:
                segments.append(([current, next_point], path_index))
        current = next_point
    return segments


def _merge_intersections(segments):
    # 利用 shapely 处理线段交叉与合并（调试备用）
    if not segments:
        return segments
    lines = []
    for seg, _ in segments:
        if len(seg) >= 2:
            lines.append(LineString(seg))
    if not lines:
        return segments
    merged = unary_union(lines)
    merged = linemerge(merged)
    flat = []
    if isinstance(merged, LineString):
        flat = [merged]
    elif hasattr(merged, "geoms"):
        flat = list(merged.geoms)
    merged_segments = [(list(line.coords), idx) for idx, line in enumerate(flat) if len(line.coords) >= 2]
    logger.info("Outline segments merged: %s -> %s", len(segments), len(merged_segments))
    return merged_segments


def _points_close(p1, p2, tol: float) -> bool:
    dx = p1[0] - p2[0]
    dy = p1[1] - p2[1]
    return (dx * dx + dy * dy) ** 0.5 <= tol


def _colinear(p1, p2, p3, tol: float) -> bool:
    dx1 = p2[0] - p1[0]
    dy1 = p2[1] - p1[1]
    dx2 = p3[0] - p2[0]
    dy2 = p3[1] - p2[1]
    cross = dx1 * dy2 - dy1 * dx2
    return abs(cross) <= tol


def _merge_colinear_segments(segments, tol: float):
    # 同路径相邻共线线段合并，减少视觉杂线
    merged = []
    for seg, path_idx in segments:
        if not merged:
            merged.append((seg, path_idx))
            continue
        last_seg, last_idx = merged[-1]
        if (
            path_idx == last_idx
            and len(last_seg) == 2
            and len(seg) == 2
            and _points_close(last_seg[-1], seg[0], tol)
            and _colinear(last_seg[0], last_seg[1], seg[1], tol)
        ):
            merged[-1] = ([last_seg[0], seg[1]], path_idx)
        else:
            merged.append((seg, path_idx))
    return merged


def _segment_key(seg, tol: float):
    if len(seg) < 2:
        return None

    def r(p):
        return (round(p[0], 6), round(p[1], 6))

    first = r(seg[0])
    last = r(seg[-1])
    mid = r(seg[len(seg) // 2])
    ends = tuple(sorted((first, last)))
    return (ends, mid)


def _dedupe_segments(segments, tol: float):
    seen = set()
    kept = []
    removed = 0
    for seg, idx in segments:
        key = _segment_key(seg, tol)
        if key is None:
            continue
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        kept.append((seg, idx))
    return kept, removed


def _max_gap_pair_from_segments(segments):
    # 找到距离最近端点最大的一对，作为“最明显断点”
    endpoints = []
    for segment, _ in segments:
        if len(segment) < 2:
            continue
        endpoints.append(segment[0])
        endpoints.append(segment[-1])
    if len(endpoints) < 2:
        return None
    max_dist = -1.0
    max_pair = None
    for i, p1 in enumerate(endpoints):
        min_dist = None
        min_point = None
        for j, p2 in enumerate(endpoints):
            if i == j:
                continue
            dx = p1[0] - p2[0]
            dy = p1[1] - p2[1]
            dist = (dx * dx + dy * dy) ** 0.5
            if min_dist is None or dist < min_dist:
                min_dist = dist
                min_point = p2
        if min_dist is not None and min_dist > max_dist:
            max_dist = min_dist
            max_pair = (p1, min_point, min_dist)
    return max_pair


def _arc_points_raw(start, end, center, ccw: bool, steps: int = 64):
    # 将圆弧离散成线段点序列
    sx, sy = start
    ex, ey = end
    cx, cy = center
    start_angle = math.atan2(sy - cy, sx - cx)
    end_angle = math.atan2(ey - cy, ex - cx)
    if ccw:
        if end_angle <= start_angle:
            end_angle += 2 * math.pi
        angles = [start_angle + (end_angle - start_angle) * i / (steps - 1) for i in range(steps)]
    else:
        if end_angle >= start_angle:
            end_angle -= 2 * math.pi
        angles = [start_angle + (end_angle - start_angle) * i / (steps - 1) for i in range(steps)]
    radius = math.hypot(sx - cx, sy - cy)
    return [(cx + radius * math.cos(a), cy + radius * math.sin(a)) for a in angles]


def write_debug_svg(output_path: Path, outline, paste, stencil) -> None:
    # 输出三层叠加的 SVG 便于快速比对
    if output_path is None:
        return
    out_dir = output_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, geom, color in (
        ("outline", outline, "#d64545"),
        ("paste", paste, "#2e7d32"),
        ("stencil", stencil, "#1e3a8a"),
    ):
        if geom is None or geom.is_empty:
            continue
        bounds = geom.bounds
        width = bounds[2] - bounds[0]
        height = bounds[3] - bounds[1]
        if width <= 0 or height <= 0:
            continue
        padding = 2.0
        view = (
            bounds[0] - padding,
            bounds[1] - padding,
            width + padding * 2,
            height + padding * 2,
        )
        svg = geom.svg(scale_factor=1.0)
        svg = svg.replace(
            "<svg ",
            f"<svg viewBox=\"{view[0]} {view[1]} {view[2]} {view[3]}\" ",
        )
        svg = svg.replace(
            "fill=\"none\"",
            f"fill=\"none\" stroke=\"{color}\" stroke-width=\"0.1\"",
        )
        (out_dir / f"stencil_debug_{name}.svg").write_text(svg, encoding="utf-8")
