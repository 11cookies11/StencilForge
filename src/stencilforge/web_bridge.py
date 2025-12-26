from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal, Slot
from shapely.geometry import box
import trimesh


class WebBridge(QObject):
    """QWebChannel bridge for Web UI -> Python backend."""

    stlGenerated = Signal(str)
    previewRequested = Signal()
    pickStlRequested = Signal()
    log = Signal(str)
    error = Signal(str)

    def __init__(self, output_dir: Path) -> None:
        super().__init__()
        self._output_dir = output_dir

    @Slot(str)
    def generate_stl(self, config_json: str) -> None:
        config = self._parse_config(config_json)
        width = float(config.get("width_mm", 60.0))
        height = float(config.get("height_mm", 40.0))
        thickness = float(config.get("thickness_mm", 1.2))

        self._output_dir.mkdir(parents=True, exist_ok=True)
        output_path = self._output_dir / "demo.stl"

        try:
            polygon = box(-width / 2, -height / 2, width / 2, height / 2)
            mesh = trimesh.creation.extrude_polygon(polygon, thickness, engine="earcut")
            if mesh.is_empty or mesh.faces.size == 0:
                raise ValueError("Extrusion returned empty mesh.")
        except Exception as exc:  # pragma: no cover - runtime errors
            self.log.emit(f"Extrusion failed, falling back to box mesh: {exc}")
            mesh = trimesh.creation.box(extents=(width, height, thickness))

        try:
            data = mesh.export(file_type="stl")
            if isinstance(data, str):
                output_path.write_text(data, encoding="ascii")
            else:
                output_path.write_bytes(data)
        except Exception as exc:  # pragma: no cover - runtime errors
            self.error.emit(f"Failed to export STL: {exc}")
            return

        faces_count = int(mesh.faces.shape[0]) if hasattr(mesh, "faces") else 0
        size_bytes = output_path.stat().st_size if output_path.exists() else 0
        self.log.emit(
            f"STL saved: {output_path} ({size_bytes} bytes, faces={faces_count})"
        )
        self.stlGenerated.emit(str(output_path))

    @Slot()
    def open_preview(self) -> None:
        self.previewRequested.emit()

    @Slot()
    def pick_stl(self) -> None:
        self.pickStlRequested.emit()

    def _parse_config(self, raw: str) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self.error.emit("Config JSON is invalid.")
            return {}
