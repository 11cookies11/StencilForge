from __future__ import annotations

import argparse
from pathlib import Path

from .config import StencilConfig
from .pipeline import generate_stencil


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a stencil STL from Gerber.")
    parser.add_argument("input_dir", type=Path, help="Directory with Gerber files")
    parser.add_argument("output_stl", type=Path, help="Output STL path")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to stencilforge.json config",
    )
    args = parser.parse_args()

    project_root = Path.cwd()
    config_path = args.config or StencilConfig.default_path(project_root)
    config = StencilConfig.from_json(config_path)

    generate_stencil(args.input_dir, args.output_stl, config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
