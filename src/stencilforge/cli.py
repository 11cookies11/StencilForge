from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .aperture_workspace import (
    default_aperture_workspace,
    export_aperture_workspace_payload,
    import_aperture_workspace_payload,
    normalize_aperture_workspace,
    validate_aperture_workspace_payload,
)
from .config import StencilConfig
from .pipeline import generate_stencil
from .pipeline.core import _find_files

def _bool(value: str) -> bool:
    """Parse a boolean string for argparse."""
    lowered = value.lower()
    if lowered in ("true", "1", "yes", "on"):
        return True
    if lowered in ("false", "0", "no", "off"):
        return False
    raise argparse.ArgumentTypeError(f"Expected boolean, got {value!r}")


# ── config field name → CLI flag name ──────────────────────────────
# Each dict entry maps the StencilConfig field name to the argparse dest (kebab-case)
_FIELD_MAP: list[tuple[str, str, type, str]] = [
    # (config_field, cli_dest, type, help_suffix)
    ("thickness_mm", "thickness_mm", float, "Stencil thickness in mm"),
    ("paste_offset_mm", "paste_offset_mm", float, "Paste aperture expansion (negative = shrink)"),
    ("mask_opening_scale", "mask_opening_scale", float, "Scale solder-mask openings before stencil rules"),
    ("outline_margin_mm", "outline_margin_mm", float, "Stencil outline margin beyond board edge"),
    ("output_mode", "output_mode", str, '"holes_only" or "solid_with_cutouts"'),
    ("printer_profile", "printer_profile", str, '"generic" or "fsm"'),
    ("model_backend", "model_backend", str, '"trimesh" or "cadquery"'),
    ("locator_enabled", "locator_enabled", _bool, "Enable locator/fiducial features"),
    ("locator_height_mm", "locator_height_mm", float, "Locator ring height"),
    ("locator_width_mm", "locator_width_mm", float, "Locator ring width"),
    ("locator_clearance_mm", "locator_clearance_mm", float, "Locator clearance from board"),
    ("locator_step_height_mm", "locator_step_height_mm", float, "Locator step height"),
    ("locator_step_width_mm", "locator_step_width_mm", float, "Locator step width"),
    ("locator_mode", "locator_mode", str, '"step" or "wall"'),
    ("locator_open_side", "locator_open_side", str, '"none", "top", "right", "bottom", "left"'),
    ("locator_open_width_mm", "locator_open_width_mm", float, "Locator open-side gap width"),
    ("sfmesh_quality_mode", "sfmesh_quality_mode", str, '"fast", "auto", or "watertight"'),
    ("sfmesh_voxel_pitch_mm", "sfmesh_voxel_pitch_mm", float, "SfMesh voxel pitch in mm"),
    ("sfmesh_adaptive_pitch_enabled", "sfmesh_adaptive_pitch_enabled", _bool, "Enable adaptive voxel pitch"),
    ("sfmesh_adaptive_pitch_min_mm", "sfmesh_adaptive_pitch_min_mm", float, "Min adaptive pitch"),
    ("sfmesh_adaptive_pitch_max_mm", "sfmesh_adaptive_pitch_max_mm", float, "Max adaptive pitch"),
    ("sfmesh_watertight_face_limit", "sfmesh_watertight_face_limit", int, "Watertight mode face limit"),
    ("sfmesh_simplify_tol_mm", "sfmesh_simplify_tol_mm", float, "SfMesh simplification tolerance"),
    ("sfmesh_min_polygon_area_mm2", "sfmesh_min_polygon_area_mm2", float, "Min polygon area to keep"),
    ("sfmesh_min_hole_area_mm2", "sfmesh_min_hole_area_mm2", float, "Min hole area to keep"),
    ("sfmesh_decimate_target_ratio", "sfmesh_decimate_target_ratio", float, "Decimate target ratio (0-1]"),
    ("sfmesh_hole_protect_enabled", "sfmesh_hole_protect_enabled", _bool, "Enable hole protection"),
    ("sfmesh_hole_protect_max_width_mm", "sfmesh_hole_protect_max_width_mm", float, "Max hole width to protect"),
    ("sfmesh_hole_pitch_divisor", "sfmesh_hole_pitch_divisor", float, "Hole pitch divisor"),
    ("sfmesh_chunked_watertight_enabled", "sfmesh_chunked_watertight_enabled", _bool, "Enable chunked watertight mesh"),
    ("sfmesh_chunk_size_mm", "sfmesh_chunk_size_mm", float, "Chunk size for watertight mesh"),
    ("sfmesh_chunk_overlap_mm", "sfmesh_chunk_overlap_mm", float, "Chunk overlap for watertight mesh"),
    ("stl_quality", "stl_quality", str, 'STL quality preset: "fast", "balanced", "high_quality", or empty'),
    ("stl_linear_deflection", "stl_linear_deflection", float, "STL linear deflection"),
    ("stl_angular_deflection", "stl_angular_deflection", float, "STL angular deflection"),
    ("stl_tolerance", "stl_tolerance", float, "STL tolerance"),
    ("arc_steps", "arc_steps", int, "Arc tessellation segments"),
    ("curve_resolution", "curve_resolution", int, "Curve resolution for offset/buffer ops"),
    ("qfn_regen_enabled", "qfn_regen_enabled", _bool, "Enable QFN pad reconstruction"),
    ("qfn_min_feature_mm", "qfn_min_feature_mm", float, "QFN min feature size"),
    ("qfn_confidence_threshold", "qfn_confidence_threshold", float, "QFN detection confidence threshold"),
    ("qfn_max_pad_width_mm", "qfn_max_pad_width_mm", float, "QFN max pad width"),
    ("outline_fill_rule", "outline_fill_rule", str, '"legacy" or "evenodd"'),
    ("outline_close_strategy", "outline_close_strategy", str, '"legacy", "graph", or "robust_polygonize"'),
    ("outline_merge_tol_mm", "outline_merge_tol_mm", float, "Outline merge tolerance"),
    ("outline_snap_eps_mm", "outline_snap_eps_mm", float, "Outline snap epsilon"),
    ("outline_arc_max_chord_error_mm", "outline_arc_max_chord_error_mm", float, "Outline arc chord error"),
    ("outline_gap_bridge_mm", "outline_gap_bridge_mm", float, "Outline gap bridging distance"),
    ("cadquery_simplify_tol_mm", "cadquery_simplify_tol_mm", float, "CadQuery simplification tolerance"),
    ("cadquery_short_edge_min_mm", "cadquery_short_edge_min_mm", float, "CadQuery min short edge"),
    ("cadquery_quantize_mm", "cadquery_quantize_mm", float, "CadQuery quantization step"),
    ("ui_debug_plot_outline", "ui_debug_plot_outline", _bool, "Show outline debug plot"),
    ("ui_debug_plot_max_segments", "ui_debug_plot_max_segments", int, "Max debug plot segments"),
    ("ui_debug_plot_max_offset_vectors", "ui_debug_plot_max_offset_vectors", int, "Max offset vectors to plot"),
    ("ui_debug_plot_offset_min_mm", "ui_debug_plot_offset_min_mm", float, "Min offset to plot"),
    ("paste_patterns", "paste_patterns", "list", "Gerber paste layer patterns (accepts multiple)"),
    ("paste_side", "paste_side", str, '"top", "bottom", or "both"'),
    ("outline_patterns", "outline_patterns", "list", "Gerber outline layer patterns (accepts multiple)"),
    ("drill_patterns", "drill_patterns", "list", "Drill file patterns (accepts multiple)"),
]


