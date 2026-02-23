from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import traceback
import zipfile

import trimesh

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from stencilforge.config import StencilConfig
from stencilforge.pipeline import generate_stencil


def _default_config(quality_mode: str, voxel_pitch_mm: float) -> StencilConfig:
    return StencilConfig.from_dict(
        {
            "model_backend": "sfmesh",
            "sfmesh_quality_mode": quality_mode,
            "sfmesh_voxel_pitch_mm": voxel_pitch_mm,
            "paste_patterns": [
                "*gtp*",
                "*.gtp",
                "*gbp*",
                "*.gbp",
                "*paste*top*",
                "*top*paste*",
                "*paste*bottom*",
                "*bottom*paste*",
                "*tcream*",
                "*cream*top*",
                "*smt*top*",
            ],
            "outline_patterns": ["*gko*", "*gm1*", "*outline*", "*edge*cuts*"],
            "outline_fill_rule": "evenodd",
            "outline_close_strategy": "robust_polygonize",
            "outline_merge_tol_mm": 0.01,
            "outline_snap_eps_mm": 0.05,
            "outline_gap_bridge_mm": 0.1,
            "sfmesh_adaptive_pitch_enabled": True,
            "sfmesh_adaptive_pitch_min_mm": voxel_pitch_mm,
            "sfmesh_adaptive_pitch_max_mm": max(voxel_pitch_mm, 0.24),
            "sfmesh_watertight_face_limit": 250000,
        }
    )


def _collect_metrics(stl_path: Path) -> dict:
    mesh = trimesh.load_mesh(stl_path, force="mesh")
    bounds = mesh.bounds.tolist() if mesh.bounds is not None else None
    return {
        "faces": int(mesh.faces.shape[0]) if getattr(mesh, "faces", None) is not None else 0,
        "watertight": bool(getattr(mesh, "is_watertight", False)),
        "euler": int(getattr(mesh, "euler_number", 0)),
        "volume": float(getattr(mesh, "volume", 0.0)),
        "bounds": bounds,
    }


