# StencilForge 🛠️

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

```text
+--------------------------------------------------+
|  StencilForge                                    |
|  PCB 钢网与定位治具生成 (Gerber -> STL)          |
+--------------------------------------------------+
```

语言: 简体中文 | [English](README.md)

## 简介 ✨

StencilForge 用于把 Gerber + Excellon 导出转换为 3D 钢网模型 (STL)。
支持桌面 UI 预览，适合快速生成钢网和定位治具。

## 特性 🚀

- Gerber -> STL 一键生成
- CadQuery/Trimesh 建模后端可选
- 钢网开口与外形自动处理
- PCB 定位结构: 台阶或外框墙
- VTK 预览窗口 (不依赖 WebGL)

## ???? ???

**????**
![????](assets/images/????.jpg)

**???**
![???](assets/images/????.png)

**????**
![????](assets/images/????.png)

## 快速开始 ⚡

1. 创建 venv 并安装依赖: `pip install -r requirements.txt`
2. 安装包: `pip install -e .`
3. 按需修改 `config/stencilforge.json`
4. 运行:

```bash
stencilforge <gerber_dir> <output_stl>
```

## 桌面 UI (Vue + PySide6 + Qt WebEngine) 🧭

构建前端:

```bash
cd ui-vue
npm install
npm run build
```

启动桌面 UI:

```bash
stencilforge-ui
```

## 配置参数 🧰

- `paste_patterns`: 焊膏层文件匹配规则
- `outline_patterns`: 外形层文件匹配规则
- `thickness_mm`: 钢网厚度
- `paste_offset_mm`: 开口偏移 (负值为缩小)
- `outline_margin_mm`: 无外形时的回退边距
- `output_mode`: `holes_only` 或 `solid_with_cutouts`
- `model_backend`: `trimesh` 或 `cadquery`
- `locator_enabled`: 是否启用定位结构
- `locator_mode`: `step` (台阶) 或 `wall` (外框墙)
- `locator_height_mm`: 外框墙高度
- `locator_width_mm`: 外框墙宽度
- `locator_clearance_mm`: 定位间隙
- `locator_step_height_mm`: 台阶高度 (PCB 下沉高度)
- `locator_step_width_mm`: 台阶宽度 (向外扩展)
- `locator_open_side`: 开口方向 (`none/top/right/bottom/left`)
- `locator_open_width_mm`: 开口宽度
- `stl_linear_deflection`: STL 线性偏差 (mm)
- `stl_angular_deflection`: STL 角度偏差 (弧度)
- `arc_steps`: 圆弧采样步数
- `curve_resolution`: 圆形缓冲分辨率
- `qfn_regen_enabled`: 是否启用 QFN 开口重建
- `qfn_min_feature_mm`: FDM 最小可打印特征
- `qfn_confidence_threshold`: 置信度阈值 (低于该值不修改)
- `qfn_max_pad_width_mm`: 识别 QFN pad 的最大宽度

## 约定 (建议) 📌

- Changelog: `CHANGELOG.md` (Keep a Changelog 风格)
- 提交信息与 PR 标题: Conventional Commits
- 社区文档: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`

## 许可证 📄

GPL-3.0-only?? `LICENSE`?