def build_parser() -> argparse.ArgumentParser:
    """Build the full argument parser with subcommands and all config flags."""
    parser = argparse.ArgumentParser(
        prog="stencilforge",
        description="Fast PCB stencil model generator (Gerber -> STL).",
    )
    sub = parser.add_subparsers(dest="command", title="subcommands")

    # ── generate ──────────────────────────────────────────────────
    gen = sub.add_parser("generate", help="Generate STL from Gerber files")
    gen.add_argument("input_dir", type=Path, help="Directory with Gerber files or ZIP archive")
    gen.add_argument("output_stl", type=Path, help="Output STL path")
    gen.add_argument("--config", type=Path, default=None, help="Path to stencilforge.json config")
    gen.add_argument("--aperture-rules", type=Path, default=None, help="Path to aperture rules JSON")
    gen.add_argument("--verbose", action="store_true", help="Print detailed progress")
    _add_config_args(gen)

    # ── scan ──────────────────────────────────────────────────────
    sc = sub.add_parser("scan", help="List files matching paste/outline/drill patterns")
    sc.add_argument("input_dir", type=Path, help="Directory with Gerber files or ZIP archive")
    sc.add_argument("--config", type=Path, default=None, help="Path to stencilforge.json config")

    # ── validate ──────────────────────────────────────────────────
    va = sub.add_parser("validate", help="Validate a stencilforge.json config file")
    va.add_argument("--config", type=Path, default=None, help="Path to stencilforge.json config (default: user config)")

    # ── dump-default-config ───────────────────────────────────────
    sub.add_parser("dump-default-config", help="Print default StencilConfig as JSON to stdout")

    return parser


