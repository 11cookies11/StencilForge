from __future__ import annotations

import sys

from stencilforge.cli import main as cli_main
from stencilforge.ui_app import main as ui_main


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in {"--ui", "ui"}:
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        raise SystemExit(ui_main())
    raise SystemExit(cli_main())
