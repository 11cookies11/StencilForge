from __future__ import annotations

import re

from stencilforge.i18n import _MESSAGES, normalize_locale, text


PLACEHOLDER_RE = re.compile(r"\{[a-zA-Z0-9_]+\}")


def _placeholders(message: str) -> set[str]:
    return set(PLACEHOLDER_RE.findall(message))


def test_normalize_locale_aliases() -> None:
    assert normalize_locale("en-US") == "en"
    assert normalize_locale("ja-JP") == "ja"
    assert normalize_locale("de-DE") == "de"
    assert normalize_locale("es-ES") == "es"
    assert normalize_locale("zh-CN") == "zh-CN"
    assert normalize_locale("fr-FR") == "zh-CN"


def test_backend_i18n_keys_and_placeholders_are_consistent() -> None:
    baseline = _MESSAGES["en"]
    baseline_keys = set(baseline.keys())

    for locale, messages in _MESSAGES.items():
        assert set(messages.keys()) == baseline_keys, f"Locale key mismatch: {locale}"
        for key in baseline_keys:
            assert _placeholders(messages[key]) == _placeholders(
                baseline[key]
            ), f"Placeholder mismatch: {locale}:{key}"


def test_text_fallback_and_formatting() -> None:
    assert text("de-DE", "dialog.error_title") == "Job fehlgeschlagen"
    assert text("fr-FR", "dialog.error_title") == "运行失败"
    assert text("es", "dialog.error_detail", message="boom") == "Error: boom"
