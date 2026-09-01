from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any


_OBSERVABLE = {"directly_observed", "strongly_supported"}
_CORE_CLASSES = {"game_rule", "gameplay_parameter"}
_PUBLISHABLE_REQUIREMENT_RULE_STATUSES = {"approved_review", "evidence_derived_valid", "existing_valid"}


def attach_approved_requirement_rules(
        synthesis_report: dict[str, Any],
        requirement_rules: list[dict[str, Any]],
        *,
        owner_by_mechanic: dict[str, dict[str, str]],
) -> dict[str, Any]:
    """Publish already-valid Requirement Rules without re-inferring their content.

    Owner selection and provenance are supplied as structured inputs.  Missing owner
    mappings are deliberately non-publishable: this bridge never guesses from text.
    """
    result = deepcopy(synthesis_report)
    game_rules = result.setdefault("gameRules", [])
    superseded = {
        syn_id for rule in requirement_rules
        if rule.get("valid") and rule.get("ruleStatus") in _PUBLISHABLE_REQUIREMENT_RULE_STATUSES
        for syn_id in rule.get("supersedesSynthesisRuleIds", [])
    }
    if superseded:
        game_rules[:] = [item for item in game_rules if item.get("ruleId") not in superseded]
    existing_rule_ids = {
        source_rule_id
        for item in game_rules
        for source_rule_id in item.get("sourceRuleIds", [])
    }
    for rule in requirement_rules:
        source_rule_id = rule.get("ruleId")
        owner_path = rule.get("planningOwnerPath", [])
        owner = ({
            "ownerChapter": owner_path[0],
            "ruleGroup": " / ".join(owner_path[1:]),
        } if owner_path else owner_by_mechanic.get(rule.get("mechanicId", "")))
        if (
            not rule.get("valid")
            or rule.get("ruleStatus") not in _PUBLISHABLE_REQUIREMENT_RULE_STATUSES
            or not source_rule_id
            or source_rule_id in existing_rule_ids
            or not owner
            or not owner.get("ownerChapter")
            or not owner.get("ruleGroup")
        ):
            continue
        game_rules.append({
            "ruleId": f"SYN-REQ-{source_rule_id.removeprefix('RULE-')}",
            "ownerChapter": owner["ownerChapter"],
            "ruleGroup": owner["ruleGroup"],
            "planningOwnerPath": list(owner_path),
            "statement": rule["text"],
            "classification": "game_rule",
            "sourceDimensions": list(rule.get("dimensionIds", [])),
            "sourceObservationTexts": [],
            "evidenceRefs": list(rule.get("evidenceRefs", [])),
            "evidenceStatus": rule.get("sourceType", "approved_review"),
            "concreteSubrules": [],
            "ruleRelations": [],
            "sourceLineIds": [],
            "sourceRuleIds": [source_rule_id],
            "sourceRequirementIds": list(dict.fromkeys(
                rule.get("satisfiesRequirementIds", []) + rule.get("originRequirementIds", [])
            )),
            "supersedesSynthesisRuleIds": list(rule.get("supersedesSynthesisRuleIds", [])),
            "approvalStatus": "approved",
        })
        existing_rule_ids.add(source_rule_id)
    result.setdefault("metrics", {})["meaningfulGameRules"] = len(game_rules)
    return result


def normalize_ui_evidence(observation: dict[str, Any]) -> dict[str, Any]:
    """Translate visible UI state into a bounded mechanic interpretation.

    A UI value may prove a current state. Lifecycle semantics are accepted only when
    the visible label says so explicitly (for example, 今日).
    """
    semantic = observation.get("uiSemantic", {})
    label = str(semantic.get("label", ""))
    value = str(semantic.get("value", ""))
    dimension = observation.get("observationDimension", "")
    result = {
        "observationDimension": dimension,
        "currentObservedState": observation.get("observedText", ""),
        "underlyingMechanic": None,
        "ruleDimension": None,
        "persistentRule": None,
        "unresolvedSemantic": [],
        "lifecycle": None,
        "evidenceRefs": observation.get("evidenceRefs", []),
    }
    if dimension == "refresh_ad_path" or "观看次数" in label:
        result.update({
            "underlyingMechanic": "ad_refresh_limit",
            "ruleDimension": "refresh_availability",
            "persistentRule": "广告刷新存在次数限制",
            "unresolvedSemantic": ["reset_period", "scope"],
        })
        return result
    if dimension == "settlement_daily_count" or "今日" in label:
        total = value.split("/")[-1] if "/" in value else value
        result.update({
            "underlyingMechanic": "daily_challenge_limit",
            "ruleDimension": "daily_attempt_limit",
            "persistentRule": f"每日挑战次数上限为{total}次",
            "unresolvedSemantic": [],
            "lifecycle": "daily",
        })
        return result
    if dimension == "weapon_slot_visible_count":
        result.update({"underlyingMechanic": "weapon_slot_capacity", "ruleDimension": "capacity",
                       "persistentRule": "战斗中提供6个武器栏位", "unresolvedSemantic": []})
    elif dimension == "hud_elapsed_time":
        result.update({"underlyingMechanic": "run_elapsed_time", "ruleDimension": "elapsed_time_tracking",
                       "persistentRule": "关卡记录本局经过时间", "unresolvedSemantic": []})
    elif dimension == "level_progress_bar":
        result.update({"underlyingMechanic": "battle_level_progress", "ruleDimension": "progress_state",
                       "persistentRule": "关卡内存在独立战斗等级和升级进度", "unresolvedSemantic": ["progress_source", "upgrade_threshold"]})
    return result


