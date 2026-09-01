from copy import deepcopy

import pytest

from backend.visual_delivery import build_visual_blocks


PRESENTATION = {
    "ruleId": "RP1", "ruleType": "presentation", "reviewStatus": "approved",
    "semanticValidity": "valid", "schemaSlot": "damage_death_definition",
    "ownerChapterId": "C1", "subject": "怪物", "behavior": "怪物显示生命条",
    "evidenceIds": ["EV1"],
}
LOGIC = {
    "ruleId": "RL1", "ruleType": "logic", "reviewStatus": "approved",
    "semanticValidity": "valid", "schemaSlot": "damage_death_definition",
    "ownerChapterId": "C1", "subject": "怪物", "behavior": "怪物受击后减少当前生命值",
    "evidenceIds": ["EV1"],
}
GRAPH = {
    "entities": [{"entityId": "ENT-MONSTER", "relatedRuleIds": ["RL1"]}],
    "presentationRuleReferences": [{"ruleId": "RP1", "relatedEntityIds": ["ENT-MONSTER"]}],
}
EVIDENCE = {
    "EV1": {"screenshotIds": ["SHOT-001"]},
    "screenshots": {"SHOT-001": {"kind": "screenshot", "screen": "战斗", "state": "受击"}},
}


def test_each_presentation_rule_becomes_one_stable_block_using_audited_entities():
    blocks = build_visual_blocks([PRESENTATION], [LOGIC], GRAPH, EVIDENCE)
    assert blocks[0]["visualBlockId"] == "VIS-RP1"
    assert blocks[0]["relatedEntityIds"] == ["ENT-MONSTER"]
    assert blocks[0]["relatedRuleIds"] == ["RP1"]
    assert blocks[0]["presentationDescription"] == PRESENTATION["behavior"]


def test_derived_logic_link_requires_entity_semantic_and_evidence_together():
    block = build_visual_blocks([PRESENTATION], [LOGIC], GRAPH, EVIDENCE)[0]
    assert block["relatedLogicRuleIds"] == ["RL1"]

    disjoint = {**LOGIC, "evidenceIds": ["EV2"]}
    assert build_visual_blocks([PRESENTATION], [disjoint], GRAPH, EVIDENCE)[0]["relatedLogicRuleIds"] == []

    incompatible = {**LOGIC, "schemaSlot": "movement_trigger"}
    assert build_visual_blocks([PRESENTATION], [incompatible], GRAPH, EVIDENCE)[0]["relatedLogicRuleIds"] == []

    graph_without_logic_entity = deepcopy(GRAPH)
    graph_without_logic_entity["entities"][0]["relatedRuleIds"] = []
    assert build_visual_blocks([PRESENTATION], [LOGIC], graph_without_logic_entity, EVIDENCE)[0]["relatedLogicRuleIds"] == []

    cross_chapter = {**LOGIC, "ownerChapterId": "C2"}
    assert build_visual_blocks([PRESENTATION], [cross_chapter], GRAPH, EVIDENCE)[0]["relatedLogicRuleIds"] == []


def test_broad_attack_presentation_is_not_treated_as_a_deterministic_mechanism_link():
    presentation = {**PRESENTATION, "schemaSlot": "attack_presentation"}
    logic = {**LOGIC, "schemaSlot": "attack_trigger"}
    assert build_visual_blocks([presentation], [logic], GRAPH, EVIDENCE)[0]["relatedLogicRuleIds"] == []


def test_explicit_logic_rule_id_has_precedence_but_must_be_approved_non_presentation():
    presentation = {**PRESENTATION, "relatedLogicRuleIds": ["RL1"]}
    logic = {**LOGIC, "evidenceIds": ["OTHER"], "schemaSlot": "movement_trigger"}
    assert build_visual_blocks([presentation], [logic], GRAPH, EVIDENCE)[0]["relatedLogicRuleIds"] == ["RL1"]

    invalid = {**logic, "ruleType": "presentation"}
    with pytest.raises(ValueError, match="explicit Logic Rule"):
        build_visual_blocks([presentation], [invalid], GRAPH, EVIDENCE)


def test_screenshot_ids_only_come_from_explicit_screenshot_registry():
    block = build_visual_blocks([PRESENTATION], [LOGIC], GRAPH, EVIDENCE)[0]
    assert block["sourceScreenshotIds"] == ["SHOT-001"]
    assert "EV1" not in block["sourceScreenshotIds"]
    assert block["screen"] == "战斗"
    assert block["state"] == "受击"


def test_missing_or_unknown_audited_entity_is_a_hard_error():
    with pytest.raises(ValueError, match="audited Entity"):
        build_visual_blocks([PRESENTATION], [LOGIC], {**GRAPH, "presentationRuleReferences": []}, EVIDENCE)
    bad_graph = deepcopy(GRAPH)
    bad_graph["presentationRuleReferences"][0]["relatedEntityIds"] = ["ENT-UNKNOWN"]
    with pytest.raises(ValueError, match="audited Entity"):
        build_visual_blocks([PRESENTATION], [LOGIC], bad_graph, EVIDENCE)


def test_inputs_are_not_mutated():
    inputs = ([PRESENTATION], [LOGIC], GRAPH, EVIDENCE)
    before = deepcopy(inputs)
    build_visual_blocks(*inputs)
    assert inputs == before