def _add_config_args(parser: argparse.ArgumentParser) -> None:
    """Register all config fields as optional arguments grouped by category."""
    groups: dict[str, argparse._ArgumentGroup] = {}

    for field_name, dest, typ, help_text in _FIELD_MAP:
        category = _arg_group(field_name)
        if category not in groups:
            groups[category] = parser.add_argument_group(category)
        grp = groups[category]
        flag = f"--{dest.replace('_', '-')}"
        kwargs: dict = {"dest": dest, "help": help_text}
        if typ == "list":
            kwargs["nargs"] = "*"
            kwargs["default"] = None
        elif typ is _bool:
            kwargs["type"] = _bool
            kwargs["default"] = None
        elif typ is int:
            kwargs["type"] = int
            kwargs["default"] = None
        else:
            kwargs["type"] = str if typ is str else typ
            kwargs["default"] = None
        grp.add_argument(flag, **kwargs)


def _arg_group(field: str) -> str:
    """Map a config field name to an argument group label."""
    if field.startswith("locator_"):
        return "locator options"
    if field.startswith("sfmesh_"):
        return "sfmesh options"
    if field.startswith("stl_"):
        return "stl quality options"
    if field.startswith("qfn_"):
        return "qfn options"
    if field.startswith("outline_"):
        return "outline options"
    if field.startswith("cadquery_"):
        return "cadquery options"
    if field.startswith("ui_debug_"):
        return "debug options"
    if field.endswith("_patterns"):
        return "file pattern options"
    if field in ("arc_steps", "curve_resolution"):
        return "resolution options"
    if field in ("output_mode", "model_backend", "printer_profile"):
        return "output options"
    if field in ("paste_side", "mask_opening_scale"):
        return "paste options"
    return "geometry options"


# ── command handlers ────────────────────────────────────────────────────────


def _build_config_from_args(args: argparse.Namespace) -> StencilConfig:
    """Merge file config with CLI overrides."""
    file_data: dict = {}
    config_path: Path | None = getattr(args, "config", None)
    if config_path is not None:
        try:
            loaded = StencilConfig.from_json(config_path)
            file_data = loaded.to_dict()
        except Exception:
            file_data = {}

    cli_overrides: dict = {}
    for field_name, dest, _typ, _help in _FIELD_MAP:
        raw = getattr(args, dest, None)
        if raw is not None:
            cli_overrides[field_name] = raw

    merged = {**file_data, **cli_overrides}
    return StencilConfig.from_dict(merged)


def _load_aperture_rules(path: Path | None) -> dict | None:
    """Load and validate aperture rules JSON from a file path."""
    if path is None:
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Failed to read aperture rules file: {exc}") from exc
    result = validate_aperture_workspace_payload(raw)
    if not result["ok"]:
        issues = "\n".join(result["issues"])
        raise SystemExit(f"Invalid aperture rules:\n{issues}")
    return normalize_aperture_workspace(result.get("workspace", raw))


