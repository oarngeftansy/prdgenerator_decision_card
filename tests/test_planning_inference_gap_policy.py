from backend.document_assembler import build_final_document, document_to_markdown
from backend.rule_intelligence_pipeline import build_rule_intelligence_projection


def _rule(rule_id, behavior, *, intent, slot, subject="系统", chapter="C1"):
    return {
        "ruleId": rule_id,
        "subject": subject,
        "behavior": behavior,
        "intent": intent,
        "schemaSlot": slot,
        "ownerChapterId": chapter,
        "reviewStatus": "approved",
        "semanticValidity": "valid",
        "evidenceIds": [f"E-{rule_id}"],
        "sourceFactIds": [f"F-{rule_id}"],
    }


def _projection(rules, *, chapters=None, gaps=None):
    return build_rule_intelligence_projection(
        approved_data={"rules": rules, "facts": [], "parameters": [], "gaps": gaps or []},
        chapters=chapters or [{"chapterId": "C1", "chapterType": "attack", "title": "攻击"}],
    )


def test_t1_safe_closure_inference_reselects_after_confirmed_target_death():
    result = _projection([
        _rule("TARGET", "武器选择唯一存活敌人作为目标", intent="TargetSelection", slot="attack_target", subject="武器"),
        _rule("DEATH", "敌人生命值归零后死亡", intent="Death", slot="death_condition", subject="敌人"),
    ])

    inferred = next(rule for rule in result["plannerInferences"] if rule["intent"] == "TargetSelection")
    assert inferred["inferenceLevel"] == "planner_inference"
    assert inferred["inferencePermission"] == "infer_and_publish"
    assert set(inferred["sourceRuleIds"]) == {"TARGET", "DEATH"}
    assert set(inferred["sourceFactIds"]) == {"F-TARGET", "F-DEATH"}
    assert "重新选择目标" in inferred["behavior"]
    assert inferred["ruleId"] in {rule["ruleId"] for rule in result["publication"]["rules"]}


def test_safe_closure_does_not_join_unrelated_rules_across_chapters():
    result = _projection([
        _rule("TARGET", "武器选择敌人作为目标", intent="TargetSelection", slot="attack_target", chapter="WEAPON"),
        _rule("DEATH", "护送对象生命值归零后死亡", intent="Death", slot="death_condition", chapter="ESCORT"),
    ], chapters=[
        {"chapterId": "WEAPON", "chapterType": "attack", "title": "武器攻击"},
        {"chapterId": "ESCORT", "chapterType": "damage_death", "title": "护送对象死亡"},
    ])

    assert not result["plannerInferences"]


def test_t2_technical_and_generic_schema_questions_remain_auditable_but_not_in_final():
    technical = {
        "gapId": "G-TECH", "chapterId": "C1", "schemaSlot": "movement_speed_source",
        "severity": "implementation_blocking", "status": "reviewed_open",
        "question": "移动速度读取哪个配置字段？", "gapDomain": "technical",
    }
    planning = {
        "gapId": "G-PLAN", "chapterId": "C1", "schemaSlot": "victory_condition",
        "severity": "implementation_blocking", "status": "reviewed_open",
        "question": "满足什么条件时判定胜利？", "gapDomain": "planning",
    }
    document = build_final_document({
        "rules": [], "gaps": [technical, planning],
        "chapters": [{"chapterId": "C1", "title": "胜负判定", "system": "关卡", "object": "关卡"}],
    })
    text = document_to_markdown(document)

    assert "满足什么条件时判定胜利" not in text
    assert "配置字段" not in text


def test_t3_optional_weight_without_weight_evidence_is_not_blocking_gap():
    result = _projection([
        _rule("DRAW", "升级时生成三张候选卡", intent="CandidateGeneration", slot="random_trigger"),
    ], chapters=[{
        "chapterId": "C1", "chapterType": "randomization", "mechanicVariant": "three_choice",
        "title": "三选一", "schemaResponsibilities": ["candidate_generation"],
    }])

    closure = result["closures"][0]
    assert closure["slots"]["WeightRule"] == "not_observed"
    assert not any(gap.get("schemaSlot") == "WeightRule" for gap in result["gaps"])


def test_t4_sufficient_context_creates_review_proposal_not_blank_question():
    result = _projection([
        _rule("PAUSE", "进入候选选择界面时暂停战斗", intent="CandidateGeneration", slot="selection_pause"),
        _rule("SELECT", "玩家确认一个候选项", intent="CandidateGeneration", slot="candidate_selection"),
    ], chapters=[{
        "chapterId": "C1", "chapterType": "randomization", "mechanicVariant": "three_choice",
        "title": "三选一", "schemaResponsibilities": ["candidate_generation"],
    }])

    proposal = next(item for item in result["reviewProposals"] if item["proposedRule"]["schemaSlot"] == "selection_exit")
    assert proposal["reviewStatus"] == "unreviewed"
    assert proposal["proposedRule"]["publicationEligibility"] == "review_required"
    assert "恢复战斗" in proposal["proposedRule"]["behavior"]
    assert proposal["proposedRule"]["ruleId"] not in {rule["ruleId"] for rule in result["publication"]["rules"]}
    assert proposal["proposedRule"]["ruleId"] in {
        rule["ruleId"] for rule in result["reviewProjection"]["chapters"][0]["ruleDefinitions"]
    }


def test_t5_high_risk_random_guard_still_blocks_unsupported_mechanics():
    result = _projection([
        _rule("DRAW", "系统随机抽取候选", intent="CandidateGeneration", slot="random_trigger"),
        _rule("UNSAFE", "候选等概率无放回抽取并设置保底", intent="CandidateGeneration", slot="sampling_rule"),
    ])

    unsafe = next(rule for rule in result["rules"] if rule["ruleId"] == "UNSAFE")
    assert unsafe["publicationEligibility"] == "blocked"
    assert "unsupported_random_mechanic" in unsafe["guardReasons"]
    assert not any(term in rule["behavior"] for rule in result["plannerInferences"] for term in ("等概率", "无放回", "权重", "保底"))


def test_t6_unknown_victory_condition_remains_planning_blocker():
    result = _projection([], chapters=[{
        "chapterId": "C1", "chapterType": "level_flow", "title": "胜负判定",
        "schemaResponsibilities": ["victory_condition", "failure_condition", "result_transition"],
    }])

    victory = next(gap for gap in result["gaps"] if gap.get("intent") == "VictoryCondition")
    assert victory["gapDomain"] == "planning"
    assert victory["inferencePermission"] == "evidence_required"
    assert victory["severity"] == "implementation_blocking"
    assert victory["blockingScope"] == "chapter"
