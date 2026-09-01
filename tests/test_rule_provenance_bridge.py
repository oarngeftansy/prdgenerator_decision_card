from backend.rule_provenance_bridge import build_rule_provenance_bridge, project_chains_to_synthesized_rules


def test_bridge_resolves_explicit_synthesis_lineage_and_keeps_many_to_many():
    synthesis_rules = [
        {"ruleId": "SYN-1", "sourceLineIds": ["LINE-A", "LINE-B"]},
        {"ruleId": "SYN-2", "sourceLineIds": ["LINE-B"]},
        {"ruleId": "SYN-UNMAPPED", "sourceLineIds": []},
    ]
    source_lines = [
        {"lineId": "LINE-A", "supportingRuleIds": ["RULE-1", "RULE-2"]},
        {"lineId": "LINE-B", "supportingRuleIds": ["RULE-2", "RULE-3"]},
    ]
    bridge = build_rule_provenance_bridge(synthesis_rules, source_lines)
    assert bridge["synToRules"]["SYN-1"] == ["RULE-1", "RULE-2", "RULE-3"]
    assert bridge["ruleToSyn"]["RULE-2"] == ["SYN-1", "SYN-2"]
    assert bridge["unmappedSynRuleIds"] == ["SYN-UNMAPPED"]
    assert bridge["mappings"][0]["basis"] == "explicit_synthesis_input_lineage"


def test_bridge_prefers_direct_structured_rule_lineage_without_source_lines():
    bridge = build_rule_provenance_bridge(
        [{"ruleId": "SYN-REQ-X", "sourceRuleIds": ["RULE-X", "RULE-Y"], "sourceLineIds": []}],
        [],
    )
    assert bridge["synToRules"]["SYN-REQ-X"] == ["RULE-X", "RULE-Y"]
    assert bridge["mappings"][0]["basis"] == "explicit_rule_lineage"


def test_real_chain_nodes_project_only_through_verified_bridge():
    bridge = {
        "ruleToSyn": {"RULE-1": ["SYN-1"], "RULE-2": ["SYN-2", "SYN-2B"]},
        "synToRules": {"SYN-1": ["RULE-1"], "SYN-2": ["RULE-2"], "SYN-2B": ["RULE-2"]},
    }
    chains = [{
        "chainId": "CHAIN-1", "chainType": "lifecycle", "entry": {"semantic": "enter", "ruleIds": ["RULE-1"]},
        "playerAction": [], "systemResponse": [{"semantic": "process", "ruleIds": ["RULE-2"]}],
        "stateChange": [], "progressionResult": [], "exitOrNext": [],
        "relationTypes": ["sequence", "state_transition"],
    }]
    projected = project_chains_to_synthesized_rules(chains, bridge)
    assert projected["SYN-1"][0]["chainPosition"] == 1
    assert projected["SYN-1"][0]["nodeRole"] == "entry"
    assert projected["SYN-1"][0]["successorSynRuleIds"] == ["SYN-2", "SYN-2B"]
    assert projected["SYN-2"][0]["predecessorSynRuleIds"] == ["SYN-1"]
    assert projected["SYN-2B"][0]["sourceRuleIds"] == ["RULE-2"]


def test_ordered_rule_chain_normalizes_adjacency_to_sequence_but_single_mapped_node_does_not():
    bridge = {"ruleToSyn": {"R1": ["S1"], "R2": ["S2"]}}
    chain = {"chainId": "C", "chainType": "flow", "entry": {"ruleIds": ["R1"]},
             "playerAction": [], "systemResponse": [{"ruleIds": ["R2"]}],
             "stateChange": [], "progressionResult": [], "exitOrNext": [], "relationTypes": []}
    projected = project_chains_to_synthesized_rules([chain], bridge)
    assert projected["S1"][0]["relationTypes"] == ["sequence"]
    single = project_chains_to_synthesized_rules([{**chain, "systemResponse": []}], bridge)
    assert single["S1"][0]["relationTypes"] == []
