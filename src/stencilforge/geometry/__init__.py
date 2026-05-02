"""几何子模块导出集合。"""

from .primitives import PrimitiveGeometryBuilder
from .outline import OutlineBuilder
from .service import GerberGeometryService, flatten_to_polygons

__all__ = ["GerberGeometryService", "OutlineBuilder", "PrimitiveGeometryBuilder", "flatten_to_polygons"]
