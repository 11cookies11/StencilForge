# StencilForge

快速生成 PCB 钢网模型（Gerber -> STL）。

语言：简体中文 | [English](README.md)

## 概览

本项目将 Gerber + Excellon 导出转换为 3D 钢网模型（STL），
默认面向嘉立创 EDA 的导出，但管线保持通用。

## 快速开始

1. 创建 venv 并安装依赖：`pip install -r requirements.txt`
2. 安装包：`pip install -e .`
3. 根据需要修改 `config/stencilforge.json`
4. 运行：

```bash
stencilforge <gerber_dir> <output_stl>
```

## 桌面 UI（PySide6 + Qt WebEngine）

启动桌面界面：

```bash
stencilforge-ui
```

## 配置参数

- `paste_patterns`：焊膏层文件匹配（默认顶层焊膏）
- `outline_patterns`：板框文件匹配
- `thickness_mm`：钢网厚度
- `paste_offset_mm`：开口缩放（负值为缩小）
- `outline_margin_mm`：无板框时的回退外扩
- `output_mode`：`holes_only` 或 `solid_with_cutouts`
- `arc_steps`：圆弧采样步数
- `curve_resolution`：圆形缓冲精度

## 约定（建议）

- 变更记录：`CHANGELOG.md`（Keep a Changelog 风格）
- 提交信息与 PR 标题：Conventional Commits（例如 `feat:`, `fix:`, `chore:`）
- 社区文档：`CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- Issue / PR 模板：`.github/`

## 许可证

见 `LICENSE`。
