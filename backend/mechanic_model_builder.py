from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
from typing import Any, Mapping


LOGIC_TYPES = frozenset({"logic", "flow", "numeric", "config", "interaction"})


def _approved(rule: dict[str, Any]) -> bool:
    return rule.get("reviewStatus") in {"approved", "confirmed"} and rule.get("semanticValidity") == "valid"


def _stable_id(chapter_ids: list[str], mechanic_type: str) -> str:
    digest = hashlib.sha1(("|".join(chapter_ids) + ":" + mechanic_type).encode("utf-8")).hexdigest()[:12].upper()
    return f"MECH-{digest}"


def _group_chapters(chapters: list[dict[str, Any]], corpus: Mapping[str, Any]) -> list[list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for chapter in chapters:
        mechanic_type = str(chapter.get("chapterType") or "")
        if mechanic_type not in corpus["mechanicTypes"]:
            continue
        key = (str(chapter.get("object") or chapter.get("owner") or ""), mechanic_type, str(chapter.get("mechanicVariant") or ""))
        grouped[key].append(chapter)
    return [sorted(items, key=lambda item: item["chapterId"]) for items in grouped.values()]


def _rule_node_keys(mechanic_type: str, rule: dict[str, Any], profiles: tuple[Mapping[str, Any], ...]) -> list[str]:
    slot = str(rule.get("schemaSlot") or "")
    behavior = str(rule.get("behavior") or "")
    if mechanic_type == "attack":
        if slot == "attack_trigger" and "无需玩家手动瞄准" in behavior:
            return ["attack_input_mode"]
        if slot == "attack_trigger":
            return ["attack_trigger"]
        if slot == "attack_target" and "选择" in behavior and "目标" in behavior:
            return ["attack_target_select"]
        if slot in {"attack_target", "attack_method"} and any(token in behavior for token in ("发射", "生成", "执行")):
            return ["attack_execute"]
    if mechanic_type == "randomization":
        if slot == "random_trigger":
            return ["random_trigger", "candidate_generate"]
        if slot == "selection_pause":
            return ["random_pause"]
        if slot == "candidate_selection":
            return ["candidate_select"]
        if slot in {"candidate_effect", "effect_parameter", "confirm_effect_timing"}:
            return ["candidate_apply"]
        if slot in {"refresh_rule", "refresh_count", "refresh_cost"}:
            return ["candidate_refresh"]
    if mechanic_type == "movement":
        if slot == "movement_trigger":
            return ["movement_start", "movement_update"]
        if slot == "movement_control":
            return ["movement_input", "movement_update"]
    matches = [
        str(profile["nodeKey"]) for profile in profiles
        if slot and slot in profile.get("slotPatterns", ())
    ]
    return matches[:1]


def _gap_node_key(gap: dict[str, Any], profiles: tuple[Mapping[str, Any], ...]) -> str | None:
    slot = str(gap.get("schemaSlot") or "")
    for profile in profiles:
        if slot in profile.get("slotPatterns", ()):
            return str(profile["nodeKey"])
    return None


def _rule_information_gain(rule: dict[str, Any], node_keys: list[str], nodes_by_key: dict[str, Mapping[str, Any]]) -> dict[str, Any]:
    behavior = str(rule.get("behavior") or "")
    roles = {str(nodes_by_key[key]["role"]) for key in node_keys if key in nodes_by_key}
    signals: set[str] = set()
    if rule.get("ruleType") == "interaction" or roles.intersection({"input"}):
        signals.add("input")
    if rule.get("trigger") or rule.get("conditions") or rule.get("condition"):
        signals.add("condition")
    if roles.intersection({"trigger", "precondition"}):
        signals.add("condition")
    if roles.intersection({"processing", "effect"}) and rule.get("ruleType") != "interaction":
        signals.add("processing")
    if roles.intersection({"state_change", "state_before"}) or rule.get("stateChange") or any(token in behavior for token in ("替换", "改变", "更新", "暂停", "恢复")):
        signals.add("state_change")
    if roles.intersection({"output"}) or rule.get("result") or any(token in behavior for token in ("生成", "造成", "增加", "扩大")):
        signals.add("result")
    if roles.intersection({"exit_boundary", "failure_boundary"}) or rule.get("exitCondition") or rule.get("exception"):
        signals.add("boundary")
    if roles.intersection({"parameter_need"}) or rule.get("ruleType") in {"numeric", "config"} or rule.get("parameterRefs"):
        signals.add("parameter_contract")
    if roles.intersection({"dependency"}):
        signals.add("cross_mechanic_dependency")
    if "目标" in behavior or (rule.get("subject") and any(token in behavior for token in ("改变", "替换", "造成"))):
        signals.add("system_relationship")
    return {
        "ruleId": rule["ruleId"],
        "signals": sorted(signals),
        "mechanicalInformationGain": len(signals),
        "classification": "low_abstraction" if len(signals) <= 1 else "mechanically_dense",
    }


def build_mechanic_models(
    chapters: list[dict[str, Any]], approved_rules: list[dict[str, Any]], reviewed_gaps: list[dict[str, Any]],
    schemas: Mapping[str, Any] | list[dict[str, Any]], entity_graph: dict[str, Any],
    structure_corpus: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Build read-only mechanism skeletons; never promotes structural inference to Rule content."""
    chapter_data = deepcopy(chapters)
    rules = [deepcopy(rule) for rule in approved_rules if _approved(rule) and rule.get("ruleType") in LOGIC_TYPES]
    gaps = [deepcopy(gap) for gap in reviewed_gaps if gap.get("status") not in {"closed", "resolved"}]
    graph = deepcopy(entity_graph)
    del schemas  # Schema applicability was already resolved by Phase 3 GapAnalyzer.
    models: list[dict[str, Any]] = []
    for chapter_group in _group_chapters(chapter_data, structure_corpus):
        chapter_ids = [item["chapterId"] for item in chapter_group]
        primary = chapter_group[0]
        mechanic_type = primary["chapterType"]
        profile = structure_corpus["mechanicTypes"][mechanic_type]
        node_profiles = profile["nodes"]
        nodes_by_key = {str(item["nodeKey"]): item for item in node_profiles}
        group_rules = [rule for rule in rules if rule.get("ownerChapterId") in chapter_ids]
        group_gaps = [gap for gap in gaps if gap.get("chapterId") in chapter_ids]
        rules_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        gaps_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rule in group_rules:
            for node_key in _rule_node_keys(mechanic_type, rule, node_profiles):
                rules_by_node[node_key].append(rule)
        for gap in group_gaps:
            node_key = _gap_node_key(gap, node_profiles)
            if node_key:
                gaps_by_node[node_key].append(gap)

        mechanic_id = _stable_id(chapter_ids, mechanic_type)
        nodes: list[dict[str, Any]] = []
        for index, node_profile in enumerate(node_profiles, start=1):
            node_key = str(node_profile["nodeKey"])
            node_rules = rules_by_node.get(node_key, [])
            node_gaps = gaps_by_node.get(node_key, [])
            variants = set(node_profile.get("variants", ()))
            variant = str(primary.get("mechanicVariant") or "")
            if variants and variant not in variants:
                status = "not_applicable"
            elif node_rules:
                status = "confirmed"
            elif node_gaps:
                status = "unresolved"
            else:
                status = "inferred_structure"
            nodes.append({
                "nodeId": f"{mechanic_id}-N{index:02d}",
                "nodeKey": node_key,
                "label": node_profile["label"],
                "role": node_profile["role"],
                "status": status,
                "coverageStatus": "partial" if node_rules and node_gaps else ("covered" if node_rules else "open"),
                "content": [rule.get("behavior") for rule in node_rules] if node_rules else None,
                "supportingRuleIds": [rule["ruleId"] for rule in node_rules],
                "supportingGapIds": [gap["gapId"] for gap in node_gaps],
                "supportingEvidenceIds": sorted({evidence_id for rule in node_rules for evidence_id in rule.get("evidenceIds", [])}),
            })

        rule_ids = sorted({rule_id for node in nodes for rule_id in node["supportingRuleIds"]})
        evidence_ids = sorted({evidence_id for node in nodes for evidence_id in node["supportingEvidenceIds"]})
        actors = sorted({str(rule.get("subject")) for rule in group_rules if rule.get("subject")})
        if primary.get("object"):
            actors.append(str(primary["object"]))
        for entity in graph.get("entities", []):
            if set(entity.get("relatedRuleIds", [])).intersection(rule_ids):
                actors.append(str(entity.get("entityId")))
        actors = sorted(set(actors))
        by_role = lambda *roles: [node["nodeId"] for node in nodes if node["role"] in roles and node["status"] != "not_applicable"]
        confirmed = [node for node in nodes if node["status"] == "confirmed"]
        inferred = [node for node in nodes if node["status"] == "inferred_structure"]
        unresolved = [node for node in nodes if node["status"] == "unresolved"]
        applicable_count = len(nodes) - sum(node["status"] == "not_applicable" for node in nodes)
        confidence = round(len(confirmed) / applicable_count, 4) if applicable_count else 1.0
        contributions = [
            _rule_information_gain(rule, _rule_node_keys(mechanic_type, rule, node_profiles), nodes_by_key)
            for rule in group_rules
        ]
        object_name = str(primary.get("object") or "")
        title = str(primary.get("title") or "")
        models.append({
            "mechanicId": mechanic_id,
            "chapterId": primary["chapterId"],
            "chapterIds": chapter_ids,
            "mechanicType": mechanic_type,
            "mechanicVariant": primary.get("mechanicVariant"),
            "name": object_name if object_name == title else " / ".join(part for part in (object_name, title) if part),
            "purpose": profile["purpose"],
            "actors": actors,
            "inputs": by_role("input"),
            "preconditions": by_role("precondition"),
            "trigger": (by_role("trigger") or [None])[0],
            "stateBefore": by_role("state_before"),
            "processingSteps": by_role("processing", "effect"),
            "stateChanges": by_role("state_change"),
            "outputs": by_role("output"),
            "exitConditions": by_role("exit_boundary"),
            "failureOrBoundary": by_role("failure_boundary"),
            "dependentMechanics": by_role("dependency"),
            "parameterNeeds": by_role("parameter_need"),
            "confirmedNodes": confirmed,
            "inferredNodes": inferred,
            "unresolvedNodes": unresolved,
            "notApplicableNodes": [node for node in nodes if node["status"] == "not_applicable"],
            "nodes": nodes,
            "supportingRuleIds": rule_ids,
            "supportingEvidenceIds": evidence_ids,
            "ruleMechanicalInformationGain": contributions,
            "unmappedGapIds": [gap["gapId"] for gap in group_gaps if not _gap_node_key(gap, node_profiles)],
            "confidence": confidence,
            "contentAuthority": "approved_rule_only",
        })
    return models
