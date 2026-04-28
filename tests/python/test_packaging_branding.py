from __future__ import annotations

import json
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_branding_config_contains_required_fields() -> None:
    branding_path = _repo_root() / "packaging" / "branding.json"
    data = json.loads(branding_path.read_text(encoding="utf-8"))

    assert data["app_name"] == "StencilForge"
    assert data["app_description"] == "PCB stencil and fixture generator"
    assert data["publisher_display_name"] == "StencilForge"
    assert data["msix_identity_name"] == "AD7477BB.StencilForge"
    assert data["msix_identity_publisher"] == "CN=7FE71472-71A6-4A5E-8C37-0123AD823583"


def test_msix_manifest_uses_branding_placeholders() -> None:
    manifest_path = _repo_root() / "packaging" / "msix" / "AppxManifest.xml"
    manifest = manifest_path.read_text(encoding="utf-8")

    assert "__APP_NAME__" in manifest
    assert "__APP_DESCRIPTION__" in manifest
    assert "__PUBLISHER_DISPLAY_NAME__" in manifest
    assert "__IDENTITY_NAME__" in manifest
    assert "__IDENTITY_PUBLISHER__" in manifest
