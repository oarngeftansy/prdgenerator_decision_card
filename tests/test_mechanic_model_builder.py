from copy import deepcopy
from pathlib import Path

from backend.mechanic_model_builder import build_mechanic_models
from backend.mechanic_structure_corpus import load_mechanic_structure_corpus


ROOT = Path(__file__).resolve().parents[1]
CORPUS = load_mechanic_structure_corpus(ROOT / "data/quality/gve16-mechanic-structure-corpus-v1.json")

CHAPTERS = [{
    "chapterId": "C-ATTACK", "object": "武器", "title": "攻击",
    "chapterType": "attack", "mechanicVariant": "ranged", "matchedSchema": "attack:ranged",
}]
RULES = [
    {"ruleId": "R-INPUT", "ownerChapterId": "C-ATTACK", "ruleType": "logic", "schemaSlot": "attack_trigger", "subject": "武器", "behavior": "武器无需玩家手动瞄准", "reviewStatus": "approved", "semanticValidity": "valid", "sourceFactIds": ["F1"]},
    {"ruleId": "R-TARGET", "ownerChapterId": "C-ATTACK", "ruleType": "logic", "schemaSlot": "attack_target", "subject": "武器", "behavior": "武器选择射程内敌人作为攻击目标", "reviewStatus": "approved", "semanticValidity": "valid", "sourceFactIds": ["F2"]},
    {"ruleId": "R-EXECUTE", "ownerChapterId": "C-ATTACK", "ruleType": "logic", "schemaSlot": "attack_target", "subject": "武器", "behavior": "武器向目标发射投射物", "reviewStatus": "approved", "semanticValidity": "valid", "sourceFactIds": ["F3"]},
    {"ruleId": "R-PRESENTATION", "ownerChapterId": "C-ATTACK", "ruleType": "presentation", "schemaSlot": "attack_presentation", "subject": "投射物", "behavior": "显示飞行轨迹", "reviewStatus": "approved", "semanticValidity": "valid", "sourceFactIds": ["F4"]},
]
GAPS = [
    {"gapId": "G-RANGE", "chapterId": "C-ATTACK", "schemaSlot": "attack_range", "question": "攻击距离如何确定？", "status": "open"},
    {"gapId": "G-EXIT", "chapterId": "C-ATTACK", "schemaSlot": "attack_exit_condition", "question": "何时退出攻击状态？", "status": "open"},
]
GRAPH = {"entities": [{"entityId": "E-WEAPON", "name": "武器", "relatedRuleIds": ["R-INPUT", "R-TARGET", "R-EXECUTE"]}]}


def test_attack_model_separates_confirmed_structure_and_unresolved_nodes_without_inventing_content():
    models = build_mechanic_models(CHAPTERS, RULES, GAPS, {}, GRAPH, CORPUS)
    model = models[0]
    nodes = {node["nodeKey"]: node for node in model["nodes"]}

    assert nodes["attack_input_mode"]["status"] == "confirmed"
    assert nodes["attack_target_select"]["supportingRuleIds"] == ["R-TARGET"]
    assert nodes["attack_execute"]["supportingRuleIds"] == ["R-EXECUTE"]
    assert nodes["attack_precondition"]["status"] == "unresolved"
    assert nodes["attack_precondition"]["supportingGapIds"] == ["G-RANGE"]
    assert nodes["attack_precondition"]["content"] is None
    assert nodes["attack_target_set"]["status"] == "inferred_structure"
    assert nodes["attack_target_set"]["content"] is None
    assert "R-PRESENTATION" not in model["supportingRuleIds"]
    assert set(model["actors"]) == {"武器", "E-WEAPON"}


def test_builder_is_read_only_and_does_not_promote_structure_to_rules_or_close_gaps():
    inputs = (CHAPTERS, RULES, GAPS, {}, GRAPH)
    before = deepcopy(inputs)
    models = build_mechanic_models(*inputs, CORPUS)

    assert inputs == before
    assert all(node["content"] is None for model in models for node in model["inferredNodes"] + model["unresolvedNodes"])
    assert GAPS[0]["status"] == "open"
    assert RULES[0]["reviewStatus"] == "approved"
