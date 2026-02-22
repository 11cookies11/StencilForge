from __future__ import annotations

from dataclasses import dataclass
import logging
import time
from typing import Protocol

import trimesh

from ..config import StencilConfig
from .cadquery import export_cadquery_stl
from .geometry import extrude_geometry
from .mesh import cleanup_mesh, translate_to_origin

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EngineExportInput:
    stencil_2d: object
    locator_geom: object
    locator_step_geom: object
    output_path: object
    config: StencilConfig


class ModelEngine(Protocol):
    name: str

    def export(self, data: EngineExportInput) -> None:
        ...


class CadQueryEngine:
    name = "cadquery"

    def export(self, data: EngineExportInput) -> None:
        export_cadquery_stl(
            data.stencil_2d,
            data.locator_geom,
            data.locator_step_geom,
            data.output_path,
            data.config,
        )


class TrimeshEngine:
    name = "trimesh"

    def export(self, data: EngineExportInput) -> None:
        cfg = data.config

        t0 = time.perf_counter()
        mesh = extrude_geometry(data.stencil_2d, cfg.thickness_mm)
        logger.info("Base mesh extrusion in %.3fs", time.perf_counter() - t0)

        if data.locator_geom is not None and not data.locator_geom.is_empty and cfg.locator_height_mm > 0:
            t0 = time.perf_counter()
            locator_mesh = extrude_geometry(data.locator_geom, cfg.locator_height_mm)
            logger.info("Locator mesh extrusion in %.3fs", time.perf_counter() - t0)
            locator_mesh.apply_translation((0, 0, cfg.thickness_mm))
            mesh = trimesh.util.concatenate([mesh, locator_mesh])

        if (
            data.locator_step_geom is not None
            and not data.locator_step_geom.is_empty
            and cfg.locator_step_height_mm > 0
        ):
            t0 = time.perf_counter()
            step_mesh = extrude_geometry(data.locator_step_geom, cfg.locator_step_height_mm)
            logger.info("Locator step extrusion in %.3fs", time.perf_counter() - t0)
            step_mesh.apply_translation((0, 0, -cfg.locator_step_height_mm))
            mesh = trimesh.util.concatenate([mesh, step_mesh])

        logger.info("Cleaning mesh...")
        try:
            t0 = time.perf_counter()
            cleanup_mesh(mesh)
            logger.info("Mesh cleanup in %.3fs", time.perf_counter() - t0)
        except Exception as exc:
            logger.warning("Mesh cleanup failed: %s", exc)

        logger.info("Translating mesh to origin...")
        try:
            t0 = time.perf_counter()
            translate_to_origin(mesh)
            logger.info("Mesh translation in %.3fs", time.perf_counter() - t0)
        except Exception as exc:
            logger.warning("Mesh translation failed: %s", exc)

        data.output_path.parent.mkdir(parents=True, exist_ok=True)
        if mesh.is_empty or mesh.faces.size == 0:
            raise ValueError("Generated mesh is empty; check outline/paste geometry.")

        watertight = getattr(mesh, "is_watertight", None)
        euler = getattr(mesh, "euler_number", None)
        logger.info("Mesh stats: faces=%s watertight=%s euler=%s", mesh.faces.shape[0], watertight, euler)

        t0 = time.perf_counter()
        mesh.export(data.output_path, file_type="stl_ascii")
        logger.info("STL export write in %.3fs", time.perf_counter() - t0)

        try:
            size = data.output_path.stat().st_size
        except OSError:
            size = 0
        logger.info("STL size: %s bytes", size)
        if size <= 0:
            raise ValueError("Exported STL file is empty.")

        try:
            t0 = time.perf_counter()
            check_mesh = trimesh.load_mesh(data.output_path, force="mesh")
            faces = getattr(check_mesh, "faces", None)
            face_count = int(faces.shape[0]) if faces is not None else 0
            logger.info("STL reload check in %.3fs", time.perf_counter() - t0)
            logger.info("STL check: faces=%s", face_count)
            if face_count == 0:
                raise ValueError("Exported STL has no faces; check geometry.")
        except Exception as exc:
            raise ValueError(f"Failed to validate exported STL: {exc}") from exc

        logger.info("STL export complete")


class SfMeshEngine:
    name = "sfmesh"

    def __init__(self) -> None:
        self._fallback = TrimeshEngine()

    def export(self, data: EngineExportInput) -> None:
        # Placeholder adapter: keep interface stable while sfmesh core is built.
        logger.info("sfmesh backend is in adapter mode; using trimesh implementation.")
        self._fallback.export(data)


_ENGINES: dict[str, ModelEngine] = {
    "cadquery": CadQueryEngine(),
    "trimesh": TrimeshEngine(),
    "sfmesh": SfMeshEngine(),
}


def get_model_engine(name: str) -> ModelEngine:
    key = (name or "").strip().lower()
    engine = _ENGINES.get(key)
    if engine is None:
        supported = ", ".join(sorted(_ENGINES.keys()))
        raise ValueError(f"Unsupported model backend '{name}'. Supported: {supported}")
    return engine
