import os
import sys
from pathlib import Path

exe_dir = Path(sys.executable).resolve().parent
internal_dir = exe_dir / "_internal"
base_dir = internal_dir if internal_dir.exists() else Path(getattr(sys, "_MEIPASS", exe_dir))
casadi_dir = base_dir / "casadi"

# CasADi requires the parent package path on sys.path (not the casadi folder itself).
if base_dir.exists() and str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

paths = [base_dir, casadi_dir]
for path in paths:
    if not path.exists():
        continue
    try:
        os.add_dll_directory(str(path))
    except Exception:
        pass
    os.environ["PATH"] = f"{path};{os.environ.get('PATH', '')}"
