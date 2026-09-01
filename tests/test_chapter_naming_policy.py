from backend.chapter_naming_policy import ChapterNamingInput, chapter_naming_policy


def test_naming_uses_stable_rule_category_and_omits_internal_variant():
    result = chapter_naming_policy.name(ChapterNamingInput(
        level=3, system_name="核心战斗", object_name="武器", chapter_type="attack",
        mechanic_variant="ranged", user_visible_variant_name=None,
        legacy_title="武器命中、反馈与伤害归集",
    ))
    assert result.title == "攻击"
    assert result.title_split is True
    assert result.quality_issues == ()


def test_naming_allows_fixed_business_concept_but_rejects_summary_title():
    assert chapter_naming_policy.inspect("解锁与养成", "unlock_progression") == ()
    issues = chapter_naming_policy.inspect("攻击、养成与词条生效", "attack")
    assert "parallel_connectors" in issues
    assert "multiple_actions" in issues


def test_user_visible_variant_can_name_object_but_internal_variant_cannot():
    visible = chapter_naming_policy.name(ChapterNamingInput(
        level=2, system_name="局内成长", object_name=None, chapter_type="randomization",
        mechanic_variant="three_choice", user_visible_variant_name="三选一", legacy_title="候选、刷新与确认",
    ))
    assert visible.title == "三选一"
