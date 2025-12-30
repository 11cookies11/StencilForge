# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

import importlib.util

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules

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
try:
    import shapely  # noqa: F401
except Exception as exc:
    raise SystemExit("Missing dependency: shapely. Install requirements.txt before packaging.") from exc
datas += collect_data_files("shapely", include_py_files=True)
hiddenimports += collect_submodules("shapely")

try:
    import cadquery  # noqa: F401
    import OCP  # noqa: F401
    import casadi  # noqa: F401
except Exception as exc:
    raise SystemExit("Missing dependency: cadquery/OCP/casadi. Install requirements.txt before packaging.") from exc
datas += collect_data_files("cadquery", include_py_files=True)
datas += collect_data_files("OCP", include_py_files=True)
datas += collect_data_files("casadi", include_py_files=True)
hiddenimports += collect_submodules("cadquery")
hiddenimports += collect_submodules("OCP")
hiddenimports += collect_submodules("casadi")
extra_binaries = (
    collect_dynamic_libs("OCP")
    + collect_dynamic_libs("cadquery")
    + collect_dynamic_libs("casadi")
)

casadi_spec = importlib.util.find_spec("casadi")
if casadi_spec and casadi_spec.submodule_search_locations:
    casadi_dir = Path(list(casadi_spec.submodule_search_locations)[0])
    casadi_candidates = list(casadi_dir.glob("_casadi*.pyd")) + list(casadi_dir.parent.glob("_casadi*.pyd"))
    for candidate in casadi_candidates:
        extra_binaries.append((str(candidate), "."))
        extra_binaries.append((str(candidate), "casadi"))

a = Analysis(
    [str(entry_script)],
    pathex=[str(project_root / "src")],
    binaries=extra_binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "packaging" / "runtime_hooks" / "casadi_dll_path.py")],
    excludes=[
        "PySide6.QtQml",
        "PySide6.QtQmlModels",
        "PySide6.QtQuick",
        "PySide6.QtQuickWidgets",
    ],
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
