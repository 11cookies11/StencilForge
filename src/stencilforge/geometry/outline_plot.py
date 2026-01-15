from __future__ import annotations

import math
from statistics import mean
from typing import Iterable

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Rectangle


Point2D = tuple[float, float]
Segment2D = tuple[Point2D, Point2D]


def show_outline_debug_plot(debug: dict, plot_cfg: dict) -> None:
    raw_segments = list(debug.get("raw_segments", []))
    snapped_segments = list(debug.get("snapped_segments", []))
    deduped_segments = list(debug.get("deduped_segments", []))
    polygon_coords = debug.get("chosen_polygon_coords") or []
    bbox = debug.get("bbox")

    max_segments = int(plot_cfg.get("max_segments", 20000))
    max_vectors = int(plot_cfg.get("max_offset_vectors", 800))
    offset_min = float(plot_cfg.get("offset_min_mm", 0.0))
    eps = float(debug.get("eps_mm", 0.001))
    if offset_min <= 0:
        offset_min = eps * 0.2

    raw_segments = _sample_items(raw_segments, max_segments)
    snapped_segments = _sample_items(snapped_segments, max_segments)
    deduped_segments = _sample_items(deduped_segments, max_segments)

    offset_vectors = list(debug.get("offset_vectors", []))
    offset_vectors = _limit_offset_vectors(offset_vectors, max_vectors)
    offset_vectors = [vec for vec in offset_vectors if vec[2] >= offset_min]
    distances = [dist for _, _, dist in offset_vectors]

    fig = plt.figure(figsize=(13.8, 8.6), constrained_layout=False)
    grid = fig.add_gridspec(2, 2, height_ratios=[2.0, 1.0])
    ax_raw = fig.add_subplot(grid[0, 0])
    ax_final = fig.add_subplot(grid[0, 1])
    ax_hist = fig.add_subplot(grid[1, :])

    for ax in (ax_raw, ax_final):
        ax.set_aspect("equal", adjustable="box")

    bbox = bbox or _calc_bbox(raw_segments, deduped_segments, polygon_coords)
    if bbox is not None:
        _apply_bbox(ax_raw, bbox)
        _apply_bbox(ax_final, bbox)

    raw_lc = _add_segments(ax_raw, raw_segments, color="#94a3b8", alpha=0.3, lw=0.7)
    snapped_lc = _add_segments(ax_raw, snapped_segments, color="#60a5fa", alpha=0.5, lw=0.7)
    final_lc = _add_segments(ax_final, deduped_segments, color="#0f172a", alpha=0.9, lw=1.6)
    poly_line = _add_polygon(ax_final, polygon_coords, color="#ef4444", lw=2.4)

    raw_pts = _add_endpoints(ax_raw, raw_segments, color="#94a3b8")
    final_pts = _add_endpoints(ax_final, deduped_segments, color="#0f172a")
    offset_lc = _add_offset_vectors(ax_raw, offset_vectors, color="#f97316")

    ax_raw.set_title(
        _format_title(
            "Raw/Snapped",
            eps,
            debug,
            counts=("raw_segments_count", "snapped_segments_count"),
        )
    )
    ax_final.set_title(
        _format_title(
            "Final",
            eps,
            debug,
            counts=("deduped_segments_count", None),
            area=debug.get("chosen_area"),
        )
    )

    if distances:
        ax_hist.hist(distances, bins=50, color="#475569", alpha=0.75)
        p95 = _percentile(distances, 95)
        stats = f"max={max(distances):.6f} mean={mean(distances):.6f} p95={p95:.6f}"
    else:
        stats = "no offsets"
    poly_stats = _format_poly_stats(debug)
    ax_hist.set_title(
        f"Offset histogram (count={len(distances)} min={offset_min:.6f}) {stats}{poly_stats}"
    )
    ax_hist.set_xlabel("Offset distance (mm)")
    ax_hist.set_ylabel("Count")

    labels = [
        "Show Raw",
        "Show Snapped",
        "Show Final",
        "Show Polygon",
        "Show Endpoints",
        "Show Offset Vectors",
    ]
    visibility = [True, False, True, True, True, False]
    fig.subplots_adjust(right=0.83, wspace=0.18, hspace=0.28)
    controls_ax = fig.add_axes([0.85, 0.52, 0.13, 0.24])
    controls_ax.set_facecolor("white")
    controls_ax.patch.set_alpha(0.95)
    controls_ax.set_zorder(10)
    controls_ax.set_navigate(False)
    controls_ax.set_xlim(0, 1)
    controls_ax.set_ylim(0, 1)
    controls_ax.axis("off")

    box_patches = []
    check_marks = []
    label_texts = []
    row_h = 1.0 / (len(labels) + 0.5)
    for idx, label in enumerate(labels):
        y = 1.0 - (idx + 1) * row_h
        box = Rectangle((0.05, y + 0.02), 0.08, 0.08, edgecolor="black", facecolor="white", lw=1)
        controls_ax.add_patch(box)
        mark = controls_ax.text(0.065, y + 0.025, "x", fontsize=9, color="black", va="bottom", ha="left")
        mark.set_visible(visibility[idx])
        text = controls_ax.text(0.18, y + 0.02, label, fontsize=9, va="bottom", ha="left")
        box_patches.append(box)
        check_marks.append(mark)
        label_texts.append(text)

    artists = {
        "Show Raw": [raw_lc],
        "Show Snapped": [snapped_lc],
        "Show Final": [final_lc],
        "Show Polygon": [poly_line],
        "Show Endpoints": [raw_pts, final_pts],
        "Show Offset Vectors": [offset_lc],
    }

    def _toggle(label: str, idx: int) -> None:
        for artist in artists.get(label, []):
            if artist is not None:
                artist.set_visible(not artist.get_visible())
        check_marks[idx].set_visible(not check_marks[idx].get_visible())
        fig.canvas.draw_idle()

    def _on_click(event) -> None:
        if event.inaxes != controls_ax or event.ydata is None or event.xdata is None:
            return
        x, y = event.xdata, event.ydata
        if x < 0.05 or x > 0.95:
            return
        idx = int((1.0 - y) / row_h)
        if 0 <= idx < len(labels):
            _toggle(labels[idx], idx)

    fig.canvas.mpl_connect("button_press_event", _on_click)

    if fig.canvas.toolbar is not None:
        fig.canvas.toolbar.mode = ""
    fig.canvas.draw_idle()
    plt.show(block=False)


