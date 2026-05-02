from __future__ import annotations

from math import isfinite

from stencilforge.aperture_workspace import (
    _get_pad_size_metric,
    _match_specificity,
    _parse_pad_size,
    _rule_matches_workspace,
    compute_aperture_workspace,
    default_aperture_workspace,
    describe_action,
    describe_match,
    export_aperture_workspace_payload,
    import_aperture_workspace_payload,
    normalize_aperture_workspace,
    resolve_aperture_workspace_effect,
    validate_aperture_workspace_payload,
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
    assert snapshot["matchedRuleGroupSummary"] == "QFN / SMD"
    assert len(snapshot["ruleGroups"]) == 3


def test_workspace_rule_groups_are_usable_for_filtering():
    snapshot = compute_aperture_workspace(default_aperture_workspace(), 0.12)
    group_map = {group["key"]: group for group in snapshot["ruleGroups"]}

    assert group_map["qfn::smd"]["label"] == "QFN / SMD"
    assert group_map["qfn::smd"]["ruleCount"] == 1
    assert group_map["qfn::smd"]["enabledRuleCount"] == 1
    assert group_map["any::any"]["ruleCount"] == 1


def test_workspace_descriptions_are_human_readable():
    workspace = default_aperture_workspace()
    rule = workspace["rules"][1]

    match_text = describe_match(rule)
    assert "QFN" in match_text
    assert "SMD" in match_text
    assert "Top" not in match_text
    assert "0.20-0.60 mm" in match_text
    assert describe_action(rule) == "Delta -0.030 mm"


def test_workspace_effect_prefers_package_and_pad_type_match():
    workspace = default_aperture_workspace()
    workspace["selectedRuleId"] = "rule_default"
    workspace["packageType"] = "QFN"
    workspace["padType"] = "SMD"

    effect = resolve_aperture_workspace_effect(workspace, 0.15)

    assert effect["ruleId"] == "rule_qfn"
    assert effect["ruleName"] == "QFN fine pitch"
    assert effect["groupSummary"] == "QFN / SMD"
    assert effect["matchSummary"].startswith("QFN")
    assert effect["effect"]["mode"] == "delta"
    assert effect["effect"]["deltaMm"] == -0.03


def test_workspace_payload_round_trip_keeps_rules():
    workspace = default_aperture_workspace()
    workspace["profileName"] = "Import / Export"
    workspace["rules"][1]["name"] = "Round trip rule"
    workspace["selectedRuleGroupKey"] = "qfn::smd"

    payload = export_aperture_workspace_payload(workspace, 0.15)

    assert payload["schemaVersion"] == 1
    assert payload["kind"] == "stencilforge.aperture_workspace"
    assert payload["workspace"]["profileName"] == "Import / Export"
    assert payload["workspace"]["selectedRuleGroupKey"] == "qfn::smd"
    assert payload["snapshot"]["thicknessValue"] == 0.15
    assert payload["snapshot"]["matchedRuleGroupSummary"] == "QFN / SMD"

    imported = import_aperture_workspace_payload(payload)

    assert imported["profileName"] == "Import / Export"
    assert imported["rules"][1]["name"] == "Round trip rule"
    assert imported["selectedRuleId"] == workspace["selectedRuleId"]
    assert imported["selectedRuleGroupKey"] == "qfn::smd"


def test_workspace_payload_accepts_legacy_field_aliases():
    payload = {
        "kind": "stencilforge.aperture_workspace",
        "schemaVersion": 1,
        "workspace": {
            "profile_name": "Legacy profile",
            "transfer_ratio": 0.91,
            "selected_rule_id": "rule_legacy",
            "rules": [
                {
                    "rule_id": "rule_legacy",
                    "rule_name": "Legacy rule",
                    "is_enabled": True,
                    "rank": 12,
                    "match": {
                        "package_type": "QFN",
                        "pad_type": "SMD",
                        "layer": "Top",
                        "pad_size_mm": "0.30-0.60 mm",
                    },
                    "action": {
                        "actionMode": "scale",
                        "scale_factor": 0.97,
                        "delta_mm": -0.04,
                    },
                    "description": "Legacy note",
                    "unexpected": "ignored",
                }
            ],
        },
    }

    validation = validate_aperture_workspace_payload(payload)
    workspace = validation["workspace"]

    assert validation["ok"] is True
    assert workspace["profileName"] == "Legacy profile"
    assert workspace["transferRatio"] == 0.91
    assert workspace["selectedRuleId"] == "rule_legacy"
    assert workspace["rules"][0]["id"] == "rule_legacy"
    assert workspace["rules"][0]["name"] == "Legacy rule"
    assert workspace["rules"][0]["priority"] == 12
    assert workspace["rules"][0]["match"]["package"] == "QFN"
    assert workspace["rules"][0]["match"]["padType"] == "SMD"
    assert "layer" not in workspace["rules"][0]["match"]
    assert workspace["rules"][0]["action"]["mode"] == "scale"
    assert workspace["rules"][0]["action"]["scale"] == 0.97


def test_workspace_payload_rejects_unsupported_schema_version():
    validation = validate_aperture_workspace_payload(
        {
            "kind": "stencilforge.aperture_workspace",
            "schemaVersion": 99,
            "workspace": default_aperture_workspace(),
        }
    )

    assert validation["ok"] is False
    assert any("unsupported schemaVersion" in issue for issue in validation["issues"])


def test_pad_size_parses_correctly():
    assert _parse_pad_size("0.20-0.60 mm") == (0.20, 0.60)
    assert _parse_pad_size("") is None
    assert _parse_pad_size("0.20-1.00 mm") == (0.20, 1.00)
    assert _parse_pad_size(None) is None
    assert _parse_pad_size("invalid") is None


def test_pad_size_metric_uses_min_dimension():
    assert _get_pad_size_metric(0.45, 0.4) == 0.4
    assert _get_pad_size_metric(0.5, 0.5) == 0.5
    assert _get_pad_size_metric(0, 0.4) == 0.0


def test_pad_size_matching_empty_matches_any():
    match = {"package": "Any", "padType": "Any", "padSize": ""}
    assert _rule_matches_workspace(match, "QFN", "SMD", 0.45, 0.4)


def test_pad_size_matching_in_range_succeeds():
    match = {"package": "QFN", "padType": "SMD", "padSize": "0.20-0.60 mm"}
    assert _rule_matches_workspace(match, "QFN", "SMD", 0.45, 0.4)


def test_pad_size_matching_out_of_range_fails():
    match = {"package": "QFN", "padType": "SMD", "padSize": "0.20-0.30 mm"}
    assert not _rule_matches_workspace(match, "QFN", "SMD", 0.45, 0.4)


def test_pad_size_contributes_to_specificity():
    assert _match_specificity({"package": "Any", "padType": "Any", "padSize": ""}) == 0
    assert _match_specificity({"package": "QFN", "padType": "Any", "padSize": ""}) == 1
    assert _match_specificity({"package": "QFN", "padType": "SMD", "padSize": ""}) == 2
    assert _match_specificity({"package": "QFN", "padType": "SMD", "padSize": "0.20-0.60 mm"}) == 3


def test_pad_size_breaks_tie_in_matching():
    workspace = default_aperture_workspace()
    workspace["packageType"] = "QFN"
    workspace["padType"] = "SMD"
    workspace["padWidthMm"] = 0.45
    workspace["padHeightMm"] = 0.4
    workspace["rules"] = [
        {
            "id": "rule_fine", "name": "Fine pitch", "enabled": True, "priority": 80,
            "match": {"package": "QFN", "padType": "SMD", "padSize": "0.20-0.60 mm"},
            "action": {"mode": "delta", "deltaMm": -0.03, "scale": 0.96},
        },
        {
            "id": "rule_standard", "name": "Standard", "enabled": True, "priority": 80,
            "match": {"package": "QFN", "padType": "SMD", "padSize": "0.60-1.00 mm"},
            "action": {"mode": "delta", "deltaMm": -0.02, "scale": 0.97},
        },
    ]
    effect = resolve_aperture_workspace_effect(workspace, 0.15)
    assert effect["ruleId"] == "rule_fine"
