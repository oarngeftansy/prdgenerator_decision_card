from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_rule_provenance_bridge(synthesis_rules: list[dict[str, Any]],
                                 source_lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Resolve only explicit synthesis input lineage; no semantic matching is allowed."""
    lines = {line["lineId"]: line for line in source_lines if line.get("lineId")}
    syn_to_rules: dict[str, list[str]] = {}
    rule_to_syn: dict[str, list[str]] = defaultdict(list)
    mappings = []
    unmapped = []
    for synthesis_rule in synthesis_rules:
        syn_id = synthesis_rule["ruleId"]
        source_line_ids = [line_id for line_id in synthesis_rule.get("sourceLineIds", []) if line_id in lines]
        direct_rule_ids = [rule_id for rule_id in synthesis_rule.get("sourceRuleIds", [])
                           if str(rule_id).startswith("RULE-")]
        line_rule_ids = list(dict.fromkeys(
            rule_id for line_id in source_line_ids
            for rule_id in lines[line_id].get("supportingRuleIds", [])
            if str(rule_id).startswith("RULE-")
        ))
        source_rule_ids = list(dict.fromkeys(direct_rule_ids + line_rule_ids))
        syn_to_rules[syn_id] = source_rule_ids
        if not source_rule_ids:
            unmapped.append(syn_id)
            continue
        mappings.append({
            "synRuleId": syn_id, "sourceRuleIds": source_rule_ids,
            "sourceLineIds": source_line_ids,
            "basis": "explicit_rule_lineage" if direct_rule_ids else "explicit_synthesis_input_lineage",
        })
        for rule_id in source_rule_ids:
            rule_to_syn[rule_id].append(syn_id)
    return {
        "mappings": mappings,
        "synToRules": syn_to_rules,
        "ruleToSyn": {rule_id: list(dict.fromkeys(syn_ids)) for rule_id, syn_ids in rule_to_syn.items()},
        "unmappedSynRuleIds": unmapped,
    }


def project_chains_to_synthesized_rules(chains: list[dict[str, Any]],
                                        bridge: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    projected: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rule_to_syn = bridge.get("ruleToSyn", {})
    sections = (
        ("entry", lambda chain: [chain["entry"]] if chain.get("entry") else []),
        ("player_action", lambda chain: chain.get("playerAction", [])),
        ("system_response", lambda chain: chain.get("systemResponse", [])),
        ("state_change", lambda chain: chain.get("stateChange", [])),
        ("progression_result", lambda chain: chain.get("progressionResult", [])),
        ("exit", lambda chain: chain.get("exitOrNext", [])),
    )
    for chain in chains:
        nodes = [(role, node) for role, getter in sections for node in getter(chain)]
        mapped_nodes = []
        for position, (role, node) in enumerate(nodes, 1):
            syn_ids = list(dict.fromkeys(
                syn_id for rule_id in node.get("ruleIds", []) for syn_id in rule_to_syn.get(rule_id, [])
            ))
            if syn_ids:
                mapped_nodes.append((position, role, node, syn_ids))
        for index, (position, role, node, syn_ids) in enumerate(mapped_nodes):
            predecessor = mapped_nodes[index - 1][3] if index else []
            successor = mapped_nodes[index + 1][3] if index + 1 < len(mapped_nodes) else []
            relation_types = list(chain.get("relationTypes", []))
            if len(mapped_nodes) > 1 and "sequence" not in relation_types:
                relation_types.insert(0, "sequence")
            for syn_id in syn_ids:
                projected[syn_id].append({
                    "chainId": chain["chainId"], "chainType": chain.get("chainType"),
                    "chainPosition": position, "nodeRole": role, "nodeSemantic": node.get("semantic"),
                    "sourceRuleIds": list(node.get("ruleIds", [])),
                    "predecessorSynRuleIds": [item for item in predecessor if item != syn_id],
                    "successorSynRuleIds": [item for item in successor if item != syn_id],
                    "relationTypes": relation_types,
                    "terminal": role == "exit", "resetRelation": "reset" in chain.get("relationTypes", []),
                })
    return dict(projected)
