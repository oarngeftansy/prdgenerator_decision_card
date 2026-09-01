from copy import deepcopy

from backend.logic_delivery import build_logic_only_delivery


CHAPTERS = [{"chapterId": "C1", "object": "怪物", "title": "攻击"}]
BLOCKS = [{
    "blockId": "MB-C1-01", "chapterId": "C1", "mechanismSemantic": "接触伤害",
    "status": "partial_mechanism_chain", "ruleIds": ["RL1", "RP1"],
    "definition": [], "input_constraint": [], "trigger": [], "condition": [],
    "target_selection": [],
    "processing": [{"text": "怪物接触载具后造成伤害", "ruleId": "RL1", "ruleType": "logic", "schemaSlot": "attack_trigger", "subject": "怪物", "semanticRole": "processing", "resolutionStatus": "executable"}],
    "effect": [], "state_change": [], "result": [], "exit_boundary": [],
    "presentation": [{"text": "敌人受击时显示伤害数字", "ruleId": "RP1", "ruleType": "presentation", "schemaSlot": "attack_presentation", "subject": "敌人", "semanticRole": "presentation", "resolutionStatus": "descriptive"}],
    "config_reference": [], "unabsorbedGapIds": ["G1"],
}]
VISUALS = [{"visualBlockId": "VIS-RP1", "relatedRuleIds": ["RP1"], "relatedLogicRuleIds": ["RL1"], "presentationDescription": "敌人受击时显示伤害数字"}]
STYLE = {"organization_rules": {"contextual_subject_omission": True}}


def test_logic_delivery_excludes_presentation_rules_and_text():
    delivery = build_logic_only_delivery(CHAPTERS, BLOCKS, VISUALS, STYLE)
    assert delivery["metrics"]["presentationRuleCountInExecution"] == 0
    assert "显示伤害数字" not in delivery["markdown"]
    assert "RP1" not in delivery["traceability"]["ruleToFinalParagraphs"]


def test_linked_logic_paragraph_keeps_visual_relation_in_json_not_markdown():
    delivery = build_logic_only_delivery(CHAPTERS, BLOCKS, VISUALS, STYLE)
    assert "相关表现见策划草图" not in delivery["markdown"]
    assert "VIS-RP1" not in delivery["markdown"]
    assert delivery["metrics"]["visualReferenceResolutionRate"] == 1.0
    paragraph = delivery["chapters"][0]["paragraphs"][0]
    assert paragraph["relatedVisualBlockIds"] == ["VIS-RP1"]
    assert delivery["traceability"]["logicRuleToVisualBlocks"] == {"RL1": ["VIS-RP1"]}


def test_unlinked_visual_block_is_not_forced_into_execution_text():
    visuals = [{**VISUALS[0], "relatedLogicRuleIds": []}]
    delivery = build_logic_only_delivery(CHAPTERS, BLOCKS, visuals, STYLE)
    assert "相关表现见策划草图" not in delivery["markdown"]
    assert delivery["metrics"]["visualReferenceCount"] == 0


def test_hard_gates_and_logic_traceability_pass():
    delivery = build_logic_only_delivery(CHAPTERS, BLOCKS, VISUALS, STYLE)
    assert delivery["metrics"]["presentationBackflowCount"] == 0
    assert delivery["metrics"]["gapRenderedAsConfirmedRuleCount"] == 0
    assert delivery["metrics"]["unsupportedSemanticAdditionCount"] == 0
    assert delivery["metrics"]["ruleToFinalOutputTraceability"] == 1.0


def test_sources_are_not_mutated():
    inputs = (CHAPTERS, BLOCKS, VISUALS, STYLE)
    before = deepcopy(inputs)
    build_logic_only_delivery(*inputs)
    assert inputs == before
