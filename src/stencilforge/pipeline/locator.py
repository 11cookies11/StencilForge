from __future__ import annotations

"""定位结构构建：用于在钢网上生成桥、台阶或环形定位结构。"""

from shapely.geometry import box


def _exclude_keepout(geom, keepout):
    if geom is None or geom.is_empty:
        return None
    if keepout is None or keepout.is_empty:
        return geom
    trimmed = geom.difference(keepout)
    if trimmed.is_empty:
        return None
    return trimmed



def build_locator_ring(outline_geom, clearance_mm: float, width_mm: float, open_side: str, open_width_mm: float):
    # 基于外轮廓生成环形定位墙：外扩 - 内扩得到环
    if width_mm <= 0:
        return None
    inner = outline_geom.buffer(clearance_mm)
    outer = outline_geom.buffer(clearance_mm + width_mm)
    ring = outer.difference(inner)
    ring = apply_open_side(ring, outer, open_side, open_width_mm)
    return _exclude_keepout(ring, outline_geom)


def build_locator_step(outline_geom, clearance_mm: float, step_width_mm: float, open_side: str, open_width_mm: float):
    # 台阶与环形类似，但用于做“台阶”几何，后续会向负 Z 方向挤出
    if step_width_mm <= 0:
        return None
    inner = outline_geom.buffer(clearance_mm)
    outer = outline_geom.buffer(clearance_mm + step_width_mm)
    step = outer.difference(inner)
    step = apply_open_side(step, outer, open_side, open_width_mm)
    return _exclude_keepout(step, outline_geom)


def build_locator_bridge(outline_geom, clearance_mm: float, open_side: str, open_width_mm: float):
    # 桥结构：用外扩轮廓减去原轮廓，形成外侧桥环
    if clearance_mm <= 0:
        return None
    outer = outline_geom.buffer(clearance_mm)
    ring = outer.difference(outline_geom)
    ring = apply_open_side(ring, outer, open_side, open_width_mm)
    return _exclude_keepout(ring, outline_geom)


def apply_open_side(ring, outer, open_side: str, open_width_mm: float):
    # 在指定边开口：通过减去一个裁剪矩形形成缺口
    if open_side == "none" or open_width_mm <= 0:
        return ring
    min_x, min_y, max_x, max_y = outer.bounds
    if open_side == "top":
        cutter = box(min_x - open_width_mm, max_y - open_width_mm, max_x + open_width_mm, max_y + open_width_mm)
    elif open_side == "bottom":
        cutter = box(min_x - open_width_mm, min_y - open_width_mm, max_x + open_width_mm, min_y + open_width_mm)
    elif open_side == "left":
        cutter = box(min_x - open_width_mm, min_y - open_width_mm, min_x + open_width_mm, max_y + open_width_mm)
    elif open_side == "right":
        cutter = box(max_x - open_width_mm, min_y - open_width_mm, max_x + open_width_mm, max_y + open_width_mm)
    else:
        return ring
    return ring.difference(cutter)
