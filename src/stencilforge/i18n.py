from __future__ import annotations

from typing import Any


_MESSAGES = {
    "zh-CN": {
        "preview.title": "钢网预览",
        "preview.fit": "适配",
        "preview.reset": "重置",
        "preview.wireframe": "线框",
        "preview.axes": "坐标轴",
        "preview.no_preview_path": "预览 STL 路径为空。",
        "preview.preview_unavailable": "预览窗口未初始化。",
        "dialog.error_title": "运行失败",
        "dialog.error_body": "发生错误，任务已停止。",
        "dialog.error_detail": "错误原因: {message}",
        "dialog.error_log": "日志已保存到: {path}",
        "dialog.error_open_log": "查看日志",
        "ui.debug_plot_load_failed": "无法加载调试绘图: {error}",
        "ui.debug_plot_failed": "调试绘图失败: {error}",
        "ui.config_not_found": "未找到配置文件: {path}",
        "ui.pick_save_stl_title": "保存 STL",
        "ui.pick_directory_title": "选择 Gerber 文件夹",
        "ui.pick_config_title": "选择配置文件",
        "ui.pick_zip_title": "选择 Gerber ZIP",
        "ui.pick_stl_title": "选择 STL",
        "ui.file_not_found": "文件不存在: {path}",
        "ui.read_file_failed": "读取文件失败: {error}",
        "ui.preview_path_empty": "预览 STL 路径为空。",
        "ui.preview_viewer_uninitialized": "预览视图未初始化。",
        "ui.stl_not_found": "未找到 STL: {path}",
        "ui.preview_launch_failed": "启动预览失败: {error}",
        "ui.zip_not_found": "未找到 ZIP: {path}",
        "ui.zip_invalid": "无效的 ZIP 文件。",
        "ui.job_already_running": "任务已在运行。",
        "ui.zip_extract_failed": "无法解压 ZIP 输入。",
        "ui.job_canceled": "任务已取消。",
        "ui.zip_extracted": "已解压 ZIP: {name}",
        "ui.no_running_job": "当前没有运行中的任务。",
        "ui.stop_requested_terminating": "已请求停止，正在终止导出进程。",
        "ui.terminate_failed": "终止进程失败: {detail}",
        "ui.terminate_pid_missing": "终止进程失败: 无法获取进程 ID。",
        "ui.stop_requested_waiting": "已请求停止，正在等待任务响应。",
        "ui.ui_dist_missing": "未找到 UI 构建产物，请确认安装包包含前端资源。\n已尝试路径:\n{paths}",
        "cli.preview_usage": "Usage: python -m stencilforge.preview_app <stl_path>",
        "cli.stl_not_found": "STL not found: {path}",
    },
    "en": {
        "preview.title": "Stencil preview",
        "preview.fit": "Fit",
        "preview.reset": "Reset",
        "preview.wireframe": "Wireframe",
        "preview.axes": "Axes",
        "preview.no_preview_path": "Preview STL path is empty.",
        "preview.preview_unavailable": "Preview window is not initialized.",
        "dialog.error_title": "Job Failed",
        "dialog.error_body": "An error occurred and the job was stopped.",
        "dialog.error_detail": "Error: {message}",
        "dialog.error_log": "Log saved to: {path}",
        "dialog.error_open_log": "Open Log",
        "ui.debug_plot_load_failed": "Failed to load debug plot module: {error}",
        "ui.debug_plot_failed": "Debug plot failed: {error}",
        "ui.config_not_found": "Config file not found: {path}",
        "ui.pick_save_stl_title": "Save STL",
        "ui.pick_directory_title": "Select Gerber folder",
        "ui.pick_config_title": "Select config file",
        "ui.pick_zip_title": "Select Gerber ZIP",
        "ui.pick_stl_title": "Select STL",
        "ui.file_not_found": "File not found: {path}",
        "ui.read_file_failed": "Failed to read file: {error}",
        "ui.preview_path_empty": "Preview STL path is empty.",
        "ui.preview_viewer_uninitialized": "Preview viewer is not initialized.",
        "ui.stl_not_found": "STL not found: {path}",
        "ui.preview_launch_failed": "Failed to launch preview: {error}",
        "ui.zip_not_found": "ZIP file not found: {path}",
        "ui.zip_invalid": "Invalid ZIP file.",
        "ui.job_already_running": "A job is already running.",
        "ui.zip_extract_failed": "Failed to extract ZIP input.",
        "ui.job_canceled": "Job canceled.",
        "ui.zip_extracted": "ZIP extracted: {name}",
        "ui.no_running_job": "No running job.",
        "ui.stop_requested_terminating": "Stop requested. Terminating export process.",
        "ui.terminate_failed": "Failed to terminate process: {detail}",
        "ui.terminate_pid_missing": "Failed to terminate process: missing process ID.",
        "ui.stop_requested_waiting": "Stop requested. Waiting for job to exit.",
        "ui.ui_dist_missing": "UI build artifacts not found. Ensure frontend assets are packaged.\nChecked paths:\n{paths}",
        "cli.preview_usage": "Usage: python -m stencilforge.preview_app <stl_path>",
        "cli.stl_not_found": "STL not found: {path}",
    },
}


def normalize_locale(locale: str | None) -> str:
    if not locale:
        return "zh-CN"
    lowered = locale.lower()
    if lowered.startswith("en"):
        return "en"
    return "zh-CN"


def text(locale: str | None, key: str, **kwargs: Any) -> str:
    normalized = normalize_locale(locale)
    table = _MESSAGES.get(normalized, _MESSAGES["zh-CN"])
    fallback = _MESSAGES["zh-CN"]
    message = table.get(key) or fallback.get(key) or key
    if kwargs:
        return message.format(**kwargs)
    return message


def preview_labels(locale: str | None) -> dict[str, str]:
    return {
        "title": text(locale, "preview.title"),
        "fit": text(locale, "preview.fit"),
        "reset": text(locale, "preview.reset"),
        "wireframe": text(locale, "preview.wireframe"),
        "axes": text(locale, "preview.axes"),
        "no_preview_path": text(locale, "preview.no_preview_path"),
        "preview_unavailable": text(locale, "preview.preview_unavailable"),
    }


def dialog_labels(locale: str | None) -> dict[str, str]:
    return {
        "error_title": text(locale, "dialog.error_title"),
        "error_body": text(locale, "dialog.error_body"),
        "error_detail": text(locale, "dialog.error_detail"),
        "error_log": text(locale, "dialog.error_log"),
        "error_open_log": text(locale, "dialog.error_open_log"),
    }
