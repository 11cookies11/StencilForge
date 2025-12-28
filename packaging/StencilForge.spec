# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

project_root = Path(SPECPATH).resolve().parent
entry_script = project_root / "src" / "stencilforge" / "ui_app.py"

datas = []
ui_dist = project_root / "ui-vue" / "dist"
if ui_dist.exists():
    datas.append((str(ui_dist), "ui-vue/dist"))

config_dir = project_root / "config"
if config_dir.exists():
    datas.append((str(config_dir), "config"))

assets_dir = project_root / "assets"
if assets_dir.exists():
    datas.append((str(assets_dir), "assets"))

hiddenimports = collect_submodules("vtkmodules")

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="StencilForge",
    icon=str(project_root / "assets" / "icon.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="StencilForge",
)
