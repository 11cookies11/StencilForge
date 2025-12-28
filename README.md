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

```text
+--------------------------------------------------+
|  StencilForge                                    |
|  PCB Stencil + Fixture Generator (Gerber -> STL) |
+--------------------------------------------------+
```

Language: English | [简体中文](README.zh-CN.md)

## Overview ✨

StencilForge converts Gerber + Excellon exports into 3D STL models for
PCB stencils and locator fixtures. It targets common EDA exports while
keeping the pipeline generic and configurable.

## Highlights 🚀

- Fast Gerber -> STL pipeline
- CadQuery or Trimesh backend
- Stencil cutouts with configurable offsets
- Locator structure: step or wall
- VTK preview window (no WebGL)

## Gallery 🖼️

**Printed stencil**
![Printed stencil](assets/images/实物照片.jpg)

**UI main screen**
![UI main screen](assets/images/菜单照片.png)

**STL preview**
![STL preview](assets/images/预览照片.png)

## Quick start ⚡

1. Create a venv and install deps: `pip install -r requirements.txt`
2. Install the package: `pip install -e .`
3. Update `config/stencilforge.json` as needed
4. Run:

```bash
stencilforge <gerber_dir> <output_stl>
```

## UI (Vue + PySide6 + Qt WebEngine) 🧭

Build the UI:

```bash
cd ui-vue
npm install
npm run build
```

Launch the desktop UI:

```bash
stencilforge-ui
```

## Config parameters 🧰

- `paste_patterns`: paste layer file patterns (top paste default)
- `outline_patterns`: board outline patterns
- `thickness_mm`: stencil thickness
- `paste_offset_mm`: shrink/expand opening (negative shrinks)
- `outline_margin_mm`: fallback outline margin when no outline file exists
- `output_mode`: `holes_only` or `solid_with_cutouts`
- `model_backend`: `trimesh` or `cadquery`
- `locator_enabled`: enable locator structure
- `locator_mode`: `step` (recess) or `wall` (frame)
- `locator_height_mm`: wall height
- `locator_width_mm`: wall width
- `locator_clearance_mm`: clearance gap
- `locator_step_height_mm`: step height (PCB recess)
- `locator_step_width_mm`: step width (expands outward)
- `locator_open_side`: open side (`none/top/right/bottom/left`)
- `locator_open_width_mm`: open width
- `stl_linear_deflection`: STL linear deflection (mm, smaller = finer)
- `stl_angular_deflection`: STL angular deflection (radians)
- `arc_steps`: number of steps to approximate arcs
- `curve_resolution`: buffer resolution for circles
- `qfn_regen_enabled`: enable QFN paste regeneration
- `qfn_min_feature_mm`: minimum printable feature for FDM
- `qfn_confidence_threshold`: confidence threshold to modify apertures
- `qfn_max_pad_width_mm`: max pad width to consider as QFN pad

## Conventions (recommended) 📌

- Changelog: `CHANGELOG.md` (Keep a Changelog style)
- Commit messages & PR titles: Conventional Commits (e.g. `feat:`, `fix:`, `chore:`)
- Community docs: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- Issue / PR templates: `.github/`

## License 📄

GPL-3.0-only. See `LICENSE`.
