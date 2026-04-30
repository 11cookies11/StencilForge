from __future__ import annotations

from math import isfinite

from stencilforge.aperture_workspace import (
    compute_aperture_workspace,
    default_aperture_workspace,
    describe_action,
    describe_match,
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

    assert describe_match(rule) == "QFN • SMD • Top • 0.20-0.60 mm"
    assert describe_action(rule) == "Delta -0.030 mm"
