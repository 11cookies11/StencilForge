from __future__ import annotations

from copy import deepcopy
from math import isfinite, sqrt
from typing import Any

APERTURE_WORKSPACE_FORMAT = "stencilforge.aperture_workspace"
APERTURE_WORKSPACE_SCHEMA_VERSION = 1

PACKAGE_FACTOR_MAP = {
    "QFN": 0.94,
    "BGA": 0.92,
    "IC": 1.0,
    "Power": 1.04,
}

PAD_TYPE_FACTOR_MAP = {
    "SMD": 1.0,
    "Thermal": 0.96,
    "THT": 1.04,
}

STRATEGY_FACTOR_MAP = {
    "balanced": 1.0,
    "conservative": 0.95,
    "aggressive": 1.05,
}


def default_aperture_workspace() -> dict[str, Any]:
    return {
        "profileName": "Balanced default",
        "transferRatio": 0.88,
        "strategy": "balanced",
        "minApertureMm": 0.1,
        "maxApertureMm": 0.0,
        "allowAsymmetric": False,
        "padAreaMm2": 0.84,
        "padWidthMm": 0.45,
        "padHeightMm": 0.4,
        "packageType": "QFN",
        "padType": "SMD",
        "targetVolumeMm3": 0.062,
        "selectedRuleId": "rule_qfn",
        "rules": [
            {
                "id": "rule_default",
                "name": "Global fallback",
                "enabled": True,
                "priority": 0,
                "match": {"package": "Any", "padType": "Any", "layer": "Top", "padSize": "0.20-1.00 mm"},
                "action": {"mode": "delta", "deltaMm": -0.02, "scale": 0.98},
                "note": "Fallback rule for the whole library.",
            },
            {
                "id": "rule_qfn",
                "name": "QFN fine pitch",
                "enabled": True,
                "priority": 80,
                "match": {"package": "QFN", "padType": "SMD", "layer": "Top", "padSize": "0.20-0.60 mm"},
                "action": {"mode": "delta", "deltaMm": -0.03, "scale": 0.96},
                "note": "Default recommendation for dense QFN pads.",
            },
            {
                "id": "rule_power",
                "name": "Power pads",
                "enabled": False,
                "priority": 45,
                "match": {"package": "Power", "padType": "Thermal", "layer": "Top", "padSize": "1.00-3.00 mm"},
                "action": {"mode": "scale", "deltaMm": 0.0, "scale": 1.04},
                "note": "Enable when extra solder volume is preferred.",
            },
        ],
    }


