from __future__ import annotations

from copy import deepcopy
from math import isfinite, sqrt
from typing import Any

APERTURE_WORKSPACE_FORMAT = "stencilforge.aperture_workspace"
APERTURE_WORKSPACE_SCHEMA_VERSION = 1
APERTURE_WORKSPACE_SUPPORTED_SCHEMA_VERSIONS = {1}

# Keep in sync with ui-vue/src/components/ApertureRuleWorkspace.vue
PACKAGE_FACTOR_MAP = {
    "QFN": 0.94,
    "BGA": 0.92,
    "IC": 1.0,
    "Power": 1.04,
}

PAD_TYPE_FACTOR_MAP = {
    "SMD": 1.0,
    "BGA": 0.92,
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
        "packageType": "Any",
        "padType": "SMD",
        "targetVolumeMm3": 0.062,
        "selectedRuleId": "rule_default",
        "selectedRuleGroupKey": "",
        "rules": [
            {
                "id": "rule_default",
                "name": "Global fallback",
                "enabled": True,
                "priority": 0,
                "match": {"package": "Any", "padType": "Any", "padSize": "0.20-1.00 mm"},
                "action": {"mode": "scale", "deltaMm": 0.0, "scale": 1.0},
                "note": "Neutral fallback; mask scale and global offset handle baseline shrink.",
            },
            {
                "id": "rule_qfn",
                "name": "QFN fine pitch",
                "enabled": True,
                "priority": 80,
                "match": {"package": "QFN", "padType": "SMD", "padSize": "0.20-0.60 mm"},
                "action": {"mode": "delta", "deltaMm": -0.015, "scale": 0.98},
                "note": "Default recommendation for dense QFN pads.",
            },
            {
                "id": "rule_qfn_std",
                "name": "QFN standard",
                "enabled": True,
                "priority": 70,
                "match": {"package": "QFN", "padType": "SMD", "padSize": "0.60-1.00 mm"},
                "action": {"mode": "delta", "deltaMm": -0.01, "scale": 0.99},
                "note": "Larger QFN pads with moderate reduction.",
            },
            {
                "id": "rule_bga",
                "name": "BGA",
                "enabled": True,
                "priority": 75,
                "match": {"package": "Any", "padType": "BGA", "padSize": "0.20-0.80 mm"},
                "action": {"mode": "scale", "deltaMm": 0.0, "scale": 0.96},
                "note": "BGA ball pads with conservative reduction to avoid bridging.",
            },
            {
                "id": "rule_ic",
                "name": "IC / SOIC",
                "enabled": True,
                "priority": 60,
                "match": {"package": "IC", "padType": "SMD", "padSize": "0.30-0.80 mm"},
                "action": {"mode": "delta", "deltaMm": -0.005, "scale": 0.99},
                "note": "Standard IC pads with slight reduction for fine-pitch devices.",
            },
            {
                "id": "rule_power",
                "name": "Power pads",
                "enabled": False,
                "priority": 45,
                "match": {"package": "Power", "padType": "Thermal", "padSize": "1.00-3.00 mm"},
                "action": {"mode": "scale", "deltaMm": 0.0, "scale": 1.04},
                "note": "Enable when extra solder volume is preferred.",
            },
            {
                "id": "rule_tht",
                "name": "THT",
                "enabled": True,
                "priority": 40,
                "match": {"package": "Any", "padType": "THT", "padSize": "0.60-2.00 mm"},
                "action": {"mode": "scale", "deltaMm": 0.0, "scale": 1.04},
                "note": "Through-hole pads benefit from increased aperture for barrel fill.",
            },
        ],
    }


