"""Compose approved rules into deterministic, evidence-preserving mechanism blocks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


FIELDS = (
    "definition", "input_constraint", "trigger", "condition", "target_selection",
    "processing", "effect", "state_change", "result", "exit_boundary",
    "presentation", "config_reference",
)

ROLE_BY_SLOT = {
    "movement_trigger": "processing", "movement_direction": "processing", "movement_control": "input_constraint",
    "movement_path": "condition", "movement_collision": "exit_boundary", "movement_stop_condition": "exit_boundary",
    "movement_speed_source": "config_reference", "movement_presentation": "presentation",
    "attack_trigger": "trigger", "attack_target": "target_selection", "attack_method": "processing",
    "attack_range": "config_reference", "attack_frequency": "config_reference", "attack_exit_condition": "exit_boundary",
    "damage_reference": "config_reference", "attack_presentation": "presentation",
    "random_trigger": "trigger", "selection_pause": "state_change", "candidate_selection": "input_constraint",
    "candidate_effect": "effect", "effect_parameter": "effect", "confirm_effect_timing": "exit_boundary",
    "candidate_pool_source": "config_reference", "pool_entry_condition": "condition", "pool_exit_condition": "exit_boundary",
    "duplicate_rule": "exit_boundary", "replacement_rule": "exit_boundary", "weight_rule": "config_reference",
    "empty_result_rule": "exit_boundary", "max_level_rule": "exit_boundary", "prerequisite_rule": "condition",
    "refresh_rule": "processing", "refresh_count": "config_reference", "refresh_cost": "config_reference",
    "random_presentation": "presentation", "roulette_stop": "exit_boundary",
    "spawn_trigger": "trigger", "spawn_source": "definition", "spawn_composition": "config_reference",
    "spawn_interval": "config_reference", "spawn_stop_condition": "exit_boundary",
    "level_start_condition": "trigger", "stage_transition": "state_change", "victory_condition": "result",
    "failure_condition": "result", "level_end_timing": "exit_boundary",
    "settlement_trigger": "trigger", "result_determination": "result", "reward_rule": "result",
    "persistence_timing": "state_change", "exit_path": "exit_boundary", "settlement_presentation": "presentation",
}


def _resolve_primary_role(chapter_type: str, rule: dict[str, Any]) -> tuple[str, str]:
    slot = str(rule.get("schemaSlot") or "")
    behavior = str(rule.get("behavior") or "")
    base = ROLE_BY_SLOT.get(slot)
    if chapter_type == "attack" and slot == "attack_trigger" and "无需玩家手动瞄准" in behavior:
        return "input_constraint", "predicate_pattern_disambiguation:no_manual_aim; base=attack_trigger"
    if chapter_type == "attack" and slot == "attack_trigger" and "接触" in behavior and "造成伤害" in behavior:
        return "effect", "predicate_pattern_disambiguation:contact_damage; base=attack_trigger"
    if chapter_type == "attack" and slot == "attack_target":
        if "选择" in behavior and "作为攻击目标" in behavior:
            return "target_selection", "predicate_pattern_disambiguation:select_as_target; base=attack_target"
        if "发射" in behavior or "伤害区域" in behavior:
            return "processing", "predicate_pattern_disambiguation:attack_execution; base=attack_target"
    if chapter_type == "randomization" and slot == "refresh_rule" and rule.get("ruleType") == "interaction":
        return "trigger", "predicate_pattern_disambiguation:player_refresh_input; base=refresh_rule"
    if chapter_type == "randomization" and slot == "refresh_cost" and "存在" in behavior and ("或" in behavior or "条件" in behavior):
        return "config_reference", "predicate_pattern_disambiguation:unspecified_refresh_dependency; base=refresh_cost"
    if base:
        return base, f"chapter_slot_rule_type:{chapter_type}/{slot}/{rule.get('ruleType')}"
    return "definition", "fallback_descriptive:no_deterministic_role"


def _resolution_status(role: str, rule: dict[str, Any], reason: str) -> str:
    if reason.startswith("fallback_descriptive") or role == "presentation":
        return "descriptive"
    if role == "config_reference" and not rule.get("parameterRefs"):
        behavior = str(rule.get("behavior") or "")
        if "存在" in behavior and ("或" in behavior or "条件" in behavior):
            return "unresolved_dependency"
        return "descriptive"
    return "executable"


def _family(chapter_type: str, content_group: str, rule: dict[str, Any]) -> str:
    if chapter_type == "randomization":
        if rule.get("schemaSlot") == "effect_parameter":
            return f"effect:{rule.get('subject') or rule['ruleId']}"
        return {"flow": "candidate", "draw": "candidate", "presentation": "candidate", "refresh": "refresh", "pool": "pool", "exceptions": "boundary"}.get(content_group, content_group)
    if chapter_type == "attack":
        return "presentation" if content_group == "presentation" else "attack"
    if chapter_type == "movement":
        return "movement"
    if chapter_type == "settlement":
        return "settlement"
    if chapter_type == "level_flow":
        return "level_flow"
    return content_group


def _semantic(chapter: dict[str, Any], family: str, slots: set[str], rules: list[dict[str, Any]]) -> str:
    chapter_type = chapter.get("chapterType")
    if chapter_type == "movement":
        return "移动方式"
    if chapter_type == "attack":
        if family == "presentation":
            return "攻击表现"
        if slots == {"attack_trigger"} and any(rule.get("subject") == "怪物" for rule in rules):
            return "接触伤害"
        return "自动索敌" if "attack_target" in slots else "攻击触发"
    if chapter_type == "randomization":
        if family.startswith("effect:"):
            return f"{family.split(':', 1)[1]}强化"
        return {"candidate": "候选流程", "refresh": "刷新处理", "pool": "候选池", "boundary": "候选边界"}.get(family, chapter.get("title", "随机"))
    if chapter_type == "settlement":
        if chapter.get("title") == "伤害统计":
            return "伤害统计"
        return "界面内容" if slots == {"settlement_presentation"} else "结算处理"
    if chapter_type == "level_flow":
        return "关卡流程"
    return chapter.get("title") or chapter_type or "机制"


def _entry(rule: dict[str, Any], role: str, reason: str, text: str | None = None, resolution_status: str | None = None) -> dict[str, Any]:
    return {
        "text": str(text if text is not None else rule.get("behavior") or ""),
        "ruleId": rule["ruleId"], "semanticKey": rule.get("semanticKey"),
        "ruleType": rule.get("ruleType"), "schemaSlot": rule.get("schemaSlot"),
        "subject": rule.get("subject"),
        "semanticRole": role, "roleAssignmentReason": reason,
        "resolutionStatus": resolution_status or _resolution_status(role, rule, reason),
    }


def _blank(chapter: dict[str, Any], gap_ids: list[str]) -> dict[str, Any]:
    block = {field: [] for field in FIELDS}
    block.update({
        "blockId": f"MB-{chapter['chapterId']}-INSUFFICIENT", "chapterId": chapter["chapterId"],
        "mechanismSemantic": chapter.get("title", "机制"), "status": "evidence_insufficient",
        "ruleIds": [], "factIds": [], "evidenceIds": [], "emptyFields": list(FIELDS),
        "unabsorbedGapIds": gap_ids, "stitchGroups": [], "usedOrganizationRules": [],
        "owner": chapter.get("object") or chapter.get("system") or chapter["chapterId"],
        "compatibleRoleDomain": "insufficient", "synonymousBlockMergeCount": 0, "roleConflicts": [],
    })
    return block


def _merge_compatible_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    by_key: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for block in blocks:
        key = (block["chapterId"], block["owner"], block["mechanismSemantic"], block["compatibleRoleDomain"])
        if key not in by_key:
            by_key[key] = block
            merged.append(block)
            continue
        target = by_key[key]
        for field in FIELDS:
            target[field].extend(block[field])
        for field in ("ruleIds", "factIds", "evidenceIds", "unabsorbedGapIds"):
            target[field] = list(dict.fromkeys(target[field] + block[field]))
        target["stitchGroups"].extend(block["stitchGroups"])
        target["synonymousBlockMergeCount"] += 1 + block.get("synonymousBlockMergeCount", 0)
        target["emptyFields"] = [field for field in FIELDS if not target[field]]
    title_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for block in merged:
        title_groups[(block["chapterId"], block["mechanismSemantic"])].append(block)
    for siblings in title_groups.values():
        domains = {(block["owner"], block["compatibleRoleDomain"]) for block in siblings}
        if len(domains) > 1:
            conflict = {"code": "same_title_incompatible_owner_or_domain", "domains": sorted(f"{owner}/{domain}" for owner, domain in domains)}
            for block in siblings:
                block["roleConflicts"].append(conflict)
    return merged


def compose_mechanism_blocks(chapter: dict[str, Any], approved_rules: list[dict[str, Any]], reviewed_gaps: list[dict[str, Any]], schema: Any) -> list[dict[str, Any]]:
    """Map approved rules to blocks without filling unsupported semantic roles."""
    chapter_id = chapter["chapterId"]
    rules = [rule for rule in approved_rules if rule.get("ownerChapterId") == chapter_id and rule.get("reviewStatus") in {"approved", "confirmed"} and rule.get("semanticValidity") == "valid"]
    gap_ids = [gap["gapId"] for gap in reviewed_gaps if gap.get("chapterId") == chapter_id and gap.get("status") in {"open", "reviewed_open"}]
    if not rules:
        return [_blank(chapter, gap_ids)]

    slot_defs = {slot.slot_id: slot for slot in schema.slots}
    buckets: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for rule in rules:
        slot = slot_defs.get(rule.get("schemaSlot"))
        content_group = slot.content_group if slot else "core"
        family = _family(chapter.get("chapterType", ""), content_group, rule)
        buckets[(family, str(rule.get("semanticKey") or rule["ruleId"]))].append(rule)

    blocks = []
    family_rules_map: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (family, _partition), partition_rules in buckets.items():
        family_rules_map[family].extend(partition_rules)
    for index, ((family, _semantic_partition), family_rules) in enumerate(buckets.items(), 1):
        block = {field: [] for field in FIELDS}
        slots = {rule.get("schemaSlot") for rule in family_rules}
        for rule in family_rules:
            role, reason = _resolve_primary_role(chapter.get("chapterType", ""), rule)
            block[role].append(_entry(rule, role, reason))
            if rule.get("trigger") and role != "trigger":
                block["trigger"].append(_entry(rule, "trigger", "structured_field:trigger", rule["trigger"], "executable"))
            for condition in rule.get("conditions") or []:
                block["condition"].append(_entry(rule, "condition", "structured_field:conditions", condition, "executable"))
            if rule.get("stateChange") and role != "state_change":
                block["state_change"].append(_entry(rule, "state_change", "structured_field:stateChange", rule["stateChange"], "executable"))
            if rule.get("result") and role != "result":
                block["result"].append(_entry(rule, "result", "structured_field:result", rule["result"], "executable"))
            if rule.get("exitCondition") and role != "exit_boundary":
                block["exit_boundary"].append(_entry(rule, "exit_boundary", "structured_field:exitCondition", rule["exitCondition"], "executable"))
            if rule.get("parameterRefs") and role != "config_reference":
                block["config_reference"].append(_entry(rule, "config_reference", "structured_field:parameterRefs", "、".join(rule["parameterRefs"]), "executable"))
        rule_ids = [rule["ruleId"] for rule in family_rules]
        status = "partial_mechanism_chain" if gap_ids or any(not block[field] for field in ("trigger", "processing", "result", "exit_boundary")) else "confirmed_mechanism_chain"
        block.update({
            "blockId": f"MB-{chapter_id}-{index:02d}", "chapterId": chapter_id,
            "mechanismSemantic": _semantic(chapter, family, {rule.get("schemaSlot") for rule in family_rules_map[family]}, family_rules_map[family]), "status": status,
            "ruleIds": rule_ids,
            "factIds": list(dict.fromkeys(fid for rule in family_rules for fid in rule.get("sourceFactIds", []))),
            "evidenceIds": list(dict.fromkeys(eid for rule in family_rules for eid in rule.get("evidenceIds", []))),
            "emptyFields": [field for field in FIELDS if not block[field]],
            "unabsorbedGapIds": gap_ids,
            "stitchGroups": [rule_ids] if len(rule_ids) > 1 else [],
            "usedOrganizationRules": ["chapter_internal_grouping", "mechanism_semantic_subheading", "definition_before_detail", "lifecycle_after_main_behavior"],
            "partitionEvidence": {"chapterType": chapter.get("chapterType"), "schemaContentFamily": family, "policy": "explicit_schema_group_adjacency"},
            "owner": chapter.get("object") or chapter.get("system") or chapter_id,
            "compatibleRoleDomain": family,
            "synonymousBlockMergeCount": 0,
            "roleConflicts": [],
        })
        blocks.append(block)
    return _merge_compatible_blocks(blocks)
