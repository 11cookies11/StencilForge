from __future__ import annotations

from pathlib import Path
from fnmatch import fnmatch

from shapely.geometry import box
from shapely.ops import unary_union
import trimesh

from .config import StencilConfig
from .gerber_adapter import load_outline_geometry, load_paste_geometry


def generate_stencil(input_dir: Path, output_path: Path, config: StencilConfig) -> None:
    config.validate()
    paste_files = _find_files(input_dir, config.paste_patterns)
    if not paste_files:
        raise FileNotFoundError("No paste layer files found in input directory.")
    paste_geom = load_paste_geometry(paste_files, config)
    if paste_geom is None or paste_geom.is_empty:
        raise ValueError("Paste layer produced empty geometry.")

    paste_geom = paste_geom.buffer(
        config.paste_offset_mm, resolution=config.curve_resolution
    )
    if paste_geom.is_empty:
        raise ValueError("Paste offset produced empty geometry.")

    outline_geom = None
    outline_files = _find_files(input_dir, config.outline_patterns)
    if outline_files:
        outline_geom = load_outline_geometry(outline_files[0], config)

    if outline_geom is None or outline_geom.is_empty:
        outline_geom = _outline_from_paste(paste_geom, config.outline_margin_mm)

    if config.output_mode == "holes_only":
        mesh = _extrude_geometry(paste_geom, config.thickness_mm)
    else:
        stencil_2d = outline_geom.difference(paste_geom)
        mesh = _extrude_geometry(stencil_2d, config.thickness_mm)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(output_path)


def _find_files(input_dir: Path, patterns: list[str]) -> list[Path]:
    if not patterns:
        return []
    files = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        name = path.name.lower()
        for pattern in patterns:
            if _match(pattern.lower(), name):
                files.append(path)
                break
    return sorted(set(files))


def _match(pattern: str, name: str) -> bool:
    return fnmatch(name, pattern)


def _outline_from_paste(paste_geom, margin_mm: float):
    min_x, min_y, max_x, max_y = paste_geom.bounds
    return box(min_x - margin_mm, min_y - margin_mm, max_x + margin_mm, max_y + margin_mm)


def _extrude_geometry(geometry, thickness_mm: float):
    geometry = geometry.buffer(0)
    meshes = []
    if geometry.geom_type == "Polygon":
        meshes.append(trimesh.creation.extrude_polygon(geometry, thickness_mm))
    elif geometry.geom_type == "MultiPolygon":
        for poly in geometry.geoms:
            meshes.append(trimesh.creation.extrude_polygon(poly, thickness_mm))
    else:
        merged = unary_union([geometry])
        if merged.geom_type == "Polygon":
            meshes.append(trimesh.creation.extrude_polygon(merged, thickness_mm))
        elif merged.geom_type == "MultiPolygon":
            for poly in merged.geoms:
                meshes.append(trimesh.creation.extrude_polygon(poly, thickness_mm))
    if not meshes:
        raise ValueError("Failed to create STL mesh from geometry.")
    return trimesh.util.concatenate(meshes)