def normalize_aperture_workspace(data: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = default_aperture_workspace()
    if isinstance(data, dict):
        merged.update({key: value for key, value in data.items() if key != "rules"})
        if "rules" in data:
            merged["rules"] = [normalize_rule(rule) for rule in _ensure_list(data.get("rules"))]
    merged["rules"] = [normalize_rule(rule) for rule in _ensure_list(merged.get("rules"))]
    if not merged["rules"]:
        merged["rules"] = default_aperture_workspace()["rules"]
    if merged.get("selectedRuleId") not in {rule["id"] for rule in merged["rules"]}:
        merged["selectedRuleId"] = merged["rules"][0]["id"]
    merged["transferRatio"] = _positive_float(merged.get("transferRatio"), 0.88, 0.01)
    merged["strategy"] = _coerce_strategy(merged.get("strategy"))
    merged["minApertureMm"] = _non_negative_float(merged.get("minApertureMm"), 0.1)
    merged["maxApertureMm"] = _non_negative_float(merged.get("maxApertureMm"), 0.0)
    merged["allowAsymmetric"] = bool(merged.get("allowAsymmetric", False))
    merged["padAreaMm2"] = _non_negative_float(merged.get("padAreaMm2"), 0.84)
    merged["padWidthMm"] = _positive_float(merged.get("padWidthMm"), 0.45, 0.01)
    merged["padHeightMm"] = _positive_float(merged.get("padHeightMm"), 0.4, 0.01)
    merged["packageType"] = _coerce_choice(merged.get("packageType"), {"QFN", "BGA", "IC", "Power"}, "QFN")
    merged["padType"] = _coerce_choice(merged.get("padType"), {"SMD", "Thermal", "THT"}, "SMD")
    merged["targetVolumeMm3"] = _non_negative_float(merged.get("targetVolumeMm3"), 0.062)
    return merged


def compute_aperture_workspace(data: dict[str, Any] | None, stencil_thickness_mm: float | None = None) -> dict[str, Any]:
    workspace = normalize_aperture_workspace(data)
    thickness_value = _positive_float(stencil_thickness_mm, 0.12, 0.01)
    transfer_ratio = workspace["transferRatio"]
    current_thickness_factor = thickness_value * transfer_ratio
    theoretical_volume_mm3 = workspace["padAreaMm2"] * current_thickness_factor
    package_factor = PACKAGE_FACTOR_MAP.get(workspace["packageType"], 1.0)
    pad_type_factor = PAD_TYPE_FACTOR_MAP.get(workspace["padType"], 1.0)
    strategy_factor = STRATEGY_FACTOR_MAP.get(workspace["strategy"], 1.0)
    recommended_volume_mm3 = theoretical_volume_mm3 * package_factor * pad_type_factor * strategy_factor
    effective_target_volume_mm3 = workspace["targetVolumeMm3"] if workspace["targetVolumeMm3"] > 0 else recommended_volume_mm3
    target_open_area_mm2 = (
        effective_target_volume_mm3 / current_thickness_factor if current_thickness_factor > 0 else 0.0
    )
    recommended_scale = (
        sqrt(max(0.0001, target_open_area_mm2 / workspace["padAreaMm2"]))
        if workspace["padAreaMm2"] > 0 and target_open_area_mm2 > 0
        else 1.0
    )
    recommended_delta_mm = solve_delta_for_rectangle(workspace["padWidthMm"], workspace["padHeightMm"], target_open_area_mm2)
    calculator_status = "ok"
    if not isfinite(recommended_delta_mm):
        calculator_status = "warning"
    elif workspace["minApertureMm"] > 0 and recommended_delta_mm < -abs(workspace["minApertureMm"]):
        calculator_status = "warning"
    elif workspace["maxApertureMm"] > 0 and recommended_delta_mm > workspace["maxApertureMm"]:
        calculator_status = "warning"

    active_rule = next(
        (rule for rule in workspace["rules"] if rule["id"] == workspace["selectedRuleId"]),
        workspace["rules"][0],
    )
    return {
        **workspace,
        "thicknessValue": thickness_value,
        "thicknessLabel": f"{thickness_value:.2f} mm",
        "currentThicknessFactor": current_thickness_factor,
        "theoreticalVolumeMm3": theoretical_volume_mm3,
        "recommendedVolumeMm3": recommended_volume_mm3,
        "effectiveTargetVolumeMm3": effective_target_volume_mm3,
        "targetOpenAreaMm2": target_open_area_mm2,
        "recommendedScale": recommended_scale,
        "recommendedDeltaMm": recommended_delta_mm if isfinite(recommended_delta_mm) else 0.0,
        "calculatorStatus": calculator_status,
        "previewStatus": "above" if effective_target_volume_mm3 > recommended_volume_mm3 else "recommended",
        "packageFactor": package_factor,
        "padTypeFactor": pad_type_factor,
        "strategyFactor": strategy_factor,
        "activeRule": active_rule,
        "generatedRulePreview": build_generated_rule_preview(workspace, recommended_delta_mm, recommended_scale),
        "activeRuleMatchSummary": describe_match(active_rule),
        "activeRuleActionSummary": describe_action(active_rule),
    }


def export_aperture_workspace_payload(
    data: dict[str, Any] | None,
    stencil_thickness_mm: float | None = None,
) -> dict[str, Any]:
    workspace = normalize_aperture_workspace(data)
    snapshot = compute_aperture_workspace(workspace, stencil_thickness_mm)
    return {
        "schemaVersion": APERTURE_WORKSPACE_SCHEMA_VERSION,
        "kind": APERTURE_WORKSPACE_FORMAT,
        "workspace": workspace,
        "snapshot": {
            "thicknessValue": snapshot["thicknessValue"],
            "thicknessLabel": snapshot["thicknessLabel"],
            "currentThicknessFactor": snapshot["currentThicknessFactor"],
            "theoreticalVolumeMm3": snapshot["theoreticalVolumeMm3"],
            "recommendedVolumeMm3": snapshot["recommendedVolumeMm3"],
            "effectiveTargetVolumeMm3": snapshot["effectiveTargetVolumeMm3"],
            "targetOpenAreaMm2": snapshot["targetOpenAreaMm2"],
            "recommendedScale": snapshot["recommendedScale"],
            "recommendedDeltaMm": snapshot["recommendedDeltaMm"],
            "calculatorStatus": snapshot["calculatorStatus"],
            "previewStatus": snapshot["previewStatus"],
            "packageFactor": snapshot["packageFactor"],
            "padTypeFactor": snapshot["padTypeFactor"],
            "strategyFactor": snapshot["strategyFactor"],
            "generatedRulePreview": snapshot["generatedRulePreview"],
            "activeRuleMatchSummary": snapshot["activeRuleMatchSummary"],
            "activeRuleActionSummary": snapshot["activeRuleActionSummary"],
        },
    }


def import_aperture_workspace_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return normalize_aperture_workspace(None)
    workspace = data.get("workspace")
    if isinstance(workspace, dict):
        return normalize_aperture_workspace(workspace)
    return normalize_aperture_workspace(data)


def resolve_aperture_workspace_effect(
    data: dict[str, Any] | None,
    stencil_thickness_mm: float | None = None,
) -> dict[str, Any]:
    snapshot = compute_aperture_workspace(data, stencil_thickness_mm)
    active_rule = snapshot["activeRule"] or {}
    action = active_rule.get("action") or {}
    enabled = bool(active_rule.get("enabled", True))
    mode = str(action.get("mode") or "delta")
    delta_mm = float(action.get("deltaMm", 0.0) or 0.0)
    scale = _positive_float(action.get("scale"), 1.0, 0.01)
    if not enabled:
        effect = {"enabled": False, "mode": "delta", "deltaMm": 0.0, "scale": 1.0}
    elif mode == "scale":
        effect = {"enabled": True, "mode": "scale", "deltaMm": 0.0, "scale": scale}
    else:
        effect = {"enabled": True, "mode": "delta", "deltaMm": delta_mm, "scale": 1.0}
    return {
        "snapshot": snapshot,
        "effect": effect,
        "ruleId": str(active_rule.get("id") or ""),
        "ruleName": str(active_rule.get("name") or ""),
        "matchSummary": snapshot["activeRuleMatchSummary"],
        "actionSummary": snapshot["activeRuleActionSummary"],
    }


def build_generated_rule_preview(workspace: dict[str, Any], recommended_delta_mm: float, recommended_scale: float) -> str:
    package = workspace.get("packageType", "Any")
    pad_type = workspace.get("padType", "Any")
    delta = recommended_delta_mm if isfinite(recommended_delta_mm) else 0.0
    return (
        f'match: {{ package: "{package}", padType: "{pad_type}" }}\n'
        f"action: {{ deltaMm: {delta:.3f}, scale: {recommended_scale:.3f} }}\n"
        f"priority: 100"
    )


def describe_match(rule: dict[str, Any] | None) -> str:
    if not rule:
        return ""
    match = rule.get("match") or {}
    parts: list[str] = []
    package = match.get("package")
    pad_type = match.get("padType")
    layer = match.get("layer")
    pad_size = match.get("padSize")
    if package and package != "Any":
        parts.append(str(package))
    if pad_type and pad_type != "Any":
        parts.append(str(pad_type))
    if layer and layer != "Any":
        parts.append(str(layer))
    if pad_size:
        parts.append(str(pad_size))
    return " · ".join(parts) if parts else "Any"


def describe_action(rule: dict[str, Any] | None) -> str:
    if not rule:
        return ""
    action = rule.get("action") or {}
    mode = str(action.get("mode") or "delta")
    if mode == "scale":
        scale = _positive_float(action.get("scale"), 1.0, 0.01)
        return f"Scale x {scale:.3f}"
    delta_mm = float(action.get("deltaMm", 0.0) or 0.0)
    return f"Delta {delta_mm:+.3f} mm"


def normalize_rule(rule: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "id": f"rule_{len(str(rule or {}))}",
        "name": "Untitled rule",
        "enabled": True,
        "priority": 0,
        "match": {"package": "Any", "padType": "Any", "layer": "Any", "padSize": ""},
        "action": {"mode": "delta", "deltaMm": 0.0, "scale": 1.0},
        "note": "",
    }
    if not isinstance(rule, dict):
        return base
    merged = deepcopy(base)
    merged.update({key: value for key, value in rule.items() if key not in {"match", "action"}})
    match = rule.get("match") or {}
    action = rule.get("action") or {}
    merged["match"] = {
        "package": str(match.get("package", "Any") or "Any"),
        "padType": str(match.get("padType", "Any") or "Any"),
        "layer": str(match.get("layer", "Any") or "Any"),
        "padSize": str(match.get("padSize", "") or ""),
    }
    merged["action"] = {
        "mode": _coerce_choice(action.get("mode"), {"delta", "scale"}, "delta"),
        "deltaMm": float(action.get("deltaMm", 0.0) or 0.0),
        "scale": _positive_float(action.get("scale"), 1.0, 0.01),
    }
    merged["enabled"] = bool(merged.get("enabled", True))
    merged["priority"] = int(merged.get("priority", 0) or 0)
    merged["name"] = str(merged.get("name") or "Untitled rule")
    fallback_name = str(merged["name"]).strip().lower().replace(" ", "_") or "rule"
    merged["id"] = str(merged.get("id") or f"{fallback_name}_{merged['priority']}")
    merged["note"] = str(merged.get("note") or "")
    return merged


def solve_delta_for_rectangle(width: float, height: float, target_area: float) -> float:
    w = float(width or 0.0)
    h = float(height or 0.0)
    area = float(target_area or 0.0)
    if w <= 0 or h <= 0 or area <= 0:
        return 0.0
    root = sqrt(max(0.0, (w - h) * (w - h) + 4 * area))
    return (-w - h + root) / 4


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _coerce_choice(value: Any, choices: set[str], default: str) -> str:
    text = str(value or default)
    return text if text in choices else default


def _coerce_strategy(value: Any) -> str:
    return _coerce_choice(value, set(STRATEGY_FACTOR_MAP), "balanced")


def _positive_float(value: Any, default: float, minimum: float) -> float:
    try:
        next_value = float(value)
    except (TypeError, ValueError):
        return default
    if not isfinite(next_value) or next_value <= 0:
        return default
    return max(next_value, minimum)


def _non_negative_float(value: Any, default: float) -> float:
    try:
        next_value = float(value)
    except (TypeError, ValueError):
        return default
    if not isfinite(next_value) or next_value < 0:
        return default
    return next_value
