from __future__ import annotations

import json
import re
from pathlib import Path


PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z0-9_]+\}")
LOCALES_DIR = Path(__file__).resolve().parents[2] / "ui-vue" / "src" / "i18n" / "locales"


def _placeholders(message: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(message))


def test_frontend_locale_files_have_consistent_keys_and_placeholders() -> None:
    locale_files = sorted(LOCALES_DIR.glob("*.json"))
    assert locale_files, "No frontend locale files found"

    payloads = {path.stem: json.loads(path.read_text(encoding="utf-8")) for path in locale_files}
    baseline = payloads["en"]
    baseline_keys = set(baseline.keys())

    for locale, messages in payloads.items():
        assert set(messages.keys()) == baseline_keys, f"Locale key mismatch: {locale}"
        for key in baseline_keys:
            assert _placeholders(messages[key]) == _placeholders(
                baseline[key]
            ), f"Placeholder mismatch: {locale}:{key}"
