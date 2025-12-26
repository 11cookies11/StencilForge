# StencilForge

Fast PCB stencil model generator (Gerber -> STL).

Language: English | [简体中文](README.zh-CN.md)

## Overview

This project converts Gerber + Excellon exports into a 3D stencil model (STL).
It targets JLC EDA exports but keeps the pipeline generic.

## Quick start

1. Create a venv and install deps: `pip install -r requirements.txt`
2. Install the package: `pip install -e .`
3. Update `config/stencilforge.json` as needed
4. Run:

```bash
stencilforge <gerber_dir> <output_stl>
```

## UI (Vue + PySide6 + Qt WebEngine)

Launch the desktop UI:

```bash
stencilforge-ui
```

## Config parameters

- `paste_patterns`: paste layer file patterns (top paste default)
- `outline_patterns`: board outline patterns
- `thickness_mm`: stencil thickness
- `paste_offset_mm`: shrink/expand opening (negative shrinks)
- `outline_margin_mm`: fallback outline margin when no outline file exists
- `output_mode`: `holes_only` or `solid_with_cutouts`
- `arc_steps`: number of steps to approximate arcs
- `curve_resolution`: buffer resolution for circles

## Conventions (recommended)

- Changelog: `CHANGELOG.md` (Keep a Changelog style)
- Commit messages & PR titles: Conventional Commits (e.g. `feat:`, `fix:`, `chore:`)
- Community docs: `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`
- Issue / PR templates: `.github/`

## License

See `LICENSE`.
