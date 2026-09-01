from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import re
from typing import Any, Mapping


EXECUTION_TYPES = frozenset({"logic", "flow", "numeric", "config", "interaction"})
DERIVATION_TYPES = frozenset({"causal_bridge", "required_input", "required_output", "state_transition_bridge", "schema_applicability", "gap_backed"})


def _component(role: str, semantic: str, text: str, source: str = "behavior") -> dict[str, Any]:
    return {"semanticRole": role, "nodeSemantic": semantic, "text": text.strip(" ，。；"), "sourceField": source}


def decompose_rule_semantics(rule: dict[str, Any]) -> dict[str, Any]:
    """Deterministically expose every execution semantic explicitly asserted by one Rule."""
    behavior = str(rule.get("behavior") or "").strip()
    subject = str(rule.get("subject") or "").strip()
    slot = str(rule.get("schemaSlot") or "")
    components: list[dict[str, Any]] = []

    structured = (("condition", rule.get("condition")), ("trigger", rule.get("trigger")),
                  ("result", rule.get("result")), ("boundary", rule.get("boundary")))
    for role, value in structured:
        if value:
            components.append(_component(role, f"{slot}_{role}", str(value), role))

    if slot.startswith("movement_"):
        if subject and subject != "玩家":
            components.append(_component("object", "moving_object", subject, "subject"))
        if "路线" in behavior or "路径" in behavior:
            components.append(_component("input_constraint", "movement_path", "存在预设路线"))
        if any(token in behavior for token in ("行进", "移动", "微调")):
            components.append(_component("action", "position_update", behavior))
        if subject == "玩家":
            components.append(_component("trigger", "movement_input", behavior))
    elif slot.startswith("attack_"):
        if subject:
            components.append(_component("object", "attacker", subject, "subject"))
        if "无需玩家手动瞄准" in behavior:
            components.append(_component("input_constraint", "manual_aim_constraint", behavior))
        if "选择" in behavior and "目标" in behavior:
            components.append(_component("target_selection", "target_selection", behavior))
        if any(token in behavior for token in ("发射", "生成持续伤害区域", "执行攻击")):
            components.append(_component("action", "attack_execution", behavior))
        contact = re.search(r"(.+?接触.+?)后(.+)", behavior)
        if contact:
            components.append(_component("condition", "attack_trigger", contact.group(1)))
            components.append(_component("result", "damage_output", contact.group(2)))
    elif slot in {"selection_pause", "random_trigger", "candidate_selection", "candidate_effect", "effect_parameter", "refresh_rule", "refresh_cost"}:
        if "触发时" in behavior:
            prefix, suffix = behavior.split("触发时", 1)
            components.append(_component("trigger", "random_trigger", prefix + "触发"))
            if "暂停" in suffix:
                components.append(_component("state_change", "selection_state", suffix))
            if "生成" in suffix:
                components.append(_component("result", "candidate_generation", suffix))
        if slot == "candidate_selection":
            components.append(_component("action", "selection_processing", behavior))
        if slot in {"candidate_effect", "effect_parameter"}:
            components.append(_component("state_change", "effect_transition", behavior))
        if slot == "refresh_rule":
            components.append(_component("action", "refresh_processing", behavior))
            if "替换" in behavior:
                components.append(_component("result", "candidate_generation", behavior))
        if slot == "refresh_cost":
            components.append(_component("numeric", "random_parameters", behavior))
    if rule.get("ruleType") == "numeric" or re.search(r"\d+(?:\.\d+)?%", behavior):
        semantic = "random_parameters" if slot == "effect_parameter" else f"{slot}_numeric"
        components.append(_component("numeric", semantic, behavior))

    unique = []
    seen = set()
    for item in components:
        key = (item["semanticRole"], item["nodeSemantic"], item["text"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return {"ruleId": rule["ruleId"], "subject": subject or None, "components": unique,
            "componentCount": len(unique), "sourceBehavior": behavior}


def _node_id(mechanic_id: str, semantic: str) -> str:
    return "MGN-" + hashlib.sha1(f"{mechanic_id}:{semantic}".encode()).hexdigest()[:10].upper()


def _node_type(role: str) -> str:
    return {"object": "object", "condition": "condition", "trigger": "trigger", "input_constraint": "input_constraint",
            "target_selection": "target_selection", "action": "processing", "state_change": "state_transition",
            "result": "result", "boundary": "boundary", "numeric": "parameter"}.get(role, role)


def _derived(mechanic_type: str, confirmed: set[str], by_rule: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if mechanic_type == "attack" and {"target_selection", "attack_execution"} <= confirmed:
        rules = sorted(set(by_rule["target_selection"] + by_rule["attack_execution"]))
        result["target_set_build"] = {"derivationType": "required_input", "sourceRuleIds": rules,
            "sourceSemantics": ["target_selection", "attack_execution"], "derivationReason": "目标选择需要可供选择的目标集合，且该集合是攻击执行不可跳过的输入。"}
    if mechanic_type == "randomization" and {"candidate_generation", "selection_processing"} <= confirmed:
        rules = sorted(set(by_rule["candidate_generation"] + by_rule["selection_processing"]))
        result["candidate_draw"] = {"derivationType": "causal_bridge", "sourceRuleIds": rules,
            "sourceSemantics": ["candidate_generation", "selection_processing"], "derivationReason": "候选生成与选择处理之间必然存在候选抽取处理，但抽取规则仍未知。"}
    return result


def ground_mechanic_graphs(planning_models: list[dict[str, Any]], approved_rules: list[dict[str, Any]],
                           reviewed_gaps: list[dict[str, Any]], corpus: Mapping[str, Any]) -> list[dict[str, Any]]:
    rules = [deepcopy(rule) for rule in approved_rules if rule.get("reviewStatus") in {"approved", "confirmed"}
             and rule.get("semanticValidity") == "valid" and rule.get("ruleType") in EXECUTION_TYPES]
    decompositions = {rule["ruleId"]: decompose_rule_semantics(rule) for rule in rules}
    graphs = []
    for model in deepcopy(planning_models):
        chapter_ids = set(model.get("chapterIds") or [model.get("chapterId")])
        group_rules = [rule for rule in rules if rule.get("ownerChapterId") in chapter_ids]
        grounded: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for rule in group_rules:
            for component in decompositions[rule["ruleId"]]["components"]:
                grounded[component["nodeSemantic"]].append({"rule": rule, "component": component})
        by_rule = {semantic: [item["rule"]["ruleId"] for item in items] for semantic, items in grounded.items()}
        derived = _derived(model["mechanicType"], set(grounded), by_rule)
        old_by_semantic = {node["mechanismNode"]: node for node in model.get("nodes", [])}
        semantics = list(old_by_semantic)
        semantics.extend(semantic for semantic in grounded if semantic not in old_by_semantic)
        nodes = []
        for semantic in semantics:
            old = old_by_semantic.get(semantic, {})
            items = grounded.get(semantic, [])
            gaps = [entry["gapId"] for entry in old.get("gapLocations", [])]
            if items:
                status = "confirmed"
            elif gaps:
                status = "unresolved"
            elif semantic in derived:
                status = "derived_structure"
            else:
                status = "hypothesis"
            derivation = derived.get(semantic, {}) if status == "derived_structure" else {}
            source_semantics = derivation.get("sourceSemantics", [])
            nodes.append({
                "nodeId": _node_id(model["mechanicId"], semantic), "semantic": semantic,
                "nodeType": _node_type(items[0]["component"]["semanticRole"]) if items else old.get("axis"), "status": status,
                "supportingRuleIds": sorted({item["rule"]["ruleId"] for item in items}), "supportingGapIds": gaps,
                "supportingEvidenceIds": sorted({evidence for item in items for evidence in item["rule"].get("evidenceIds", [])}),
                "supportedSemanticRoles": sorted({item["component"]["semanticRole"] for item in items}),
                "derivationType": derivation.get("derivationType"),
                "sourceNodeIds": [_node_id(model["mechanicId"], value) for value in source_semantics],
                "sourceRuleIds": derivation.get("sourceRuleIds", []), "derivationReason": derivation.get("derivationReason"),
                "previousStatus": old.get("reasoningStatus"),
            })
        indexed = {node["semantic"]: node for node in nodes}
        edges = []
        # Same-rule semantic order is primary evidence for graph relations.
        role_order = {"condition": 0, "trigger": 0, "input_constraint": 0, "object": 0, "target_selection": 1,
                      "action": 2, "state_change": 3, "result": 4, "numeric": 1, "boundary": 5}
        for rule in group_rules:
            components = sorted(decompositions[rule["ruleId"]]["components"], key=lambda item: role_order.get(item["semanticRole"], 2))
            operational = [item for item in components if item["semanticRole"] != "object"]
            for start, end in zip(operational, operational[1:]):
                edge_start, edge_end = start, end
                relation = "produces"
                if start["semanticRole"] in {"condition", "trigger"}:
                    relation = "triggers"
                elif start["semanticRole"] == "input_constraint":
                    relation = "requires"
                    edge_start, edge_end = end, start
                elif start["semanticRole"] == "numeric":
                    relation = "depends_on"
                    edge_start, edge_end = end, start
                elif end["semanticRole"] == "state_change":
                    relation = "transitions_to"
                edges.append({"fromNodeId": indexed[edge_start["nodeSemantic"]]["nodeId"], "toNodeId": indexed[edge_end["nodeSemantic"]]["nodeId"],
                              "relationType": relation, "conditionRef": indexed[start["nodeSemantic"]]["nodeId"] if start["semanticRole"] in {"condition", "trigger"} else None,
                              "evidenceStatus": "confirmed", "supportingRuleIds": [rule["ruleId"]], "durationKind": None})
        # Corpus edges are admitted only when both endpoints are already grounded or strictly derived.
        for pattern in corpus.get("patterns", ()):
            if pattern["mechanicType"] != model["mechanicType"]:
                continue
            for start, relation, end in pattern["edgePatterns"]:
                if start not in indexed or end not in indexed:
                    continue
                pair = (indexed[start], indexed[end])
                if not all(node["status"] in {"confirmed", "derived_structure"} for node in pair):
                    continue
                key = (pair[0]["nodeId"], pair[1]["nodeId"], relation)
                if any((edge["fromNodeId"], edge["toNodeId"]) == key[:2] for edge in edges):
                    continue
                edges.append({"fromNodeId": pair[0]["nodeId"], "toNodeId": pair[1]["nodeId"], "relationType": relation,
                              "conditionRef": None, "evidenceStatus": "justified_derived" if any(node["status"] == "derived_structure" for node in pair) else "confirmed",
                              "supportingRuleIds": sorted(set(pair[0]["supportingRuleIds"] + pair[1]["supportingRuleIds"])),
                              "durationKind": "transientStateDuration" if relation == "persists_until" else None,
                              "derivationType": "schema_applicability", "derivationReason": "匿名结构 pattern 仅在两个端点均已由当前项目 Rule grounding 后提供关系候选。"})
        graphs.append({"mechanicId": model["mechanicId"], "chapterId": model.get("chapterId"), "name": model.get("name"),
                       "mechanicType": model["mechanicType"], "nodes": nodes, "edges": edges,
                       "ruleDecompositions": [decompositions[rule["ruleId"]] for rule in group_rules],
                       "supportingRuleIds": [rule["ruleId"] for rule in group_rules],
                       "lifecycle": {"status": "not_applicable", "doesMechanicOwnPersistentState": False,
                                     "transientStateDurationEdgeIds": [index for index, edge in enumerate(edges) if edge.get("durationKind") == "transientStateDuration"],
                                     "lifecyclePersistence": [], "lifecycleApplicabilityReason": "没有 Approved Rule 证明跨阶段、跨流程或跨关卡的 initialize/save/reset。"},
                       "contentAuthority": "approved_rule_only", "nonConfirmedNodesCanGenerateRule": False})
    return graphs
