import pytest

from backend.atomic_fact_normalizer import normalize_claim, normalize_claims


def test_confirmed_atomic_fact_requires_evidence_and_preserves_traceability():
    fact = normalize_claim({"id": "GCL-001", "text": "敌人攻击命中载具后扣除生命值。", "sourceFrameIds": ["F0001"]}, "载具")
    assert fact.evidence_ids == ("F0001",)
    assert fact.review_status == "unreviewed"

    with pytest.raises(ValueError, match="evidence"):
        normalize_claim({"id": "GCL-002", "text": "载具死亡。", "reviewStatus": "confirmed"}, "载具")


def test_compound_claim_becomes_atomic_facts_with_shared_evidence():
    facts = normalize_claims({
        "id": "GCL-003", "sourceFrameIds": ["F0001"],
        "text": "敌人命中载具后扣除生命值，同时刷新生命条并显示伤害跳字。",
    }, "载具")
    assert len(facts) == 3
    assert all(fact.evidence_ids == ("F0001",) for fact in facts)


def test_business_semantics_split_spawn_move_and_contact_damage_without_fragments():
    facts = normalize_claims({
        "id": "GCL-MONSTER", "sourceFrameIds": ["F0001"],
        "text": "大量怪物从屏幕上方生成并向下移动，接触载具造成伤害。",
    }, "怪物")
    assert [(fact.subject, fact.predicate) for fact in facts] == [
        ("怪物", "生成"), ("怪物", "移动"), ("怪物", "触发伤害"),
    ]
    assert all(fact.review_status == "unreviewed" for fact in facts)
    assert all(not fact.validation_errors for fact in facts)


def test_observed_and_inferred_content_are_separated_and_inference_is_not_reviewable():
    facts = normalize_claims({
        "id": "GCL-LEVEL", "sourceFrameIds": ["F0007"],
        "text": "左上角显示当前等级（如10级），决定关卡节奏。",
    }, "关卡")
    assert [fact.evidence_level for fact in facts] == ["observed", "inferred"]
    assert facts[0].object == "当前等级"
    assert facts[1].review_status == "needs_revision"


def test_quotes_and_time_values_remain_intact_and_no_fact_starts_with_fragment():
    terminal = normalize_claims({
        "id": "GCL-ULT", "sourceFrameIds": ["F0005"],
        "text": "终极词条改变武器根本逻辑，如从单方向喷射变为“向4面喷射”，显著改变攻击范围。",
    }, "终极词条")
    settlement = normalize_claims({
        "id": "GCL-END", "sourceFrameIds": ["F0015"],
        "text": "通关后显示通关时间（05:14）及新纪录标识。",
    }, "结算")
    texts = [fact.source_text for fact in (*terminal, *settlement)]
    assert any("四向喷射" in text for text in texts)
    assert any("05:14" in text and "新纪录" in text for text in texts)
    assert all(not text.startswith(("的", "间", "点", "向4")) for text in texts)


def test_refresh_ambiguous_evidence_does_not_invent_resource_type():
    facts = normalize_claims({
        "id": "C-refresh", "text": "刷新允许玩家消耗资源或观看广告重置当前三个选项。", "sourceFrameIds": ["F1"]
    }, "三选一")
    serialized = " ".join(fact.source_text for fact in facts)
    assert "局内资源" not in serialized
    assert "消耗或替代条件" in serialized
