from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
from typing import Any, Mapping


EXECUTION_TYPES = frozenset({"logic", "flow", "numeric", "config", "interaction"})


def _approved(rule: dict[str, Any]) -> bool:
    return rule.get("reviewStatus") in {"approved", "confirmed"} and rule.get("semanticValidity") == "valid"


def _mechanic_id(chapter_ids: list[str], mechanic_type: str) -> str:
    digest = hashlib.sha1(("|".join(chapter_ids) + ":planning:" + mechanic_type).encode("utf-8")).hexdigest()[:12].upper()
    return f"PMECH-{digest}"


def _node_profile(raw: tuple[Any, ...]) -> dict[str, Any]:
    return {"mechanismNode": raw[0], "axis": raw[1], "necessity": raw[2], "slotPatterns": tuple(raw[3])}


def _group(chapters: list[dict[str, Any]], corpus: Mapping[str, Any]) -> list[list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for chapter in chapters:
        mechanic_type = str(chapter.get("chapterType") or "")
        if mechanic_type not in corpus["templates"]:
            continue
        key = (str(chapter.get("object") or ""), mechanic_type, str(chapter.get("mechanicVariant") or ""))
        grouped[key].append(chapter)
    return [sorted(items, key=lambda item: item["chapterId"]) for items in grouped.values()]


def _rule_nodes(mechanic_type: str, rule: dict[str, Any], profiles: list[dict[str, Any]]) -> list[str]:
    slot = str(rule.get("schemaSlot") or "")
    behavior = str(rule.get("behavior") or "")
    if mechanic_type == "attack":
        if slot == "attack_trigger" and "无需玩家手动瞄准" in behavior:
            return ["attack_entry"]
        if slot == "attack_trigger":
            return ["attack_trigger"]
        if slot == "attack_target" and "选择" in behavior and "目标" in behavior:
            return ["target_selection"]
        if slot in {"attack_target", "attack_method"} and any(token in behavior for token in ("发射", "生成", "执行")):
            return ["attack_execution"]
    if mechanic_type == "movement":
        if slot == "movement_trigger":
            return ["movement_entry", "position_update"]
        if slot == "movement_control":
            return ["movement_input", "position_update"]
    if mechanic_type == "randomization":
        special = {
            "random_trigger": ["random_trigger", "candidate_generation"],
            "selection_pause": ["selection_state"],
            "candidate_selection": ["selection_processing"],
            "candidate_effect": ["effect_transition", "selection_output"],
            "effect_parameter": ["effect_transition"],
            "refresh_rule": ["refresh_processing"],
            "refresh_cost": ["refresh_processing", "random_parameters"],
        }
        if slot in special:
            return special[slot]
    matches = [profile["mechanismNode"] for profile in profiles if slot and slot in profile["slotPatterns"]]
    return matches[:1]


def _gap_node(gap: dict[str, Any], profiles: list[dict[str, Any]]) -> str | None:
    slot = str(gap.get("schemaSlot") or "")
    return next((profile["mechanismNode"] for profile in profiles if slot in profile["slotPatterns"]), None)


def build_planning_mechanism_models(
    chapters: list[dict[str, Any]], approved_rules: list[dict[str, Any]], reviewed_gaps: list[dict[str, Any]],
    facts: list[dict[str, Any]], entity_graph: dict[str, Any], corpus: Mapping[str, Any],
) -> list[dict[str, Any]]:
    chapter_data = deepcopy(chapters)
    rules = [deepcopy(rule) for rule in approved_rules if _approved(rule) and rule.get("ruleType") in EXECUTION_TYPES]
    gaps = [deepcopy(gap) for gap in reviewed_gaps if gap.get("status") not in {"closed", "resolved"}]
    facts_by_id = {fact["factId"]: deepcopy(fact) for fact in facts}
    graph = deepcopy(entity_graph)
    models = []
    for chapter_group in _group(chapter_data, corpus):
        chapter_ids = [chapter["chapterId"] for chapter in chapter_group]
        primary = chapter_group[0]
        mechanic_type = primary["chapterType"]
        profiles = [_node_profile(raw) for raw in corpus["templates"][mechanic_type]["nodes"]]
        group_rules = [rule for rule in rules if rule.get("ownerChapterId") in chapter_ids]
        group_gaps = [gap for gap in gaps if gap.get("chapterId") in chapter_ids]
        mechanic_id = _mechanic_id(chapter_ids, mechanic_type)
        rules_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        gaps_by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rule in group_rules:
            for node_key in _rule_nodes(mechanic_type, rule, profiles):
                rules_by_node[node_key].append(rule)
        for gap in group_gaps:
            node_key = _gap_node(gap, profiles)
            if node_key:
                gaps_by_node[node_key].append(gap)

        nodes = []
        for index, profile in enumerate(profiles, start=1):
            key = profile["mechanismNode"]
            node_rules = rules_by_node.get(key, [])
            node_gaps = gaps_by_node.get(key, [])
            if node_rules:
                status = "confirmed"
            elif node_gaps:
                status = "unresolved"
            elif profile["necessity"] == "conditional":
                status = "hypothesis"
            else:
                status = "derived_structure"
            fact_ids = sorted({fact_id for rule in node_rules for fact_id in rule.get("sourceFactIds", []) if fact_id in facts_by_id})
            evidence_ids = sorted({evidence_id for rule in node_rules for evidence_id in rule.get("evidenceIds", [])})
            for fact_id in fact_ids:
                evidence_ids.extend(facts_by_id[fact_id].get("evidenceIds", []))
            gap_locations = [{"gapId": gap["gapId"], "mechanicId": mechanic_id, "mechanismNode": key} for gap in node_gaps]
            nodes.append({
                "nodeId": f"{mechanic_id}-N{index:02d}", "mechanismNode": key, "axis": profile["axis"],
                "reasoningStatus": status, "content": [rule.get("behavior") for rule in node_rules] if node_rules else None,
                "supportingRuleIds": [rule["ruleId"] for rule in node_rules], "supportingFactIds": fact_ids,
                "supportingEvidenceIds": sorted(set(evidence_ids)), "gapLocations": gap_locations,
                "reviewSuggestionOnly": status == "hypothesis",
            })
        node_by_axis: dict[str, list[str]] = defaultdict(list)
        for node in nodes:
            node_by_axis[node["axis"]].append(node["nodeId"])
        rule_ids = sorted({rule_id for node in nodes for rule_id in node["supportingRuleIds"]})
        fact_ids = sorted({fact_id for node in nodes for fact_id in node["supportingFactIds"]})
        evidence_ids = sorted({evidence_id for node in nodes for evidence_id in node["supportingEvidenceIds"]})
        actors = sorted({str(rule.get("subject")) for rule in group_rules if rule.get("subject")})
        objects = [str(primary.get("object"))] if primary.get("object") else []
        for entity in graph.get("entities", []):
            if set(entity.get("relatedRuleIds", [])).intersection(rule_ids):
                objects.append(str(entity.get("entityId")))
        object_name = str(primary.get("object") or "")
        title = str(primary.get("title") or "")
        models.append({
            "mechanicId": mechanic_id, "chapterId": primary["chapterId"], "chapterIds": chapter_ids,
            "mechanicType": mechanic_type, "name": object_name if object_name == title else " / ".join(filter(None, (object_name, title))),
            "actors": sorted(set(actors)), "objects": sorted(set(objects)), "states": node_by_axis["state"],
            "entryConditions": node_by_axis["entry_condition"], "triggers": node_by_axis["trigger"],
            "preconditions": node_by_axis["precondition"], "processingStages": node_by_axis["processing"],
            "stateTransitions": node_by_axis["state_transition"], "outputs": node_by_axis["output"],
            "exitConditions": node_by_axis["exit_condition"], "exceptions": node_by_axis["exception"],
            "boundaries": node_by_axis["boundary"], "parameters": node_by_axis["parameter"],
            "configSources": node_by_axis["config_source"], "upstreamMechanics": node_by_axis["upstream_dependency"],
            "downstreamMechanics": node_by_axis["downstream_dependency"],
            "lifecycle": {"initialize": node_by_axis["lifecycle_initialize"], "persist": node_by_axis["lifecycle_persist"], "reset": node_by_axis["lifecycle_reset"]},
            "confirmedNodes": [node for node in nodes if node["reasoningStatus"] == "confirmed"],
            "derivedStructureNodes": [node for node in nodes if node["reasoningStatus"] == "derived_structure"],
            "hypothesisNodes": [node for node in nodes if node["reasoningStatus"] == "hypothesis"],
            "unresolvedNodes": [node for node in nodes if node["reasoningStatus"] == "unresolved"],
            "nodes": nodes, "supportingRuleIds": rule_ids, "supportingFactIds": fact_ids, "supportingEvidenceIds": evidence_ids,
            "localizedGaps": [location for node in nodes for location in node["gapLocations"]],
            "unmappedGapIds": [gap["gapId"] for gap in group_gaps if not _gap_node(gap, profiles)],
            "contentAuthority": "approved_rule_only", "nonConfirmedNodesCanGenerateRule": False,
        })
    return models
