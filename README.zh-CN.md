# StencilForge

<p align="left">
  <a href="https://github.com/11cookies11/StencilForge">
    <img alt="GitHub Repo" src="https://img.shields.io/badge/GitHub-11cookies11%2FStencilForge-181717?logo=github&logoColor=white">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/11cookies11/StencilForge?color=2b6cb0">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/stargazers">
    <img alt="Stars" src="https://img.shields.io/github/stars/11cookies11/StencilForge?style=flat">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/issues">
    <img alt="Issues" src="https://img.shields.io/github/issues/11cookies11/StencilForge">
  </a>
  <a href="https://github.com/11cookies11/StencilForge/releases">
    <img alt="Release" src="https://img.shields.io/github/v/release/11cookies11/StencilForge">
  </a>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="Vue" src="https://img.shields.io/badge/Vue-3-42b883?logo=vue.js&logoColor=white">
  <img alt="CadQuery" src="https://img.shields.io/badge/CadQuery-2.4-3b82f6">
  <img alt="VTK" src="https://img.shields.io/badge/VTK-9.3-8a2be2">
</p>

<p align="center">
  <img alt="StencilForge logo" src="assets/store/logo_1080x1080.png" width="220">
</p>

StencilForge 是一个面向 PCB 钢网的桌面工具，用于将 Gerber 输入生成 STL 模型。

## 概览

StencilForge 会把 Gerber 和 Excellon 导出转换成用于钢网和定位治具的 3D STL 模型。它支持桌面 UI、可配置的几何处理流程，以及 CadQuery 和 Trimesh 两种后端。

## 特性

- 快速的 Gerber 到 STL 流程
- CadQuery 或 Trimesh 后端
- 支持可配置偏移的钢网开口
- 支持台阶式或外框式定位结构
- 基于 VTK 的预览窗口，不依赖 WebGL

## 截图

**实物钢网**
![实物钢网](assets/images/实物照片.jpg)

**主界面**
![主界面](assets/images/菜单照片.png)

**STL 预览**
![STL 预览](assets/images/预览照片.png)

## 快速开始

1. 创建虚拟环境并安装依赖：`pip install -r requirements.txt`
2. 安装项目：`pip install -e .`
3. 按需修改 `config/stencilforge.json`
4. 运行：

```bash
stencilforge <gerber_dir> <output_stl>
```

## 桌面 UI

构建前端 UI：

```bash
cd ui-vue
npm install
npm run build
```

启动桌面 UI：

```bash
stencilforge-ui
```

## 配置参数

- `paste_patterns`：焊膏层文件匹配规则
- `outline_patterns`：板框层文件匹配规则
- `thickness_mm`：钢网厚度
- `paste_offset_mm`：开口偏移，负值表示缩小
- `outline_margin_mm`：找不到板框文件时的备用外扩边距
- `output_mode`：`holes_only` 或 `solid_with_cutouts`
- `model_backend`：`trimesh` 或 `cadquery`
- `locator_enabled`：是否启用定位结构
- `locator_mode`：`step` 或 `wall`
- `locator_height_mm`：定位外框高度
- `locator_width_mm`：定位外框宽度
- `locator_clearance_mm`：定位间隙
- `locator_step_height_mm`：台阶高度
- `locator_step_width_mm`：台阶宽度
- `locator_open_side`：开口方向（`none/top/right/bottom/left`）
- `locator_open_width_mm`：开口宽度
- `stl_linear_deflection`：STL 线性偏差，单位 mm
- `stl_angular_deflection`：STL 角度偏差，单位弧度
- `arc_steps`：圆弧近似步数
- `curve_resolution`：圆形缓冲分辨率
- `qfn_regen_enabled`：是否启用 QFN 开口重建
- `qfn_min_feature_mm`：最小可打印特征尺寸
- `qfn_confidence_threshold`：QFN 重建置信度阈值
- `qfn_max_pad_width_mm`：判定为 QFN pad 的最大宽度

## 约定

- 更新日志：`CHANGELOG.md`
- 提交信息和 PR 标题：Conventional Commits
- 社区文档：`CONTRIBUTING.md`、`SECURITY.md`、`CODE_OF_CONDUCT.md`
- Issue / PR 模板：`.github/`

## 许可证

GPL-3.0-only，见 `LICENSE`。
