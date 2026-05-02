from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES_DIR = ROOT / "tests" / "fixtures" / "gerber"
EXPECT_JSON_PATH = FIXTURES_DIR / "expect.json"


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests as full pipeline integration tests (slow)",
    )


def _find_gerber_zip(case_name: str) -> Path | None:
    case_dir = FIXTURES_DIR / case_name / "input"
    if not case_dir.is_dir():
        return None
    zips = sorted(case_dir.glob("*.zip"))
    return zips[0] if zips else None


@pytest.fixture
def gerber_fixture(tmp_path: Path, request) -> Path:
    """Extract a Gerber fixture ZIP to a temp directory.

    Usage via indirect parametrize:
        @pytest.mark.parametrize("gerber_fixture", ["case_001_basic"], indirect=True)
    """
    case_name: str = request.param
    zip_path = _find_gerber_zip(case_name)
    if zip_path is None:
        pytest.skip(f"No ZIP fixture found for {case_name}")
    extract_dir = tmp_path / "gerber"
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    return extract_dir


@pytest.fixture
def expect_metrics() -> dict:
    """Load expected output metrics from expect.json, or empty dict if missing."""
    if EXPECT_JSON_PATH.exists():
        return json.loads(EXPECT_JSON_PATH.read_text(encoding="utf-8"))
    return {}