def _add_segments(ax, segments: Iterable[Segment2D], color: str, alpha: float, lw: float):
    if not segments:
        return None
    lines = [[p1, p2] for p1, p2 in segments]
    collection = LineCollection(lines, colors=color, linewidths=lw, alpha=alpha)
    ax.add_collection(collection)
    return collection


def _add_polygon(ax, coords: list[Point2D], color: str, lw: float):
    if not coords:
        return None
    closed = coords + [coords[0]]
    xs, ys = zip(*closed)
    line = ax.plot(xs, ys, color=color, linewidth=lw)[0]
    return line


def _add_endpoints(ax, segments: Iterable[Segment2D], color: str):
    points = []
    for p1, p2 in segments:
        points.append(p1)
        points.append(p2)
    points = _sample_items(points, 10000)
    if not points:
        return None
    xs, ys = zip(*points)
    return ax.scatter(xs, ys, s=6, c=color, alpha=0.8)


def _add_offset_vectors(ax, vectors, color: str):
    if not vectors:
        return None
    lines = [[raw, snapped] for raw, snapped, _ in vectors]
    collection = LineCollection(lines, colors=color, linewidths=0.8, alpha=0.8, linestyles="--")
    ax.add_collection(collection)
    return collection


def _sample_items(items, max_items: int):
    if max_items <= 0 or len(items) <= max_items:
        return list(items)
    stride = max(1, int(math.ceil(len(items) / max_items)))
    return list(items[::stride])[:max_items]


def _limit_offset_vectors(vectors, max_vectors: int):
    if max_vectors <= 0 or len(vectors) <= max_vectors:
        return list(vectors)
    return list(vectors[:max_vectors])


def _calc_bbox(raw_segments: list[Segment2D], deduped_segments: list[Segment2D], coords: list[Point2D]):
    points = []
    for seg in raw_segments + deduped_segments:
        points.extend(seg)
    points.extend(coords)
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _apply_bbox(ax, bbox):
    min_x, min_y, max_x, max_y = bbox
    width = max_x - min_x
    height = max_y - min_y
    pad = max(width, height) * 0.05
    ax.set_xlim(min_x - pad, max_x + pad)
    ax.set_ylim(min_y - pad, max_y + pad)


def _format_title(label: str, eps: float, debug: dict, counts: tuple, area: float | None = None) -> str:
    raw_key, other_key = counts
    parts = [label, f"eps={eps:.4g}", f"arc={float(debug.get('arc_max_chord_error_mm', 0.0)):.4g}"]
    if raw_key:
        parts.append(f"{raw_key.split('_')[0]}={debug.get(raw_key)}")
    if other_key:
        parts.append(f"{other_key.split('_')[0]}={debug.get(other_key)}")
    if area is not None:
        parts.append(f"area={area:.4g}")
    if debug.get("used_fallback") is not None:
        parts.append(f"fb={debug.get('used_fallback')}")
    return " | ".join(parts)


def _format_poly_stats(debug: dict) -> str:
    union_type = debug.get("polygonize_union_type")
    merged_type = debug.get("polygonize_merged_type")
    poly_count = debug.get("polygonize_count")
    if union_type is None and merged_type is None:
        return ""
    return f" | poly={poly_count} union={union_type} merge={merged_type}"


def _percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    k = (len(values) - 1) * (percent / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return values[int(k)]
    return values[int(f)] + (values[int(c)] - values[int(f)]) * (k - f)
