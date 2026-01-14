from __future__ import annotations

"""网格后处理：清理与归零。"""

import logging

import trimesh

logger = logging.getLogger(__name__)


def cleanup_mesh(mesh: trimesh.Trimesh) -> None:
    # 逐步移除退化/重复面并合并顶点，提升可切片性
    before_faces = int(mesh.faces.shape[0]) if mesh.faces is not None else 0
    if hasattr(mesh, "remove_degenerate_faces"):
        mesh.remove_degenerate_faces()
    if hasattr(mesh, "remove_duplicate_faces"):
        mesh.remove_duplicate_faces()
    if hasattr(mesh, "remove_infinite_values"):
        mesh.remove_infinite_values()
    if hasattr(mesh, "merge_vertices"):
        mesh.merge_vertices()
    if hasattr(mesh, "remove_unreferenced_vertices"):
        mesh.remove_unreferenced_vertices()
    if hasattr(mesh, "fix_normals"):
        try:
            mesh.fix_normals()
        except Exception:
            pass
    after_faces = int(mesh.faces.shape[0]) if mesh.faces is not None else 0
    logger.info("Mesh cleanup: faces %s -> %s", before_faces, after_faces)


def translate_to_origin(mesh: trimesh.Trimesh) -> None:
    # 将网格整体平移到原点，便于对齐与显示
    bounds = mesh.bounds
    if bounds is None:
        return
    min_x, min_y, min_z = bounds[0]
    offset = (-min_x, -min_y, -min_z)
    mesh.apply_translation(offset)
    logger.info("Mesh translated to origin: offset=%s", offset)