def normalize_aperture_workspace(data: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = default_aperture_workspace()
    if isinstance(data, dict):
        merged.update(_pick_workspace_fields(data))
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
    merged["packageType"] = _coerce_choice(merged.get("packageType"), {"Any", "QFN", "BGA", "IC", "Power"}, "Any")
    merged["padType"] = _coerce_choice(merged.get("padType"), {"Any", "SMD", "BGA", "Thermal", "THT"}, "SMD")
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
    matched_rule = resolve_matching_rule(workspace)
    rule_groups = build_rule_groups(workspace, matched_rule=matched_rule, active_rule=active_rule)
    matched_rule_group = next((group for group in rule_groups if group.get("matched")), None)
    active_rule_group = next((group for group in rule_groups if group.get("active")), None)
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
        "previewStatus": _preview_status(effective_target_volume_mm3, recommended_volume_mm3),
        "packageFactor": package_factor,
        "padTypeFactor": pad_type_factor,
        "strategyFactor": strategy_factor,
        "activeRule": active_rule,
        "matchedRule": matched_rule,
        "ruleGroups": rule_groups,
        "activeRuleGroup": active_rule_group,
        "matchedRuleGroup": matched_rule_group,
        "activeRuleGroupSummary": describe_rule_group(active_rule_group),
        "matchedRuleGroupSummary": describe_rule_group(matched_rule_group),
        "generatedRulePreview": build_generated_rule_preview(workspace, recommended_delta_mm, recommended_scale),
        "activeRuleMatchSummary": describe_match(active_rule),
        "activeRuleActionSummary": describe_action(active_rule),
        "matchedRuleMatchSummary": describe_match(matched_rule),
        "matchedRuleActionSummary": describe_action(matched_rule),
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
            "ruleGroups": snapshot["ruleGroups"],
            "activeRuleGroup": snapshot["activeRuleGroup"],
            "matchedRuleGroup": snapshot["matchedRuleGroup"],
            "activeRuleGroupSummary": snapshot["activeRuleGroupSummary"],
            "matchedRuleGroupSummary": snapshot["matchedRuleGroupSummary"],
            "generatedRulePreview": snapshot["generatedRulePreview"],
            "activeRuleMatchSummary": snapshot["activeRuleMatchSummary"],
            "activeRuleActionSummary": snapshot["activeRuleActionSummary"],
            "matchedRuleMatchSummary": snapshot["matchedRuleMatchSummary"],
            "matchedRuleActionSummary": snapshot["matchedRuleActionSummary"],
        },
    }


