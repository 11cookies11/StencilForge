from __future__ import annotations

from pathlib import Path
import shutil
import tempfile

import numpy as np
import trimesh

from PySide6.QtWidgets import QVBoxLayout, QWidget
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper, vtkRenderer
from vtkmodules.vtkRenderingCore import vtkLight
from vtkmodules.vtkIOGeometry import vtkSTLReader
from vtkmodules.vtkRenderingAnnotation import vtkAxesActor
from vtkmodules.vtkRenderingCore import vtkLightKit
from vtkmodules.vtkFiltersCore import vtkFeatureEdges
from vtkmodules.vtkFiltersCore import vtkPolyDataNormals
from vtkmodules.vtkFiltersModeling import vtkOutlineFilter
from vtkmodules.vtkCommonCore import vtkPoints
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
try:
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
except Exception:
    pass


class VtkStlViewer(QWidget):
    """Qt widget that renders STL files using VTK (no WebGL)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = vtkRenderer()
        self._renderer.SetBackground(0.92, 0.94, 0.96)
        self._renderer.SetBackground2(0.80, 0.86, 0.92)
        self._renderer.GradientBackgroundOn()
        self._viewer = QVTKRenderWindowInteractor(self)
        self._viewer.GetRenderWindow().AddRenderer(self._renderer)
        self._actor: vtkActor | None = None
        self._edge_actor: vtkActor | None = None
        self._outline_actor: vtkActor | None = None
        self._axes = vtkAxesActor()
        self._axes.SetTotalLength(20.0, 20.0, 20.0)
        self._orientation_widget: vtkOrientationMarkerWidget | None = None
        self._light_kit = vtkLightKit()
        self._default_camera = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._viewer)
        light = vtkLight()
        light.SetLightTypeToSceneLight()
        light.SetPosition(1.0, 1.0, 1.0)
        self._renderer.AddLight(light)
        self._light_kit.SetKeyLightIntensity(0.9)
        if hasattr(self._light_kit, "SetFillLightIntensity"):
            self._light_kit.SetFillLightIntensity(0.6)
        if hasattr(self._light_kit, "SetBackLightIntensity"):
            self._light_kit.SetBackLightIntensity(0.5)
        self._light_kit.AddLightsToRenderer(self._renderer)
        interactor = self._viewer.GetRenderWindow().GetInteractor()
        if interactor is not None:
            interactor.SetInteractorStyle(vtkInteractorStyleTrackballCamera())
            interactor.Initialize()
            try:
                from vtkmodules.vtkInteractionWidgets import vtkOrientationMarkerWidget
            except Exception:
                vtkOrientationMarkerWidget = None
            if vtkOrientationMarkerWidget is not None:
                self._orientation_widget = vtkOrientationMarkerWidget()
                self._orientation_widget.SetOrientationMarker(self._axes)
                self._orientation_widget.SetInteractor(interactor)
                self._orientation_widget.SetViewport(0.0, 0.0, 0.18, 0.18)
                self._orientation_widget.SetEnabled(1)
                self._orientation_widget.InteractiveOff()
        self._viewer.GetRenderWindow().Render()

    def load_stl(self, path: str) -> None:
        stl_path = Path(path)
        if not stl_path.exists():
            return
        load_path = stl_path
        if not stl_path.name.isascii() or any(not c.isascii() for c in str(stl_path)):
            temp_dir = Path(tempfile.mkdtemp(prefix="stencilforge_stl_"))
            load_path = temp_dir / stl_path.name
            shutil.copy2(stl_path, load_path)

        reader = vtkSTLReader()
        reader.SetFileName(str(load_path))
        reader.Update()
        output = reader.GetOutput()
        polydata = output
        if output is None or output.GetNumberOfCells() == 0:
            print(f"[VTK] STL has no cells: {load_path}, trying trimesh fallback")
            polydata = self._load_with_trimesh(load_path)
            if polydata is None or polydata.GetNumberOfCells() == 0:
                print(f"[VTK] STL fallback failed: {load_path}")
                return

        mapper = vtkPolyDataMapper()
        if polydata is output:
            mapper.SetInputConnection(reader.GetOutputPort())
        else:
            mapper.SetInputData(polydata)
        mapper.ScalarVisibilityOff()

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.20, 0.32, 0.60)
        actor.GetProperty().SetAmbient(0.35)
        actor.GetProperty().SetDiffuse(0.65)
        actor.GetProperty().SetSpecular(0.05)
        actor.GetProperty().SetSpecularPower(8.0)
        actor.GetProperty().SetInterpolationToFlat()
        actor.GetProperty().EdgeVisibilityOff()

        if self._actor is not None:
            self._renderer.RemoveActor(self._actor)
        if self._edge_actor is not None:
            self._renderer.RemoveActor(self._edge_actor)
        if self._outline_actor is not None:
            self._renderer.RemoveActor(self._outline_actor)
        self._actor = actor
        self._renderer.AddActor(self._actor)
        self._edge_actor = self._build_edge_actor(output if polydata is output else polydata)
        if self._edge_actor is not None:
            self._renderer.AddActor(self._edge_actor)
        bounds = polydata.GetBounds()
        thickness = bounds[5] - bounds[4]
        if thickness < 0.2:
            self._outline_actor = self._build_outline_actor(polydata)
            if self._outline_actor is not None:
                self._renderer.AddActor(self._outline_actor)
        if thickness > 0:
            target_thickness = 0.5
            scale_z = max(1.0, target_thickness / thickness)
            if scale_z > 1.0:
                actor.SetScale(1.0, 1.0, scale_z)
                if self._edge_actor is not None:
                    self._edge_actor.SetScale(1.0, 1.0, scale_z)
                if self._outline_actor is not None:
                    self._outline_actor.SetScale(1.0, 1.0, scale_z)
                print(f"[VTK] Applied preview Z scale: {scale_z:.2f}")
        print(f"[VTK] Loaded STL: {load_path} bounds={bounds} cells={polydata.GetNumberOfCells()}")
        self.fit_view(bounds)
        self._default_camera = self._renderer.GetActiveCamera()

    def fit_view(self, bounds: tuple[float, float, float, float, float, float] | None = None) -> None:
        if bounds is None and self._actor is None:
            return
        if bounds is None and self._actor is not None:
            bounds = self._actor.GetBounds()
        if bounds is None:
            return
        center = (
            (bounds[0] + bounds[1]) / 2.0,
            (bounds[2] + bounds[3]) / 2.0,
            (bounds[4] + bounds[5]) / 2.0,
        )
        max_dim = max(
            bounds[1] - bounds[0],
            bounds[3] - bounds[2],
            bounds[5] - bounds[4],
            1.0,
        )
        camera = self._renderer.GetActiveCamera()
        camera.SetFocalPoint(*center)
        camera.SetPosition(center[0], center[1] - max_dim * 2.2, center[2] + max_dim * 1.2)
        camera.SetViewUp(0.0, 0.0, 1.0)
        self._renderer.ResetCameraClippingRange()
        self._viewer.GetRenderWindow().Render()

    def reset_view(self) -> None:
        if self._default_camera is None:
            self.fit_view()
            return
        camera = self._renderer.GetActiveCamera()
        camera.DeepCopy(self._default_camera)
        self._renderer.ResetCameraClippingRange()
        self._viewer.GetRenderWindow().Render()

    def set_wireframe(self, enabled: bool) -> None:
        if self._actor is None:
            return
        prop = self._actor.GetProperty()
        if enabled:
            prop.SetRepresentationToWireframe()
            prop.SetLineWidth(1.0)
        else:
            prop.SetRepresentationToSurface()
        self._viewer.GetRenderWindow().Render()

    def toggle_axes(self, enabled: bool) -> None:
        if self._orientation_widget is None:
            return
        self._orientation_widget.SetEnabled(1 if enabled else 0)
        self._viewer.GetRenderWindow().Render()

    def _build_edge_actor(self, source) -> vtkActor | None:
        normals = vtkPolyDataNormals()
        if isinstance(source, vtkPolyData):
            normals.SetInputData(source)
        else:
            normals.SetInputConnection(source.GetOutputPort())
        normals.SetSplitting(1)
        normals.SetConsistency(1)
        normals.AutoOrientNormalsOn()
        normals.Update()

        edges = vtkFeatureEdges()
        edges.SetInputConnection(normals.GetOutputPort())
        edges.BoundaryEdgesOn()
        edges.FeatureEdgesOn()
        edges.ManifoldEdgesOff()
        edges.NonManifoldEdgesOff()
        edges.SetFeatureAngle(35.0)

        edge_mapper = vtkPolyDataMapper()
        edge_mapper.SetInputConnection(edges.GetOutputPort())

        edge_actor = vtkActor()
        edge_actor.SetMapper(edge_mapper)
        edge_actor.GetProperty().SetColor(0.02, 0.02, 0.02)
        edge_actor.GetProperty().SetLineWidth(1.6)
        return edge_actor

    def _build_outline_actor(self, polydata: vtkPolyData) -> vtkActor | None:
        outline = vtkOutlineFilter()
        outline.SetInputData(polydata)
        outline.Update()

        outline_mapper = vtkPolyDataMapper()
        outline_mapper.SetInputConnection(outline.GetOutputPort())

        outline_actor = vtkActor()
        outline_actor.SetMapper(outline_mapper)
        outline_actor.GetProperty().SetColor(0.92, 0.23, 0.18)
        outline_actor.GetProperty().SetLineWidth(2.5)
        return outline_actor

    def _load_with_trimesh(self, path: Path) -> vtkPolyData | None:
        try:
            mesh = trimesh.load_mesh(path, force="mesh")
        except Exception as exc:
            print(f"[VTK] Trimesh load failed: {exc}")
            return None
        if mesh.is_empty:
            return None
        vertices = np.asarray(mesh.vertices, dtype=float)
        faces = np.asarray(mesh.faces, dtype=np.int64)
        if faces.size == 0 or vertices.size == 0:
            return None
        points = vtkPoints()
        points.SetNumberOfPoints(len(vertices))
        for idx, (x, y, z) in enumerate(vertices):
            points.SetPoint(idx, float(x), float(y), float(z))
        cells = vtkCellArray()
        for a, b, c in faces:
            cells.InsertNextCell(3)
            cells.InsertCellPoint(int(a))
            cells.InsertCellPoint(int(b))
            cells.InsertCellPoint(int(c))
        polydata = vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetPolys(cells)
        return polydata