def _dedupe_evidence(observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in observations:
        for ref in item.get("evidenceRefs", []):
            key = (ref.get("evidenceId", ""), ref.get("sourcePath", ""))
            if key not in seen:
                seen.add(key)
                result.append(ref)
    return result


def synthesize_game_rules(observations: list[dict[str, Any]],
                          synthesis_plans: list[dict[str, Any]]) -> dict[str, Any]:
    by_dimension = {item["observationDimension"]: item for item in observations}
    rules: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    used_dimensions: set[str] = set()
    for plan in synthesis_plans:
        dimensions = plan.get("sourceDimensions", [])
        sources = [by_dimension.get(item) for item in dimensions]
        if not dimensions or any(item is None for item in sources):
            rejected.append({**plan, "reason": "missing_source_dimension"})
            continue
        if any(item.get("observationStatus") not in _OBSERVABLE for item in sources if item):
            rejected.append({**plan, "reason": "source_not_observable"})
            continue
        used_dimensions.update(dimensions)
        compiled = {
            "ruleId": plan["ruleId"],
            "ownerChapter": plan["ownerChapter"],
            "ruleGroup": plan["ruleGroup"],
            "statement": plan["statement"],
            "classification": plan["classification"],
            "sourceDimensions": dimensions,
            "sourceObservationTexts": [item.get("observedText", "") for item in sources if item],
            "evidenceRefs": _dedupe_evidence([item for item in sources if item]),
            "evidenceStatus": "directly_observed" if all(item.get("observationStatus") == "directly_observed" for item in sources if item) else "strongly_supported",
            "concreteSubrules": plan.get("concreteSubrules", []),
            "ruleRelations": plan.get("ruleRelations", []),
            "sourceLineIds": list(plan.get("sourceLineIds", [])),
            "approvalStatus": "candidate_only",
        }
        if plan["classification"] in _CORE_CLASSES:
            rules.append(compiled)
        else:
            filtered.append(compiled)
    return {
        "gameRules": rules,
        "filteredOut": filtered,
        "rejectedPlans": rejected,
        "metrics": {
            "meaningfulGameRules": len(rules),
            "meaningfulRuleRelations": sum(len(item["ruleRelations"]) for item in rules),
            "concreteSubrules": sum(len(item["concreteSubrules"]) for item in rules),
            "numericEffects": sum(any(char.isdigit() for char in sub) for item in rules for sub in item["concreteSubrules"]),
            "constraintsOrTradeoffs": sum("-" in sub or "限制" in sub or "上限" in sub for item in rules for sub in item["concreteSubrules"]),
            "crossSystemRules": sum(bool(item["ruleRelations"]) for item in rules),
            "filteredInteractionPresentation": len(filtered),
            "usedObservableDimensions": len(used_dimensions),
        },
    }


def render_human_planning_preview(synthesis_report: dict[str, Any],
                                  pending_lines: list[dict[str, Any]]) -> str:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for rule in synthesis_report.get("gameRules", []):
        grouped[rule["ownerChapter"]][rule["ruleGroup"]].append(rule)
    pending_by_chapter: dict[str, list[str]] = defaultdict(list)
    for item in pending_lines:
        pending_by_chapter[item["ownerChapter"]].append(item["text"])
    order = ["载具", "武器", "词条", "三选一", "怪物", "关卡", "结算"]
    titles = [item for item in order if item in grouped or item in pending_by_chapter]
    titles += [item for item in grouped if item not in titles]
    lines = ["# Human Planning Preview", ""]
    for chapter in titles:
        lines.extend([f"## {chapter}", ""])
        groups = grouped.get(chapter, {})
        for group, rules in groups.items():
            if len(lines) > 1 and lines[-1] != "":
                lines.append("")
            if len(groups) > 1:
                lines.extend([f"### {group}", ""])
            for rule in rules:
                lines.append(f"- {rule['statement']}")
                for subrule in rule.get("concreteSubrules", []):
                    lines.append(f"  - {subrule}")
        for text in pending_by_chapter.get(chapter, []):
            lines.append(f"- {text}")
        lines.append("")
    return "\n".join(lines)
