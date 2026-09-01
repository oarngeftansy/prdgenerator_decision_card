from __future__ import annotations

from copy import deepcopy
import hashlib
from typing import Any, Mapping


RELATIONS = frozenset({"triggers", "requires", "transitions_to", "branches_to", "repeats_to", "produces", "depends_on", "persists_until", "resets"})
FORBIDDEN_AUTO_DERIVED = frozenset({"lifecycle_initialize", "lifecycle_persist", "lifecycle_reset", "config_source", "exception", "boundary", "upstream_dependency", "downstream_dependency"})


def _id(mechanic_id: str, semantic: str) -> str:
    digest = hashlib.sha1(f"{mechanic_id}:{semantic}".encode()).hexdigest()[:10].upper()
    return f"MGN-{digest}"


def _patterns(corpus: Mapping[str, Any], mechanic_type: str) -> list[Mapping[str, Any]]:
    return [pattern for pattern in corpus["patterns"] if pattern["mechanicType"] == mechanic_type]


def _justified_semantics(mechanic_type: str, confirmed: set[str]) -> dict[str, str]:
    justified: dict[str, str] = {}
    if mechanic_type == "attack" and {"target_selection", "attack_execution"} <= confirmed:
        justified["target_set_build"] = "已确认目标选择与攻击执行之间必然需要可供选择的目标集合。"
    if mechanic_type == "randomization" and {"candidate_generation", "selection_processing"} <= confirmed:
        justified["candidate_draw"] = "已确认候选生成与选择处理，生成候选前必然存在抽取处理。"
    return justified


def _persistent_state(mechanic_type: str, confirmed: set[str]) -> tuple[bool, str]:
    if mechanic_type == "randomization" and {"selection_state", "selection_processing"} <= confirmed:
        return True, "已确认候选选择状态会持续至玩家选择或刷新处理。"
    return False, "没有 Approved Rule 证明该机制拥有跨步骤持续并需初始化或重置的状态。"


def reconstruct_mechanic_graphs(
    planning_models: list[dict[str, Any]], approved_rules: list[dict[str, Any]],
    reviewed_gaps: list[dict[str, Any]], corpus: Mapping[str, Any],
) -> list[dict[str, Any]]:
    del approved_rules, reviewed_gaps  # provenance is already carried by the read-only planning models
    graphs = []
    for raw_model in deepcopy(planning_models):
        mechanic_id = raw_model["mechanicId"]
        mechanic_type = raw_model["mechanicType"]
        confirmed = {node["mechanismNode"] for node in raw_model.get("nodes", []) if node.get("reasoningStatus") == "confirmed"}
        justified = _justified_semantics(mechanic_type, confirmed)
        nodes = []
        for raw in raw_model.get("nodes", []):
            semantic = raw["mechanismNode"]
            gaps = [item["gapId"] for item in raw.get("gapLocations", [])]
            if raw.get("reasoningStatus") == "confirmed" and raw.get("supportingRuleIds"):
                status = "confirmed"
            elif gaps:
                status = "unresolved"
            elif semantic in justified and raw.get("axis") not in FORBIDDEN_AUTO_DERIVED:
                status = "derived_structure"
            else:
                status = "hypothesis"
            nodes.append({
                "nodeId": _id(mechanic_id, semantic), "semantic": semantic, "nodeType": raw.get("axis"),
                "status": status, "supportingRuleIds": raw.get("supportingRuleIds", []),
                "supportingGapIds": gaps, "supportingEvidenceIds": raw.get("supportingEvidenceIds", []),
                "derivationJustified": status == "derived_structure",
                "derivationReason": justified.get(semantic) if status == "derived_structure" else None,
                "previousStatus": raw.get("reasoningStatus"),
            })
        by_semantic = {node["semantic"]: node for node in nodes}
        edges = []
        for pattern in _patterns(corpus, mechanic_type):
            for edge_pattern in pattern["edgePatterns"]:
                start, relation, end = edge_pattern
                if start not in by_semantic or end not in by_semantic or relation not in RELATIONS:
                    continue
                endpoints = (by_semantic[start], by_semantic[end])
                statuses = {node["status"] for node in endpoints}
                if statuses <= {"confirmed"}:
                    evidence_status = "confirmed"
                elif statuses <= {"confirmed", "derived_structure"} and "derived_structure" in statuses:
                    evidence_status = "justified_derived"
                else:
                    evidence_status = "unresolved"
                edges.append({"fromNodeId": endpoints[0]["nodeId"], "toNodeId": endpoints[1]["nodeId"],
                              "relationType": relation, "conditionRef": None, "evidenceStatus": evidence_status})
        owns_state, reason = _persistent_state(mechanic_type, confirmed)
        graphs.append({
            "mechanicId": mechanic_id, "chapterId": raw_model.get("chapterId"), "name": raw_model.get("name"),
            "mechanicType": mechanic_type, "nodes": nodes, "edges": edges,
            "supportingRuleIds": raw_model.get("supportingRuleIds", []),
            "lifecycle": {"status": "applicable" if owns_state else "not_applicable",
                          "doesMechanicOwnPersistentState": owns_state, "lifecycleApplicabilityReason": reason},
            "contentAuthority": "approved_rule_only", "nonConfirmedNodesCanGenerateRule": False,
        })
    return graphs