def _handle_generate(args: argparse.Namespace) -> int:
    input_dir: Path = args.input_dir
    output_stl: Path = args.output_stl

    if not input_dir.exists():
        print(f"Error: input path does not exist: {input_dir}", file=sys.stderr)
        return 1

    config = _build_config_from_args(args)
    try:
        config.validate()
    except ValueError as exc:
        print(f"Error: invalid config — {exc}", file=sys.stderr)
        return 1

    aperture_workspace = _load_aperture_rules(getattr(args, "aperture_rules", None))
    verbose: bool = getattr(args, "verbose", False)

    if verbose:
        print(f"Input:        {input_dir}")
        print(f"Output:       {output_stl}")
        print(f"Backend:      {config.model_backend}")
        print(f"Output mode:  {config.output_mode}")
        if config.thickness_managed_by_printer_profile:
            print(f"Thickness:    {config.effective_thickness_mm} mm (FSM managed; user {config.thickness_mm} mm ignored)")
        else:
            print(f"Thickness:    {config.thickness_mm} mm")
        if aperture_workspace:
            profile = aperture_workspace.get("profileName", "(unnamed)")
            print(f"Aperture:     {profile}")
        print("Generating...")

    try:
        result = generate_stencil(input_dir, output_stl, config, aperture_workspace)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    if output_stl.exists():
        size_kb = output_stl.stat().st_size / 1024
        if verbose:
            print(f"Done: {output_stl} ({size_kb:.1f} KB)")
        else:
            print(str(output_stl))
        if result and verbose:
            import pprint
            pprint.pprint(result)
    else:
        print(f"Error: STL was not created at {output_stl}", file=sys.stderr)
        return 1
    return 0


def _handle_scan(args: argparse.Namespace) -> int:
    input_dir: Path = args.input_dir
    if not input_dir.exists():
        print(f"Error: input path does not exist: {input_dir}", file=sys.stderr)
        return 1

    config = _build_config_from_args(args)
    for category, patterns in [
        ("paste", config.paste_patterns),
        ("outline", config.outline_patterns),
        ("drill", config.drill_patterns),
    ]:
        files = _find_files(input_dir, patterns)
        print(f"[{category}] ({len(files)} files):")
        for f in files:
            try:
                print(f"  {f.relative_to(input_dir)}")
            except UnicodeEncodeError:
                print(f"  {f.name}")
        if not files:
            print("  (none)")
        print()
    return 0


def _handle_validate(args: argparse.Namespace) -> int:
    config_path: Path | None = getattr(args, "config", None)
    if config_path is None:
        config_path = StencilConfig.default_path(Path.cwd())
    try:
        config = StencilConfig.from_json(config_path)
        config.validate()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Error: cannot read config — {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Invalid config: {exc}", file=sys.stderr)
        return 1
    print("Config OK")
    return 0


def _handle_dump_config(args: argparse.Namespace) -> int:  # noqa: ARG001
    config = StencilConfig.from_dict({})
    print(json.dumps(config.to_dict(), indent=2, ensure_ascii=False))
    return 0


# ── backwards-compat dispatch ────────────────────────────────────────────────


def _guess_command(args: list[str]) -> list[str]:
    """If no subcommand is given and args look like old-style positional, insert 'generate'."""
    if not args:
        return args
    known_subcommands = {"generate", "scan", "validate", "dump-default-config", "-h", "--help"}
    if args[0] in known_subcommands:
        return args
    # First arg is not a subcommand — assume old-style: <input_dir> <output_stl>
    return ["generate"] + args


def main() -> int:
    parser = build_parser()

    raw_args = sys.argv[1:]
    fixed_args = _guess_command(raw_args)
    args = parser.parse_args(fixed_args)

    cmd = args.command
    if cmd == "generate":
        return _handle_generate(args)
    if cmd == "scan":
        return _handle_scan(args)
    if cmd == "validate":
        return _handle_validate(args)
    if cmd == "dump-default-config":
        return _handle_dump_config(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
