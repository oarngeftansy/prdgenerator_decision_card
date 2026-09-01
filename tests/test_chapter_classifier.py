from backend.chapter_classifier import classify_text


def test_classifier_finds_attack_and_ranged_variant_from_evidence_not_title():
    result = classify_text("对象行为", ["敌人进入射程后自动索敌并发射投射物。"])
    assert result.chapter_type == "attack"
    assert result.mechanic_variant == "ranged"
    assert result.classification_evidence


def test_classifier_distinguishes_three_choice_and_roulette():
    a = classify_text("强化", ["升级后暂停并展示三张候选卡，选择一项生效。"])
    b = classify_text("抽取", ["老虎机九宫格滚动后在中线定格结果。"])
    assert (a.chapter_type, a.mechanic_variant) == ("randomization", "three_choice")
    assert (b.chapter_type, b.mechanic_variant) == ("randomization", "roulette")


def test_classifier_returns_unknown_without_mechanic_evidence():
    result = classify_text("其他说明", ["这里展示了一段内容。"])
    assert result.chapter_type == "unknown"
    assert result.matched_schema is None


def test_turn_flow_is_a_stable_cross_genre_chapter_type():
    result = classify_text("回合", ["行动点耗尽后结束当前回合并切换行动方。"])
    assert result.chapter_type == "level_flow"
    assert result.matched_schema == "chapter-schema-v2:level_flow:base"
