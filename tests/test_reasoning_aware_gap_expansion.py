from backend.reasoning_gap_expander import expand_reasoning_gaps, validate_reasoning_gap
from backend.reasoning_gap_quality_evaluator import evaluate_reasoning_gap_quality


def _node(node_id, semantic, node_type="processing", status="confirmed"):
    return {"nodeId": node_id, "semantic": semantic, "nodeType": node_type, "status": status,
            "supportingRuleIds": [f"R-{node_id}"] if status == "confirmed" else [],
            "supportingGapIds": [], "supportingEvidenceIds": [f"E-{node_id}"] if status == "confirmed" else []}


def _graph(mechanic_type="attack", nodes=(), edges=(), mechanic_id="M1", templates=100):
    return {"mechanicId": mechanic_id, "chapterId": "C1", "name": "测试", "mechanicType": mechanic_type,
            "nodes": list(nodes), "edges": list(edges), "supportingRuleIds": [rule for node in nodes for rule in node.get("supportingRuleIds", [])],
            "templateSlotCount": templates, "lifecycle": {"status": "not_applicable"}}


def test_template_slots_and_hypothesis_only_graph_do_not_create_gaps():
    graph = _graph(nodes=[_node("H1", "attack_trigger", "condition", "hypothesis")], templates=999)
    result = expand_reasoning_gaps([graph], [])
    assert result["reasoningGaps"] == []
    assert result["mechanisms"][0]["suppressionReason"] == "no_grounded_breakpoint"


def test_contact_damage_breakpoint_generates_specific_program_and_qa_questions():
    graph = _graph(nodes=[_node("C", "attack_trigger", "condition"), _node("D", "damage_output", "result")],
                   edges=[{"fromNodeId": "C", "toNodeId": "D", "relationType": "triggers", "evidenceStatus": "confirmed", "supportingRuleIds": ["R-C"]}])
    result = expand_reasoning_gaps([graph], [])
    questions = [gap["question"] for gap in result["reasoningGaps"]]
    assert "怪物与目标接触后，伤害是仅结算一次，还是在持续接触期间重复结算？" in questions
    assert any("多只怪物" in question and "独立结算" in question for question in questions)
    assert all(gap["sourceNodeIds"] and gap["implementationImpact"] and gap["qaImpact"] for gap in result["reasoningGaps"])


def test_hypothesis_node_cannot_independently_trigger_blocking_gap():
    graph = _graph(nodes=[_node("C", "attack_trigger", "condition"), _node("H", "exit_condition", "exit_condition", "hypothesis")])
    result = expand_reasoning_gaps([graph], [])
    assert all("H" not in gap["sourceNodeIds"] for gap in result["reasoningGaps"] if gap["blockingLevel"] == "P0 implementation_blocking")


def test_synonymous_existing_gaps_merge_to_one_primary_gap():
    graph = _graph(nodes=[_node("C", "attack_trigger", "condition"), _node("D", "damage_output", "result")],
                   edges=[{"fromNodeId": "C", "toNodeId": "D", "relationType": "triggers", "evidenceStatus": "confirmed", "supportingRuleIds": ["R-C"]}])
    existing = [
        {"gapId": "G1", "chapterId": "C1", "schemaSlot": "damage_interval", "question": "攻击多久结算一次？", "status": "open"},
        {"gapId": "G2", "chapterId": "C1", "schemaSlot": "damage_interval", "question": "持续接触伤害的时间间隔是多少？", "status": "open"},
    ]
    result = expand_reasoning_gaps([graph], existing)
    interval = [gap for gap in result["reasoningGaps"] if gap["semanticKey"].endswith("damage_interval")]
    assert len(interval) == 1
    assert interval[0]["existingGapIds"] == ["G1", "G2"]


def test_generic_question_fails_quality_gate_and_unbound_gap_is_invalid():
    gap = {"gapId": "RG1", "mechanicId": "M1", "sourceNodeIds": [], "missingNodeSemantic": "processing",
           "missingRelation": None, "gapType": "processing", "question": "怪物攻击规则是什么？",
           "implementationImpact": "", "qaImpact": "", "blockingLevel": "P0 implementation_blocking",
           "evidenceBasis": [], "derivationReason": "", "ownerLayer": "Gap", "semanticKey": "M1:generic"}
    graph = _graph(nodes=[_node("C", "attack_trigger", "condition")])
    validation = validate_reasoning_gap(gap, graph)
    assert validation["valid"] is False
    assert {finding["code"] for finding in validation["findings"]} >= {"generic_question", "breakpoint_not_grounded"}


def test_five_specific_grounded_gaps_outscore_twenty_generic_unbound_gaps():
    graph = _graph(nodes=[_node("C", "attack_trigger", "condition"), _node("D", "damage_output", "result")],
                   edges=[{"fromNodeId": "C", "toNodeId": "D", "relationType": "triggers", "evidenceStatus": "confirmed", "supportingRuleIds": ["R-C"]}])
    good = expand_reasoning_gaps([graph], [])["reasoningGaps"][:5]
    bad = [{"gapId": f"B{i}", "mechanicId": "M1", "sourceNodeIds": [], "missingNodeSemantic": "processing",
            "missingRelation": None, "gapType": "processing", "question": "攻击规则是什么？", "implementationImpact": "",
            "qaImpact": "", "blockingLevel": "P0 implementation_blocking", "evidenceBasis": [], "derivationReason": "",
            "ownerLayer": "Gap", "semanticKey": f"bad:{i}"} for i in range(20)]
    assert evaluate_reasoning_gap_quality(good, [graph])["total"] > evaluate_reasoning_gap_quality(bad, [graph])["total"]


def test_gap_cannot_claim_a_confirmed_node_is_missing():
    graph = _graph(nodes=[_node("C", "attack_trigger", "condition"), _node("D", "damage_output", "result")])
    gap = {"gapId": "RG1", "mechanicId": "M1", "sourceNodeIds": ["C"], "missingNodeSemantic": "damage_output",
           "missingRelation": "produces", "gapType": "result", "question": "伤害结果写入哪个已确认对象？",
           "implementationImpact": "决定写入对象。", "qaImpact": "验证写入结果。", "blockingLevel": "P0 implementation_blocking",
           "evidenceBasis": ["R-C"], "derivationReason": "结果对象尚未定义。", "ownerLayer": "Gap", "semanticKey": "M1:result"}
    assert "breakpoint_already_resolved" in {item["code"] for item in validate_reasoning_gap(gap, graph)["findings"]}
