from __future__ import annotations

from math import isfinite

from stencilforge.aperture_workspace import (
    compute_aperture_workspace,
    default_aperture_workspace,
    describe_action,
    describe_match,
    export_aperture_workspace_payload,
    import_aperture_workspace_payload,
    normalize_aperture_workspace,
)


def test_default_workspace_has_selected_rule():
    workspace = normalize_aperture_workspace({})

    assert workspace["profileName"] == "Balanced default"
    assert workspace["selectedRuleId"] == "rule_qfn"
    assert len(workspace["rules"]) >= 1


def test_workspace_metrics_are_computed():
    snapshot = compute_aperture_workspace({}, 0.12)

    assert snapshot["thicknessLabel"] == "0.12 mm"
    assert snapshot["calculatorStatus"] == "ok"
    assert snapshot["previewStatus"] == "recommended"
    assert isfinite(snapshot["recommendedVolumeMm3"])
    assert snapshot["generatedRulePreview"].startswith("match: { package:")


def test_workspace_descriptions_are_human_readable():
    workspace = default_aperture_workspace()
    rule = workspace["rules"][1]

    match_text = describe_match(rule)
    assert "QFN" in match_text
    assert "SMD" in match_text
    assert "Top" in match_text
    assert "0.20-0.60 mm" in match_text
    assert describe_action(rule) == "Delta -0.030 mm"


def test_workspace_payload_round_trip_keeps_rules():
    workspace = default_aperture_workspace()
    workspace["profileName"] = "Import / Export"
    workspace["rules"][1]["name"] = "Round trip rule"

    payload = export_aperture_workspace_payload(workspace, 0.15)

    assert payload["schemaVersion"] == 1
    assert payload["kind"] == "stencilforge.aperture_workspace"
    assert payload["workspace"]["profileName"] == "Import / Export"
    assert payload["snapshot"]["thicknessValue"] == 0.15

    imported = import_aperture_workspace_payload(payload)

    assert imported["profileName"] == "Import / Export"
    assert imported["rules"][1]["name"] == "Round trip rule"
    assert imported["selectedRuleId"] == workspace["selectedRuleId"]