def _load_expect(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _list_samples(fixtures_dir: Path) -> list[tuple[str, Path]]:
    items: list[tuple[str, Path]] = []
    for case_dir in sorted(fixtures_dir.glob("case_*/")):
        input_dir = case_dir / "input"
        if not input_dir.exists():
            continue
        for zip_path in sorted(input_dir.glob("*.zip")):
            key = f"{case_dir.name}/{zip_path.name}"
            items.append((key, zip_path))
    return items


def _cache_key(zip_path: Path, config: StencilConfig) -> str:
    stat = zip_path.stat()
    payload = {
        "zip": str(zip_path.resolve()),
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
        "cfg": {
            "mode": config.sfmesh_quality_mode,
            "pitch": config.sfmesh_voxel_pitch_mm,
            "adaptive": config.sfmesh_adaptive_pitch_enabled,
            "pitch_min": config.sfmesh_adaptive_pitch_min_mm,
            "pitch_max": config.sfmesh_adaptive_pitch_max_mm,
            "wt_face_limit": config.sfmesh_watertight_face_limit,
            "simplify": config.sfmesh_simplify_tol_mm,
            "min_poly": config.sfmesh_min_polygon_area_mm2,
            "min_hole": config.sfmesh_min_hole_area_mm2,
            "decimate": config.sfmesh_decimate_target_ratio,
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def _run_sample_task(
    key: str,
    zip_path: Path,
    output_stl: Path,
    config_data: dict,
    expect_item: dict,
    strict_expect: bool,
    cache_dir: Path | None,
) -> dict:
    cache_key = None
    cache_path = None
    metrics = None
    cache_hit = False
    config = StencilConfig.from_dict(config_data)
    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_key = _cache_key(zip_path, config)
        cache_path = cache_dir / f"{cache_key}.json"
        if cache_path.exists() and output_stl.exists():
            try:
                cached = json.loads(cache_path.read_text(encoding="utf-8"))
                metrics = cached.get("metrics")
                cache_hit = metrics is not None
            except Exception:
                metrics = None
    try:
        if metrics is None:
            with tempfile.TemporaryDirectory(prefix="sfmesh_regression_") as temp_dir:
                extract_dir = Path(temp_dir) / "input"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(extract_dir)
                output_stl.parent.mkdir(parents=True, exist_ok=True)
                generate_stencil(extract_dir, output_stl, config)
                metrics = _collect_metrics(output_stl)
            if cache_path is not None and cache_key is not None:
                cache_path.write_text(json.dumps({"key": cache_key, "metrics": metrics}, ensure_ascii=False), encoding="utf-8")
        compare = _compare_with_expect(expect_item, metrics)
        success = compare["matched"] is not False
        if strict_expect and compare["matched"] is None:
            success = False
        case_name = key.split("/", 1)[0]
        return {
            "case": case_name,
            "sample": zip_path.name,
            "zip_path": str(zip_path),
            "output_stl": str(output_stl),
            "success": success,
            "metrics": metrics,
            "expect": expect_item,
            "compare": compare,
            "from_cache": cache_hit,
        }
    except Exception as exc:
        case_name = key.split("/", 1)[0]
        return {
            "case": case_name,
            "sample": zip_path.name,
            "zip_path": str(zip_path),
            "output_stl": str(output_stl),
            "success": False,
            "error": str(exc),
            "trace": traceback.format_exc(),
        }


def _compare_with_expect(expect_item: dict, actual: dict) -> dict:
    if not expect_item:
        return {"matched": None, "reason": "no_expect"}

    tol_faces = int(expect_item.get("tol_faces", 0))
    tol_volume = float(expect_item.get("tol_volume", 0.0))
    tol_bounds = float(expect_item.get("tol_bounds", 0.0))

    faces_ok = abs(int(expect_item.get("faces", 0)) - actual["faces"]) <= tol_faces
    volume_ok = abs(float(expect_item.get("volume", 0.0)) - actual["volume"]) <= tol_volume

    bounds_ok = True
    exp_bounds = expect_item.get("bounds")
    if exp_bounds is not None and actual.get("bounds") is not None:
        diffs = []
        for i in range(2):
            for j in range(3):
                diffs.append(abs(float(exp_bounds[i][j]) - float(actual["bounds"][i][j])))
        bounds_ok = all(d <= tol_bounds for d in diffs)

    matched = faces_ok and volume_ok and bounds_ok
    return {
        "matched": matched,
        "reason": "ok" if matched else "mismatch",
        "checks": {
            "faces_ok": faces_ok,
            "volume_ok": volume_ok,
            "bounds_ok": bounds_ok,
        },
    }


def run_regression(
    fixtures_dir: Path,
    output_dir: Path,
    expect_path: Path,
    strict_expect: bool,
    quality_mode: str,
    voxel_pitch_mm: float,
    jobs: int,
    use_cache: bool,
) -> dict:
    config = _default_config(quality_mode, voxel_pitch_mm)
    config.validate()
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / ".cache" if use_cache else None

    expect_data = _load_expect(expect_path)
    results: list[dict] = []
    samples = _list_samples(fixtures_dir)
    config_data = dict(config.__dict__)

    if jobs <= 1:
        for key, zip_path in samples:
            case_name = key.split("/", 1)[0]
            case_output_dir = output_dir / case_name
            output_stl = case_output_dir / f"{zip_path.stem}.stl"
            expect_item = expect_data.get(key, {})
            results.append(
                _run_sample_task(
                    key,
                    zip_path,
                    output_stl,
                    config_data,
                    expect_item,
                    strict_expect,
                    cache_dir,
                )
            )
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            future_map = {}
            for key, zip_path in samples:
                case_name = key.split("/", 1)[0]
                case_output_dir = output_dir / case_name
                output_stl = case_output_dir / f"{zip_path.stem}.stl"
                expect_item = expect_data.get(key, {})
                fut = pool.submit(
                    _run_sample_task,
                    key,
                    zip_path,
                    output_stl,
                    config_data,
                    expect_item,
                    strict_expect,
                    cache_dir,
                )
                future_map[fut] = key
            for fut in as_completed(future_map):
                results.append(fut.result())

    results.sort(key=lambda x: (x.get("case", ""), x.get("sample", "")))

    success_count = sum(1 for r in results if r.get("success"))
    watertight_count = sum(1 for r in results if r.get("metrics", {}).get("watertight"))
    cached_count = sum(1 for r in results if r.get("from_cache"))
    report = {
        "total": len(results),
        "success": success_count,
        "failed": len(results) - success_count,
        "watertight": watertight_count,
        "cached": cached_count,
        "strict_expect": strict_expect,
        "quality_mode": quality_mode,
        "voxel_pitch_mm": voxel_pitch_mm,
        "jobs": jobs,
        "cache": use_cache,
        "results": results,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sfmesh regression on fixture ZIPs.")
    parser.add_argument("--fixtures", type=Path, default=Path("tests/fixtures/gerber"))
    parser.add_argument("--output", type=Path, default=Path("tests/artifacts/sfmesh_regression"))
    parser.add_argument("--expect", type=Path, default=Path("tests/fixtures/gerber/expect.json"))
    parser.add_argument("--strict-expect", action="store_true")
    parser.add_argument("--quality-mode", choices=["fast", "auto", "watertight"], default="fast")
    parser.add_argument("--voxel-pitch-mm", type=float, default=0.08)
    parser.add_argument("--jobs", type=int, default=max(1, min(4, (os.cpu_count() or 2) // 2)))
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    report = run_regression(
        args.fixtures,
        args.output,
        args.expect,
        args.strict_expect,
        args.quality_mode,
        args.voxel_pitch_mm,
        args.jobs,
        not args.no_cache,
    )
    args.output.mkdir(parents=True, exist_ok=True)
    summary_path = args.output / "summary.json"
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Total: {report['total']}  Success: {report['success']}  Failed: {report['failed']}")
    print(f"Watertight: {report['watertight']} / {report['total']}")
    print(f"Cached: {report['cached']} / {report['total']}  Jobs: {report['jobs']}")
    print(f"Summary: {summary_path}")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