def import_aperture_workspace_payload(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        return normalize_aperture_workspace(None)
    workspace = data.get("workspace")
    if isinstance(workspace, dict):
        return normalize_aperture_workspace(workspace)
    return normalize_aperture_workspace(data)


def validate_aperture_workspace_payload(data: Any) -> dict[str, Any]:
    issues: list[str] = []
    schema_version = None
    kind = None
    legacy = False
    workspace: dict[str, Any] | None = None
    if not isinstance(data, dict):
        issues.append("payload must be an object")
        return {
            "ok": False,
            "issues": issues,
            "schemaVersion": schema_version,
            "kind": kind,
            "legacy": legacy,
            "workspace": normalize_aperture_workspace(None),
        }

    kind = str(data.get("kind") or "")
    if kind and kind != APERTURE_WORKSPACE_FORMAT:
        issues.append(f"unsupported kind: {kind}")

    raw_schema_version = data.get("schemaVersion")
    if raw_schema_version is not None:
        try:
            schema_version = int(raw_schema_version)
        except (TypeError, ValueError):
            issues.append(f"invalid schemaVersion: {raw_schema_version!r}")
        else:
            if schema_version not in APERTURE_WORKSPACE_SUPPORTED_SCHEMA_VERSIONS:
                issues.append(f"unsupported schemaVersion: {schema_version}")

    workspace_data = data.get("workspace")
    if isinstance(workspace_data, dict):
        workspace = workspace_data
    else:
        legacy = True
        workspace = data

    normalized = normalize_aperture_workspace(workspace)
    return {
        "ok": not issues,
        "issues": issues,
        "schemaVersion": schema_version,
        "kind": kind or APERTURE_WORKSPACE_FORMAT,
        "legacy": legacy,
        "workspace": normalized,
    }


def resolve_aperture_workspace_effect(
    data: dict[str, Any] | None,
    stencil_thickness_mm: float | None = None,
) -> dict[str, Any]:
    snapshot = compute_aperture_workspace(data, stencil_thickness_mm)
    active_rule = snapshot["matchedRule"] or snapshot["activeRule"] or {}
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
        "groupSummary": snapshot["matchedRuleGroupSummary"] or snapshot["activeRuleGroupSummary"],
        "groupRuleCount": int((snapshot["matchedRuleGroup"] or snapshot["activeRuleGroup"] or {}).get("ruleCount", 0) or 0),
        "matchSummary": snapshot["matchedRuleMatchSummary"] or snapshot["activeRuleMatchSummary"],
        "actionSummary": snapshot["matchedRuleActionSummary"] or snapshot["activeRuleActionSummary"],
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
    package = _first_present(match, ("package", "packageType", "package_type"))
    pad_type = _first_present(match, ("padType", "pad_type"))
    pad_size = _first_present(match, ("padSize", "pad_size", "pad_size_mm"))
    if package and package != "Any":
        parts.append(str(package))
    if pad_type and pad_type != "Any":
        parts.append(str(pad_type))
    if pad_size:
        parts.append(str(pad_size))
    return " 路 ".join(parts) if parts else "Any"


def describe_rule_group(group: dict[str, Any] | None) -> str:
    if not isinstance(group, dict):
        return "Any"
    label = str(group.get("label") or "").strip()
    if label:
        return label
    package = _normalize_match_token(group.get("package"))
    pad_type = _normalize_match_token(group.get("padType"))
    parts: list[str] = []
    if package and package != "Any":
        parts.append(package)
    if pad_type and pad_type != "Any":
        parts.append(pad_type)
    return " / ".join(parts) if parts else "Any"



def describe_action(rule: dict[str, Any] | None) -> str:
    if not rule:
        return ""
    action = rule.get("action") or {}
    mode = str(_first_present(action, ("mode", "actionMode")) or "delta")
    if mode == "scale":
        scale = _positive_float(_first_present(action, ("scale", "scaleFactor", "scale_factor")), 1.0, 0.01)
        return f"Scale x {scale:.3f}"
    delta_mm = float(_first_present(action, ("deltaMm", "delta_mm", "delta")) or 0.0)
    return f"Delta {delta_mm:+.3f} mm"


def normalize_rule(rule: dict[str, Any] | None) -> dict[str, Any]:
    base = {
        "id": f"rule_{len(str(rule or {}))}",
        "name": "Untitled rule",
        "enabled": True,
        "priority": 0,
        "match": {"package": "Any", "padType": "Any", "padSize": ""},
        "action": {"mode": "delta", "deltaMm": 0.0, "scale": 1.0},
        "note": "",
    }
    if not isinstance(rule, dict):
        return base
    merged = deepcopy(base)
    merged.update(_pick_rule_fields(rule))
    match = rule.get("match") or {}
    action = rule.get("action") or {}
    merged["match"] = {
        "package": str(_first_present(match, ("package", "packageType", "package_type")) or "Any"),
        "padType": str(_first_present(match, ("padType", "pad_type")) or "Any"),
        "padSize": str(_first_present(match, ("padSize", "pad_size", "pad_size_mm")) or ""),
    }
    merged["action"] = {
        "mode": _coerce_choice(_first_present(action, ("mode", "actionMode")), {"delta", "scale"}, "delta"),
        "deltaMm": float(_first_present(action, ("deltaMm", "delta_mm", "delta")) or 0.0),
        "scale": _positive_float(_first_present(action, ("scale", "scaleFactor", "scale_factor")), 1.0, 0.01),
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


def _parse_pad_size(pad_size_str: str) -> tuple[float, float] | None:
    raw = (pad_size_str or "").strip()
    if not raw:
        return None
    cleaned = raw.replace("mm", "").strip()
    parts = cleaned.split("-")
    if len(parts) != 2:
        return None
    try:
        lo = float(parts[0])
        hi = float(parts[1])
    except (TypeError, ValueError):
        return None
    if not (isfinite(lo) and isfinite(hi)) or lo < 0 or hi < 0 or lo > hi:
        return None
    return (lo, hi)


def _get_pad_size_metric(pad_width_mm: float, pad_height_mm: float) -> float:
    w = float(pad_width_mm or 0.0)
    h = float(pad_height_mm or 0.0)
    if w <= 0 or h <= 0:
        return 0.0
    return min(w, h)


def _ensure_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _pick_workspace_fields(data: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "profileName": ("profileName", "profile_name"),
        "transferRatio": ("transferRatio", "transfer_ratio"),
        "strategy": ("strategy",),
        "minApertureMm": ("minApertureMm", "min_aperture_mm"),
        "maxApertureMm": ("maxApertureMm", "max_aperture_mm"),
        "allowAsymmetric": ("allowAsymmetric", "allow_asymmetric"),
        "padAreaMm2": ("padAreaMm2", "pad_area_mm2"),
        "padWidthMm": ("padWidthMm", "pad_width_mm"),
        "padHeightMm": ("padHeightMm", "pad_height_mm"),
        "packageType": ("packageType", "package_type"),
        "padType": ("padType", "pad_type"),
        "targetVolumeMm3": ("targetVolumeMm3", "target_volume_mm3"),
        "selectedRuleId": ("selectedRuleId", "selected_rule_id"),
        "selectedRuleGroupKey": ("selectedRuleGroupKey", "selected_rule_group_key"),
    }
    return _pick_fields(data, mapping)


def _pick_rule_fields(data: dict[str, Any]) -> dict[str, Any]:
    mapping = {
        "id": ("id", "rule_id"),
        "name": ("name", "rule_name"),
        "enabled": ("enabled", "is_enabled"),
        "priority": ("priority", "rank"),
        "note": ("note", "description"),
    }
    return _pick_fields(data, mapping)


def _pick_fields(data: dict[str, Any], mapping: dict[str, tuple[str, ...]]) -> dict[str, Any]:
    picked: dict[str, Any] = {}
    for canonical, aliases in mapping.items():
        for key in aliases:
            if key in data:
                picked[canonical] = data[key]
                break
    return picked


def _first_present(data: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def resolve_matching_rule(workspace: dict[str, Any]) -> dict[str, Any] | None:
    rules = _ensure_list(workspace.get("rules"))
    if not rules:
        return None
    package_type = str(workspace.get("packageType") or "Any")
    pad_type = str(workspace.get("padType") or "Any")
    pad_width = float(workspace.get("padWidthMm", 0) or 0)
    pad_height = float(workspace.get("padHeightMm", 0) or 0)
    selected_rule = next(
        (rule for rule in rules if isinstance(rule, dict) and rule.get("id") == workspace.get("selectedRuleId")),
        None,
    )
    enabled_rules = [rule for rule in rules if isinstance(rule, dict) and bool(rule.get("enabled", True))]
    candidates: list[tuple[int, int, int, dict[str, Any]]] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        if not bool(rule.get("enabled", True)):
            continue
        match = rule.get("match") or {}
        if not _rule_matches_workspace(match, package_type, pad_type, pad_width, pad_height):
            continue
        priority = int(rule.get("priority", 0) or 0)
        specificity = _match_specificity(match)
        candidates.append((priority, specificity, -index, rule))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][3]
    if isinstance(selected_rule, dict):
        return selected_rule
    if enabled_rules:
        return enabled_rules[0]
    return rules[0]


def build_rule_groups(
    workspace: dict[str, Any],
    matched_rule: dict[str, Any] | None = None,
    active_rule: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for index, rule in enumerate(_ensure_list(workspace.get("rules"))):
        if not isinstance(rule, dict):
            continue
        match = rule.get("match") or {}
        group_key = _rule_group_key(match)
        group = groups.get(group_key)
        if group is None:
            group = {
                "key": group_key,
                "label": _group_label(match),
                "package": _normalize_match_token(_first_present(match, ("package", "packageType", "package_type"))),
                "padType": _normalize_match_token(_first_present(match, ("padType", "pad_type"))),
                "ruleIds": [],
                "ruleNames": [],
                "ruleCount": 0,
                "enabledRuleCount": 0,
                "maxPriority": -10_000,
                "matched": False,
                "active": False,
                "_order": index,
            }
            groups[group_key] = group
        group["ruleIds"].append(str(rule.get("id") or ""))
        group["ruleNames"].append(str(rule.get("name") or "Untitled rule"))
        group["ruleCount"] += 1
        if bool(rule.get("enabled", True)):
            group["enabledRuleCount"] += 1
        group["maxPriority"] = max(group["maxPriority"], int(rule.get("priority", 0) or 0))
        if isinstance(matched_rule, dict) and rule.get("id") == matched_rule.get("id"):
            group["matched"] = True
        if isinstance(active_rule, dict) and rule.get("id") == active_rule.get("id"):
            group["active"] = True
    ordered_groups = sorted(
        groups.values(),
        key=lambda group: (
            0 if group.get("matched") else 1,
            0 if group.get("active") else 1,
            -int(group.get("maxPriority", 0) or 0),
            -int(group.get("enabledRuleCount", 0) or 0),
            int(group.get("_order", 0) or 0),
            str(group.get("label") or ""),
        ),
    )
    for group in ordered_groups:
        group.pop("_order", None)
    return ordered_groups


def _rule_group_key(match: dict[str, Any]) -> str:
    package = _normalize_match_token(_first_present(match, ("package", "packageType", "package_type")))
    pad_type = _normalize_match_token(_first_present(match, ("padType", "pad_type")))
    return f"{package.casefold()}::{pad_type.casefold()}"


def _group_label(match: dict[str, Any]) -> str:
    package = _normalize_match_token(_first_present(match, ("package", "packageType", "package_type")))
    pad_type = _normalize_match_token(_first_present(match, ("padType", "pad_type")))
    parts: list[str] = []
    if package and package != "Any":
        parts.append(package)
    if pad_type and pad_type != "Any":
        parts.append(pad_type)
    return " / ".join(parts) if parts else "Any"



def _rule_matches_workspace(
    match: dict[str, Any],
    package_type: str,
    pad_type: str,
    pad_width_mm: float = 0.0,
    pad_height_mm: float = 0.0,
) -> bool:
    package = _normalize_match_token(_first_present(match, ("package", "packageType", "package_type")))
    pad = _normalize_match_token(_first_present(match, ("padType", "pad_type")))
    if not (_matches_token(package, package_type) and _matches_token(pad, pad_type)):
        return False
    pad_size_str = _first_present(match, ("padSize", "pad_size", "pad_size_mm"))
    size_range = _parse_pad_size(str(pad_size_str) if pad_size_str is not None else "")
    if size_range is None:
        return True
    lo, hi = size_range
    pad_metric = _get_pad_size_metric(pad_width_mm, pad_height_mm)
    return lo <= pad_metric <= hi


def _match_specificity(match: dict[str, Any]) -> int:
    score = 0
    if _normalize_match_token(_first_present(match, ("package", "packageType", "package_type"))).casefold() != "any":
        score += 1
    if _normalize_match_token(_first_present(match, ("padType", "pad_type"))).casefold() != "any":
        score += 1
    pad_size = str(_first_present(match, ("padSize", "pad_size", "pad_size_mm")) or "")
    if pad_size.strip():
        score += 1
    return score


def _normalize_match_token(value: Any) -> str:
    token = str(value or "Any").strip()
    return token or "Any"


def _preview_status(effective_target_volume_mm3: float, recommended_volume_mm3: float) -> str:
    if effective_target_volume_mm3 > recommended_volume_mm3 * 1.005:
        return "above"
    if effective_target_volume_mm3 < recommended_volume_mm3 * 0.995:
        return "below"
    return "recommended"


def _matches_token(rule_value: str, workspace_value: str) -> bool:
    if rule_value.casefold() == "any":
        return True
    return rule_value.casefold() == workspace_value.casefold()


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
