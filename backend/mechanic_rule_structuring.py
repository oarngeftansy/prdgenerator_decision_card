from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from backend.mechanic_requirement_discovery import discover_requirements


_INTERNAL_VOCABULARY = (
    "atomic_rule", "composite_rule", "mechanic_rule", "semantic contract",
    "evidence", "relation type",
)


def build_mechanic_requirement_registry(
    mechanics: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> dict[str, Any]:
    """Discover execution requirements without making them publishable rules."""
    requirements = discover_requirements(mechanics, rules=rules)
    return {
        "requirements": requirements,
        "publicationEligible": False,
        "resolvedCount": sum(item["status"] == "resolved" for item in requirements),
        "probeCount": sum(item["status"] == "evidence_probe" for item in requirements),
        "reviewCount": sum(item["status"] == "review_required" for item in requirements),
        "dormantCount": sum(item["status"] == "dormant_optional" for item in requirements),
    }

def _rule_ids(contract: dict[str, Any]) -> list[str]:
    return [item["ruleId"] for item in contract.get("confirmedCoreRule", []) if item.get("ruleId")]


def _item(contract: dict[str, Any], dimension: dict[str, Any], text: str | None = None,
          *, synthesis_level: str | None = None) -> dict[str, Any]:
    status = dimension.get("status")
    if text is None:
        text = (dimension.get("displayText") if status == "observed"
                else f"{dimension.get('label', dimension['dimensionId'])}：待确认。")
    level = synthesis_level or ("composite_rule" if dimension.get("subrules") else "atomic_rule")
    relations = [
        {"type": dimension.get("relationType", "sequence"), "targetDimensionId": target}
        for target in dimension.get("precedes", [])
    ] + [
        {"type": "dependency", "sourceDimensionId": source}
        for source in dimension.get("dependsOn", [])
    ]
    return {
        "text": text,
        "itemType": "pending" if status == "unresolved" else (
            "parameter" if dimension.get("kind") == "parameter" else "coreRule"),
        "synthesisLevel": level,
        "supportingRuleIds": _rule_ids(contract),
        "sourceDimensionIds": [dimension["dimensionId"]],
        "semanticType": dimension.get("semanticType"),
        "subrules": list(dimension.get("subrules", [])),
        "relations": relations,
    }


def _worthiness(item: dict[str, Any]) -> tuple[str, str]:
    text = item["text"]
    dimension_ids = set(item["sourceDimensionIds"])
    if item["itemType"] == "pending":
        return "retain_meaningful", "actionable_review_dimension"
    if item["itemType"] == "parameter" or re.search(r"\d", text):
        return "retain_meaningful", "defines_numeric_or_quantified_rule"
    if dimension_ids & {"failure_condition", "success_condition", "success_result", "level_up_result"}:
        return "retain_meaningful", "defines_gameplay_outcome_or_transition"
    if "contact_damage" in dimension_ids:
        return "retain_meaningful", "defines_attack_trigger_and_cross_entity_effect"
    if dimension_ids & {"selection_result", "refresh_action", "pool_entry", "elapsed_time"}:
        return "retain_meaningful", "defines_system_transition_or_cross_system_relation"
    if "damage_reduces_health" in dimension_ids and not any(
        token in text for token in ("护盾", "减伤", "无敌", "倍率", "转移", "失败", "每")
    ):
        return "suppress_common_sense", "default_damage_semantics_without_special_rule"
    generic_patterns = (
        ("没有目标时不攻击", "default_no_target_behavior"),
        ("输入停止后停止", "default_input_release_behavior"),
        ("点击刷新后刷新内容", "default_refresh_semantics"),
        ("按钮点击后触发其对应功能", "default_button_semantics"),
    )
    for phrase, reason in generic_patterns:
        if phrase in text:
            return "suppress_common_sense", reason
    return "retain_meaningful", "project_specific_confirmed_rule"


def _apply_worthiness(chapters: list[dict[str, Any]]) -> dict[str, Any]:
    suppressed: list[dict[str, Any]] = []
    retained: list[dict[str, Any]] = []
    for chapter in chapters:
        for group in chapter["ruleGroups"]:
            for container in [group, *group["subgroups"]]:
                for item in container["items"]:
                    worthiness, reason = _worthiness(item)
                    item["publishWorthiness"] = worthiness
                    item["worthinessReason"] = reason
                    item["subrulePublishWorthiness"] = ["retain_meaningful"] * len(item["subrules"])
                    audit_item = {
                        "chapter": chapter["title"], "ruleGroup": group["title"],
                        "text": item["text"], "supportingRuleIds": item["supportingRuleIds"],
                        "sourceDimensionIds": item["sourceDimensionIds"], "reason": reason,
                    }
                    (suppressed if worthiness == "suppress_common_sense" else retained).append(audit_item)
    return {"suppressedCommonSenseRules": suppressed,
            "retainedBasicButMeaningfulRules": retained}


def _subgroup(title: str, contract: dict[str, Any], items: list[dict[str, Any]]) -> dict[str, Any]:
    dimension_ids = sorted({dimension_id for item in items for dimension_id in item["sourceDimensionIds"]})
    return {
        "title": title,
        "items": items,
        "supportingRuleIds": _rule_ids(contract),
        "sourceDimensionIds": dimension_ids,
        "structureBasis": "shared confirmed mechanic semantic",
    }


def _dimensions(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["dimensionId"]: item for item in contract.get("requiredRuleDimensions", [])}


def _structured_subgroups(contract: dict[str, Any]) -> tuple[list[dict[str, Any]], set[str]]:
    """Return evidence-backed reading groups; every node consumes existing dimensions."""
    dims = _dimensions(contract)
    semantic_id = contract["ruleSemanticId"]
    groups: list[dict[str, Any]] = []
    consumed: set[str] = set()

    def add(title: str, ids: list[str], *, allow_single: bool = False) -> None:
        present = [dimension_id for dimension_id in ids if dimension_id in dims]
        # A subheading must organize at least two pieces of information. A
        # dimension with concrete subrules also qualifies because it already
        # contains a supported rule family rather than a lone bullet.
        items = [_item(contract, dims[dimension_id]) for dimension_id in present]
        information_count = sum(1 + len(item["subrules"]) for item in items)
        if present and (information_count >= 2 or allow_single):
            groups.append(_subgroup(title, contract, items))
            consumed.update(present)

    if semantic_id == "RSC-WEAPON-ATTACK":
        add("自动攻击", ["targeting", "attack_range", "attack_interval"])
        add("攻击方式", ["attack_method"])
        add("伤害结算", ["damage_model"], allow_single=True)
    elif semantic_id == "RSC-AFFIX":
        modifier = dims.get("modifier_dimensions")
        tradeoff = dims.get("tradeoff")
        if modifier:
            numeric = [text for text in modifier.get("subrules", [])
                       if not any(token in text for token in ("四向", "方向", "改为"))]
            morphology = [text for text in modifier.get("subrules", [])
                          if any(token in text for token in ("四向", "方向", "改为"))]
            if numeric:
                groups.append(_subgroup("数值强化", contract, [
                    {**_item(contract, modifier, "词条可修改武器的攻击范围、伤害、冷却和攻击次数。",
                             synthesis_level="composite_rule"), "subrules": numeric}
                ]))
            if morphology:
                groups.append(_subgroup("攻击形态", contract, [
                    {**_item(contract, modifier, "部分词条会改变武器的攻击方向或攻击方式。",
                             synthesis_level="composite_rule"), "subrules": morphology}
                ]))
            consumed.add("modifier_dimensions")
        if tradeoff:
            groups.append(_subgroup("复合效果", contract, [_item(contract, tradeoff)]))
            consumed.add("tradeoff")
    elif semantic_id == "RSC-THREE-CHOICE":
        add("触发", ["trigger_pause"], allow_single=True)
        add("候选", ["candidate_eligibility"], allow_single=True)
        add("选择结果", ["selection_result"], allow_single=True)
    elif semantic_id == "RSC-AD-REFRESH":
        add("刷新规则", ["refresh_action", "limit_exists", "refresh_max_count", "refresh_reset_scope"])
    elif semantic_id == "RSC-MONSTER":
        add("出现与移动", ["spawn_movement"], allow_single=True)
        add("接触伤害", ["contact_damage"], allow_single=True)
    elif semantic_id == "RSC-BATTLE-LEVEL":
        add("成长规则", ["level_progress", "growth_source", "upgrade_rule"])
        add("升级结果", ["level_up_result"], allow_single=True)
    elif semantic_id == "RSC-SETTLEMENT":
        add("战斗结果", ["clear_time_record"], allow_single=True)
        add("伤害统计", ["damage_statistics"], allow_single=True)
        add("奖励", ["reward_items", "double_reward"])
        add("挑战次数", ["daily_reset_scope", "daily_max_count"])
    return groups, consumed


def build_mechanic_rule_hierarchy(contracts: list[dict[str, Any]],
                                  gated_rules: list[dict[str, Any]]) -> dict[str, Any]:
    del gated_rules  # Reserved for cross-artifact consistency checks; contracts own rendering facts.
    chapters: list[dict[str, Any]] = []
    chapter_index: dict[str, dict[str, Any]] = {}
    for contract in contracts:
        chapter_name = contract["ownerChapter"]
        chapter = chapter_index.get(chapter_name)
        if chapter is None:
            chapter = {"title": chapter_name, "ruleGroups": []}
            chapter_index[chapter_name] = chapter
            chapters.append(chapter)
        dimensions = contract.get("requiredRuleDimensions", [])
        subgroups, consumed = _structured_subgroups(contract)
        items = [_item(contract, dimension) for dimension in dimensions
                 if dimension["dimensionId"] not in consumed]
        information_count = sum(1 + len(item["subrules"]) for item in items)
        synthesis_level = "mechanic_rule" if subgroups or information_count >= 3 else (
            "composite_rule" if information_count >= 2 else "atomic_rule")
        chapter["ruleGroups"].append({
            "groupId": contract["ruleSemanticId"],
            "title": contract["ruleGroup"],
            "mechanic": contract["mechanic"],
            "synthesisLevel": synthesis_level,
            "items": items,
            "subgroups": subgroups,
            "supportingRuleIds": _rule_ids(contract),
            "sourceDimensionIds": [item["dimensionId"] for item in dimensions],
        })

    hierarchy_nodes = [group for chapter in chapters for group in chapter["ruleGroups"]]
    subgroup_nodes = [group for node in hierarchy_nodes for group in node["subgroups"]]
    unsupported = sum(not node["supportingRuleIds"] or not node["sourceDimensionIds"]
                      for node in hierarchy_nodes + subgroup_nodes)
    metrics = {
        "mechanicRuleCount": sum(group["synthesisLevel"] == "mechanic_rule" for group in hierarchy_nodes),
        "compositeRuleCount": sum(
            item["synthesisLevel"] == "composite_rule"
            for group in hierarchy_nodes for item in group["items"]
        ) + sum(item["synthesisLevel"] == "composite_rule"
                for subgroup in subgroup_nodes for item in subgroup["items"]),
        "concreteSubruleCount": sum(len(item["subrules"])
                                    for group in hierarchy_nodes for item in group["items"])
        + sum(len(item["subrules"]) for subgroup in subgroup_nodes for item in subgroup["items"]),
        "gameplayParameterCount": sum(
            item["itemType"] == "parameter" for group in hierarchy_nodes for item in group["items"]
        ) + sum(item["itemType"] == "parameter" for subgroup in subgroup_nodes for item in subgroup["items"]),
        "constraintTradeoffCount": sum(
            "tradeoff" in item["sourceDimensionIds"] for group in hierarchy_nodes for item in group["items"]
        ) + sum("tradeoff" in item["sourceDimensionIds"]
                for subgroup in subgroup_nodes for item in subgroup["items"]),
        "crossSystemRelationCount": sum(
            dimension_id in {"level_up_result", "elapsed_time", "pool_entry"}
            for group in hierarchy_nodes for dimension_id in group["sourceDimensionIds"]),
        "groundedRuleRelationCount": sum(
            len(item.get("relations", []))
            for group in hierarchy_nodes for item in group["items"]
        ) + sum(len(item.get("relations", []))
                for subgroup in subgroup_nodes for item in subgroup["items"]),
    }
    worthiness_audit = _apply_worthiness(chapters)
    return {
        "chapters": chapters,
        "metrics": metrics,
        "worthinessAudit": worthiness_audit,
        "qualityGate": {
            "unsupportedHierarchyNodeCount": unsupported,
            "emptyHeadingCount": sum(not node["items"] for node in subgroup_nodes),
            "oneRuleMechanicalSubheadingCount": sum(
                sum(1 + len(item["subrules"]) for item in node["items"]) < 2
                and not node.get("structureBasis") for node in subgroup_nodes),
        },
    }


def render_mechanic_rule_preview(hierarchy: dict[str, Any]) -> str:
    lines = ["# Human Planning Preview", ""]
    for chapter in hierarchy["chapters"]:
        publishable_groups = []
        for group in chapter["ruleGroups"]:
            direct = any(item.get("publishWorthiness") != "suppress_common_sense" for item in group["items"])
            nested = any(item.get("publishWorthiness") != "suppress_common_sense"
                         for subgroup in group["subgroups"] for item in subgroup["items"])
            if direct or nested:
                publishable_groups.append(group)
        if not publishable_groups:
            continue
        lines.extend([f"## {chapter['title']}", ""])
        for group in publishable_groups:
            published_direct_items = [item for item in group["items"]
                                      if item.get("publishWorthiness") != "suppress_common_sense"]
            published_subgroups = [subgroup for subgroup in group["subgroups"] if any(
                item.get("publishWorthiness") != "suppress_common_sense" for item in subgroup["items"])]
            flatten_group = (len(publishable_groups) == 1 and not published_direct_items and published_subgroups)
            if not flatten_group:
                lines.extend([f"### {group['title']}", ""])
            for item in published_direct_items:
                lines.append(f"- {item['text']}")
                lines.extend(f"  - {subrule}" for subrule in item["subrules"])
            for subgroup in published_subgroups:
                level = "###" if flatten_group else "####"
                lines.extend([f"{level} {subgroup['title']}", ""])
                for item in subgroup["items"]:
                    if item.get("publishWorthiness") == "suppress_common_sense":
                        continue
                    lines.append(f"- {item['text']}")
                    lines.extend(f"  - {subrule}" for subrule in item["subrules"])
                lines.append("")
            if not group["subgroups"]:
                lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def count_internal_vocabulary_leaks(preview: str) -> int:
    lowered = preview.lower()
    return sum(lowered.count(token) for token in _INTERNAL_VOCABULARY)
