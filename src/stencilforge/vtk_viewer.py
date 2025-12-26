from __future__ import annotations

from pathlib import Path

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
try:
    import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
except Exception:
    pass


class VtkStlViewer(QWidget):
    """Qt widget that renders STL files using VTK (no WebGL)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._renderer = vtkRenderer()
        self._renderer.SetBackground(0.93, 0.88, 0.80)
        self._renderer.SetBackground2(0.86, 0.76, 0.64)
        self._renderer.GradientBackgroundOn()
        self._viewer = QVTKRenderWindowInteractor(self)
        self._viewer.GetRenderWindow().AddRenderer(self._renderer)
        self._actor: vtkActor | None = None
        self._edge_actor: vtkActor | None = None
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

        reader = vtkSTLReader()
        reader.SetFileName(str(stl_path))
        reader.Update()
        output = reader.GetOutput()
        if output is None or output.GetNumberOfCells() == 0:
            print(f"[VTK] STL has no cells: {stl_path}")
            return

        mapper = vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())
        mapper.ScalarVisibilityOff()

        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.62, 0.68, 0.78)
        actor.GetProperty().SetAmbient(0.35)
        actor.GetProperty().SetDiffuse(0.65)
        actor.GetProperty().SetSpecular(0.05)
        actor.GetProperty().SetSpecularPower(8.0)
        actor.GetProperty().SetInterpolationToFlat()

        if self._actor is not None:
            self._renderer.RemoveActor(self._actor)
        if self._edge_actor is not None:
            self._renderer.RemoveActor(self._edge_actor)
        self._actor = actor
        self._renderer.AddActor(self._actor)
        self._edge_actor = self._build_edge_actor(reader)
        if self._edge_actor is not None:
            self._renderer.AddActor(self._edge_actor)
        bounds = output.GetBounds()
        print(f"[VTK] Loaded STL: {stl_path} bounds={bounds} cells={output.GetNumberOfCells()}")
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

    def _build_edge_actor(self, reader: vtkSTLReader) -> vtkActor | None:
        normals = vtkPolyDataNormals()
        normals.SetInputConnection(reader.GetOutputPort())
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
