from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
import logging

from shapely.geometry import box
from shapely.ops import unary_union
import trimesh

from ..config import StencilConfig
from ..geometry import GerberGeometryService
from .cadquery import export_cadquery_stl
from .geometry import count_holes, extrude_geometry
from .locator import build_locator_bridge, build_locator_ring, build_locator_step
from .mesh import cleanup_mesh, translate_to_origin
from .qfn import regenerate_qfn_paste

logger = logging.getLogger(__name__)


def generate_stencil(input_dir: Path, output_path: Path, config: StencilConfig) -> dict | None:
    # 主流程：从输入 Gerber 解析 -> 2D 几何 -> 3D 网格 -> 导出 STL
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    # 配置校验与几何服务初始化（封装 Gerber 解析与单位转换）
    config.validate()
    geometry_service = GerberGeometryService(config)
    logger.info("Generating stencil from %s", input_dir)
    logger.info("Output STL: %s", output_path)
    # 1) 读取锡膏层（Paste），这是钢网孔洞的直接来源
    paste_files = _find_files(input_dir, config.paste_patterns)
    if not paste_files:
        raise FileNotFoundError("No paste layer files found in input directory.")
    logger.info("Paste layers: %s", ", ".join([p.name for p in paste_files]))
    paste_geom = geometry_service.load_paste_geometry(paste_files)
    if paste_geom is None or paste_geom.is_empty:
        raise ValueError("Paste layer produced empty geometry.")
    # 可选：对 QFN 器件的开窗进行再生成，提升可焊性
    if config.qfn_regen_enabled:
        try:
            paste_geom = regenerate_qfn_paste(paste_geom, config)
        except Exception as exc:
            logger.warning("QFN regeneration skipped: %s", exc)

    # 2) 对锡膏几何做偏移（一般为收缩/扩张）
    paste_geom = paste_geom.buffer(
        config.paste_offset_mm, resolution=config.curve_resolution
    )
    if paste_geom.is_empty:
        raise ValueError("Paste offset produced empty geometry.")
    logger.info("Paste offset: %s mm", config.paste_offset_mm)

    # 3) 读取板框（Outline），用于确定钢网外轮廓
    outline_geom = None
    outline_debug: dict | None = None
    outline_files = _find_files(input_dir, config.outline_patterns)
    if outline_files:
        outline_geom = geometry_service.load_outline_geometry(outline_files[0])
        outline_debug = geometry_service.get_last_outline_debug()
        logger.info("Outline layer: %s", outline_files[0].name)

    # 3.1) 若没有板框，则用锡膏外包矩形兜底
    if outline_geom is None or outline_geom.is_empty:
        outline_geom = _outline_from_paste(paste_geom, config.outline_margin_mm)
        logger.info("Outline fallback margin: %s mm", config.outline_margin_mm)

    # 4) 生成 2D 钢网：默认用板框减去锡膏（形成孔洞）
    logger.info("Output mode: %s", config.output_mode)
    if config.output_mode == "holes_only":
        stencil_2d = paste_geom
    else:
        stencil_2d = outline_geom.difference(paste_geom)
        hole_count = count_holes(stencil_2d)
        logger.info(
            "Stencil 2D: type=%s area=%.6f bounds=%s holes=%s",
            stencil_2d.geom_type,
            stencil_2d.area,
            stencil_2d.bounds if not stencil_2d.is_empty else None,
            hole_count,
        )
    # 5) 可选定位结构（桥/环/台阶）
    locator_bridge_geom = None
    if (
        config.locator_enabled
        and config.locator_mode == "step"
        and outline_geom is not None
        and not outline_geom.is_empty
        and config.locator_clearance_mm > 0
    ):
        locator_bridge_geom = build_locator_bridge(
            outline_geom,
            config.locator_clearance_mm,
            config.locator_open_side,
            config.locator_open_width_mm,
        )
        if locator_bridge_geom is not None and not locator_bridge_geom.is_empty:
            # 桥与主体 2D 合并
            stencil_2d = unary_union([stencil_2d, locator_bridge_geom])
            logger.info(
                "Locator bridge: clearance=%s open=%s(%s)",
                config.locator_clearance_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )

    logger.info("Base thickness: %s mm", config.thickness_mm)

    locator_geom = None
    locator_step_geom = None
    if config.locator_enabled and outline_geom is not None and not outline_geom.is_empty:
        # step 模式优先生成台阶，否则退回环形定位
        if config.locator_mode == "step":
            locator_step_geom = build_locator_step(
                outline_geom,
                config.locator_clearance_mm,
                config.locator_step_width_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )
            if (
                locator_step_geom is not None
                and not locator_step_geom.is_empty
                and config.locator_step_height_mm > 0
            ):
                logger.info(
                    "Locator step: height=%s width=%s clearance=%s open=%s(%s)",
                    config.locator_step_height_mm,
                    config.locator_step_width_mm,
                    config.locator_clearance_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )
            else:
                locator_step_geom = None
                locator_geom = build_locator_ring(
                    outline_geom,
                    config.locator_clearance_mm,
                    config.locator_width_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )
                if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
                    logger.info(
                        "Locator wall: height=%s width=%s clearance=%s open=%s(%s)",
                        config.locator_height_mm,
                        config.locator_width_mm,
                        config.locator_clearance_mm,
                        config.locator_open_side,
                        config.locator_open_width_mm,
                    )
        else:
            locator_geom = build_locator_ring(
                outline_geom,
                config.locator_clearance_mm,
                config.locator_width_mm,
                config.locator_open_side,
                config.locator_open_width_mm,
            )
            if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
                logger.info(
                    "Locator wall: height=%s width=%s clearance=%s open=%s(%s)",
                    config.locator_height_mm,
                    config.locator_width_mm,
                    config.locator_clearance_mm,
                    config.locator_open_side,
                    config.locator_open_width_mm,
                )

    # 6) 导出模式：CadQuery 或 Trimesh
    if config.model_backend == "cadquery":
        export_cadquery_stl(stencil_2d, locator_geom, locator_step_geom, output_path, config)
        return outline_debug

    # 7) 2D -> 3D 网格挤出，并叠加定位结构
    mesh = extrude_geometry(stencil_2d, config.thickness_mm)
    if locator_geom is not None and not locator_geom.is_empty and config.locator_height_mm > 0:
        locator_mesh = extrude_geometry(locator_geom, config.locator_height_mm)
        locator_mesh.apply_translation((0, 0, config.thickness_mm))
        mesh = trimesh.util.concatenate([mesh, locator_mesh])
    if locator_step_geom is not None and not locator_step_geom.is_empty and config.locator_step_height_mm > 0:
        step_mesh = extrude_geometry(locator_step_geom, config.locator_step_height_mm)
        step_mesh.apply_translation((0, 0, -config.locator_step_height_mm))
        mesh = trimesh.util.concatenate([mesh, step_mesh])

    # 8) 清理与归零，避免网格问题影响切片
    logger.info("Cleaning mesh...")
    try:
        cleanup_mesh(mesh)
    except Exception as exc:
        logger.warning("Mesh cleanup failed: %s", exc)
    logger.info("Translating mesh to origin...")
    try:
        translate_to_origin(mesh)
    except Exception as exc:
        logger.warning("Mesh translation failed: %s", exc)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if mesh.is_empty or mesh.faces.size == 0:
        raise ValueError("Generated mesh is empty; check outline/paste geometry.")
    watertight = getattr(mesh, "is_watertight", None)
    euler = getattr(mesh, "euler_number", None)
    logger.info("Mesh stats: faces=%s watertight=%s euler=%s", mesh.faces.shape[0], watertight, euler)
    mesh.export(output_path, file_type="stl_ascii")
    try:
        size = output_path.stat().st_size
    except OSError:
        size = 0
    logger.info("STL size: %s bytes", size)
    if size <= 0:
        raise ValueError("Exported STL file is empty.")
    # 二次读取校验，避免输出空网格
    try:
        check_mesh = trimesh.load_mesh(output_path, force="mesh")
        faces = getattr(check_mesh, "faces", None)
        face_count = int(faces.shape[0]) if faces is not None else 0
        logger.info("STL check: faces=%s", face_count)
        if face_count == 0:
            raise ValueError("Exported STL has no faces; check geometry.")
    except Exception as exc:
        raise ValueError(f"Failed to validate exported STL: {exc}") from exc
    logger.info("STL export complete")
    return outline_debug


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
