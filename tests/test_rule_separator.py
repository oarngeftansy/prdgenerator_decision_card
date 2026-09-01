from backend.atomic_fact_normalizer import normalize_claim
from backend.rule_separator import separate_atomic_fact


def test_mixed_damage_and_feedback_becomes_one_logic_and_two_presentation_rules():
    fact = normalize_claim({
        "id": "GCL-001", "sourceFrameIds": ["F0001"],
        "text": "敌人命中载具后立即扣除生命值，同时刷新生命条并显示本次伤害跳字。",
    }, "载具")
    rules = separate_atomic_fact(fact, "V2CH-001", "damage_death_definition")
    assert [rule.rule_type for rule in rules] == ["logic", "presentation", "presentation"]
    assert len({rule.semantic_key for rule in rules}) == 3
    assert all(rule.evidence_ids == ("F0001",) for rule in rules)
    assert "扣除" in rules[0].behavior
    assert "生命条" in rules[1].behavior
    assert "跳字" in rules[2].behavior


def test_atomic_fact_rule_keeps_one_domain_and_inferred_fact_needs_revision():
    observed, inferred = __import__("backend.atomic_fact_normalizer", fromlist=["normalize_claims"]).normalize_claims({
        "id": "GCL-LEVEL", "sourceFrameIds": ["F0007"],
        "text": "左上角显示当前等级（如10级），决定关卡节奏。",
    }, "关卡")
    observed_rule = separate_atomic_fact(observed, "V2CH-001", "presentation_definition")
    inferred_rule = separate_atomic_fact(inferred, "V2CH-001", "level_flow_definition")
    assert len(observed_rule) == 1 and observed_rule[0].rule_type == "presentation"
    assert inferred_rule[0].review_status == "needs_revision"
