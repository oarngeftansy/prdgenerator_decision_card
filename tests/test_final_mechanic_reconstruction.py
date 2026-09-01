from backend.document_assembler import build_final_document, document_to_markdown
from backend.gameplay_render import authoritative_gameplay_model
from backend.rule_intelligence_pipeline import build_rule_intelligence_projection


def _rule(rule_id, behavior, *, intent, slot, subject, chapter):
    return {
        "ruleId": rule_id,
        "behavior": behavior,
        "intent": intent,
        "schemaSlot": slot,
        "ruleType": "logic",
        "subject": subject,
        "ownerChapterId": chapter,
        "reviewStatus": "approved",
        "semanticValidity": "valid",
        "evidenceIds": [f"E-{rule_id}"],
        "sourceFactIds": [f"F-{rule_id}"],
    }


def _projection(rules, chapters, gaps=None):
    return build_rule_intelligence_projection(
        approved_data={"rules": rules, "facts": [], "parameters": [], "gaps": gaps or []},
        chapters=chapters,
    )


def test_reconstructs_contact_damage_mechanic_without_targeting_questionnaire():
    chapters = [{"chapterId": "MONSTER", "title": "普通怪物", "entityScope": ["普通怪物"]}]
    result = _projection([
        _rule("S", "普通怪物从屏幕上方生成", intent="Spawn", slot="spawn_source", subject="普通怪物", chapter="MONSTER"),
        _rule("M", "普通怪物生成后向下移动", intent="Movement", slot="movement_direction", subject="普通怪物", chapter="MONSTER"),
        _rule("D", "普通怪物接触载具后造成伤害", intent="Damage", slot="damage", subject="普通怪物", chapter="MONSTER"),
    ], chapters, gaps=[{
        "gapId": "G-TARGET", "chapterId": "MONSTER", "schemaSlot": "attack_target",
        "question": "怪物如何选择攻击目标？", "status": "reviewed_open", "gapDomain": "planning",
    }])

    flow = result["publication"]["mechanicFlows"][0]
    assert [step["ruleId"] for step in flow["steps"]] == ["S", "M", "D"]
    assert result["publication"]["finalPlanningGaps"] == []
    assert result["reconstructionAudit"]["schemaQuestionsSuppressed"] == 1


def test_contact_damage_rewrites_attack_exit_template_into_specific_planning_decision():
    chapters = [{"chapterId": "MONSTER", "title": "普通怪物", "entityScope": ["普通怪物"]}]
    result = _projection([
        _rule("S", "普通怪物从屏幕上方生成", intent="Spawn", slot="spawn_source", subject="普通怪物", chapter="MONSTER"),
        _rule("M", "普通怪物生成后向下移动", intent="Movement", slot="movement_direction", subject="普通怪物", chapter="MONSTER"),
        _rule("D", "普通怪物接触载具后造成伤害", intent="Damage", slot="damage", subject="普通怪物", chapter="MONSTER"),
    ], chapters, gaps=[{
        "gapId": "G-EXIT", "chapterId": "MONSTER", "schemaSlot": "attack_exit",
        "question": "怪物在什么条件下退出攻击状态？", "status": "reviewed_open", "gapDomain": "planning",
    }])

    assert [gap["schemaSlot"] for gap in result["publication"]["finalPlanningGaps"]] == ["contact_resolution"]
    assert "继续移动、停留攻击，还是离开战场" in result["publication"]["finalPlanningGaps"][0]["question"]
    assert result["publication"]["finalPlanningGaps"][0]["finalRequirementClass"] == "player_visible_design_decision"


def test_default_death_count_and_clear_timing_stays_internal_without_becoming_final_gap():
    chapters = [{"chapterId": "MONSTER", "title": "普通怪物", "entityScope": ["普通怪物"]}]
    result = _projection([
        _rule("S", "普通怪物从场外生成", intent="Spawn", slot="spawn_source", subject="普通怪物", chapter="MONSTER"),
        _rule("M", "普通怪物生成后向目标移动", intent="Movement", slot="movement_direction", subject="普通怪物", chapter="MONSTER"),
        _rule("D", "普通怪物接触目标后造成伤害", intent="Damage", slot="damage", subject="普通怪物", chapter="MONSTER"),
    ], chapters, gaps=[{
        "gapId": "G-CLEAR", "chapterId": "MONSTER", "gapKind": "unresolved_mechanic_reference",
        "referenceKind": "remaining_count_zero", "status": "reviewed_open", "gapDomain": "planning",
        "applicabilityStatus": "applicable", "specificity": "concrete_decision",
        "question": "普通敌人死亡后何时移除并计入剩余数量，确保清空条件可以判定？",
    }])

    internal = next(gap for gap in result["gaps"] if gap["gapId"] == "G-CLEAR")
    assert internal["finalRequirementClass"] == "implicit_system_semantics"
    assert internal["finalPublicationRequired"] is False
    assert not any(gap["gapId"] == "G-CLEAR" for gap in result["publication"]["finalPlanningGaps"])
    assert result["reconstructionAudit"]["implicitSystemSemanticGapsSuppressed"] == 1


def test_special_death_state_behavior_remains_a_publishable_planning_gap():
    chapters = [{"chapterId": "MONSTER", "title": "普通怪物", "entityScope": ["普通怪物"]}]
    result = _projection([], chapters, gaps=[{
        "gapId": "G-CORPSE", "chapterId": "MONSTER", "gapKind": "unresolved_mechanic_reference",
        "referenceKind": "remaining_count_zero", "status": "reviewed_open", "gapDomain": "planning",
        "applicabilityStatus": "applicable", "specificity": "concrete_decision",
        "question": "死亡动画期间尸体是否继续占位并计入存活数量？",
    }])

    gap = next(gap for gap in result["publication"]["finalPlanningGaps"] if gap["gapId"] == "G-CORPSE")
    assert gap["finalRequirementClass"] == "special_project_behavior"
    assert gap["finalPublicationRequired"] is True


def test_recovers_cross_section_victory_rule_to_semantic_owner():
    chapters = [
        {"chapterId": "BOSS", "title": "首领", "system": "关卡", "entityScope": ["首领"]},
        {"chapterId": "RESULT", "title": "胜负判定", "system": "关卡", "entityScope": ["关卡"]},
    ]
    result = _projection([
        _rule("WIN", "首领死亡且剩余普通怪物清空后挑战成功", intent="VictoryCondition", slot="victory_condition", subject="关卡", chapter="BOSS"),
        _rule("FAIL", "载具生命值归零后挑战失败", intent="FailureCondition", slot="failure_condition", subject="关卡", chapter="RESULT"),
    ], chapters)

    win = next(rule for rule in result["publication"]["rules"] if rule["ruleId"] == "WIN")
    assert win["canonicalOwner"] == "RESULT"
    boss = next(chapter for chapter in result["publication"]["chapters"] if chapter["chapterId"] == "BOSS")
    assert [rule["ruleId"] for rule in boss["references"]] == ["WIN"]
    assert result["reconstructionAudit"]["crossSectionRecoveredRules"] == 1


def test_candidate_types_are_explicit_and_generic_candidate_nouns_are_not_a_complete_mechanism():
    chapters = [{"chapterId": "DRAW", "title": "三选一", "entityScope": ["三选一"]}]
    result = _projection([
        _rule("NEW", "三选一中可获得新武器", intent="CandidateGeneration", slot="candidate_pool_source", subject="三选一", chapter="DRAW"),
        _rule("UP", "三选一中可选择武器强化或词条", intent="CandidateGeneration", slot="candidate_pool_source", subject="三选一", chapter="DRAW"),
    ], chapters)

    mechanism = result["publication"]["mechanicFlows"][0]
    assert mechanism["candidateTypes"] == ["NewWeapon", "WeaponUpgradeOrModifier"]
    assert result["reconstructionAudit"]["genericCandidateAbstractionsResolved"] == 1


def test_entity_scope_mismatch_is_reassigned_and_never_leaks_into_normal_monster():
    chapters = [
        {"chapterId": "NORMAL", "title": "普通怪物", "entityScope": ["普通怪物"]},
        {"chapterId": "BOSS", "title": "首领", "entityScope": ["首领"]},
    ]
    result = _projection([
        _rule("BOSS-RULE", "首领展示不同攻击形态", intent="AttackMode", slot="attack_method", subject="首领", chapter="NORMAL"),
    ], chapters)

    rule = next(rule for rule in result["publication"]["rules"] if rule["ruleId"] == "BOSS-RULE")
    assert rule["canonicalOwner"] == "BOSS"
    assert result["reconstructionAudit"]["entityScopeViolations"] == 0
    assert result["reconstructionAudit"]["entityScopeReassignments"] == 1


def test_final_suppresses_schema_question_and_technical_gap_but_keeps_specific_planning_gap():
    document = build_final_document({
        "rules": [_rule("D", "普通怪物接触载具后造成伤害", intent="Damage", slot="damage", subject="普通怪物", chapter="MONSTER")],
        "chapters": [{"chapterId": "MONSTER", "title": "普通怪物", "system": "关卡", "object": "普通怪物"}],
        "gaps": [
            {"gapId": "Q", "chapterId": "MONSTER", "status": "reviewed_open", "gapDomain": "planning", "question": "怪物命中目标前依次执行哪些攻击处理？"},
            {"gapId": "T", "chapterId": "MONSTER", "status": "reviewed_open", "gapDomain": "technical", "question": "读取哪项配置？"},
            {"gapId": "P", "chapterId": "MONSTER", "status": "reviewed_open", "gapDomain": "planning", "question": "怪物接触载具并造成伤害后，是继续移动、停留攻击，还是离开战场？", "specificity": "concrete_decision"},
        ],
    })
    text = document_to_markdown(document)

    assert "接触载具后造成伤害" in text
    assert "继续移动、停留攻击，还是离开战场" in text
    assert "依次执行哪些攻击处理" not in text
    assert "读取哪项配置" not in text


def test_reconstruction_keeps_high_risk_guard_and_reports_zero_unsupported_publication():
    chapters = [{"chapterId": "DRAW", "title": "三选一", "entityScope": ["三选一"]}]
    result = _projection([
        _rule("DRAW", "升级时生成三张候选卡", intent="CandidateGeneration", slot="random_trigger", subject="三选一", chapter="DRAW"),
        _rule("BAD", "候选等概率无放回抽取并设置权重与保底", intent="CandidateGeneration", slot="sampling_rule", subject="三选一", chapter="DRAW"),
    ], chapters)

    published = "\n".join(rule["behavior"] for rule in result["publication"]["rules"])
    assert all(term not in published for term in ("等概率", "无放回", "权重", "保底"))
    assert result["reconstructionAudit"]["unsupportedInferenceCount"] == 0


def test_reconstructed_final_never_falls_back_to_blocked_or_presentation_rules():
    flow = {
        "mechanicId": "MECH-MONSTER", "chapterId": "MONSTER", "subject": "怪物",
        "steps": [{"ruleId": "OK", "intent": "Damage", "text": "怪物接触载具后造成伤害。"}],
    }
    document = build_final_document({
        "mechanicFlows": [flow],
        "chapters": [
            {"chapterId": "MONSTER", "title": "攻击", "system": "关卡", "object": "怪物"},
            {"chapterId": "PRESENTATION", "title": "战斗表现", "system": "关卡", "object": "关卡"},
        ],
        "rules": [
            _rule("OK", "怪物接触载具后造成伤害", intent="Damage", slot="damage", subject="怪物", chapter="MONSTER"),
            {**_rule("P", "战斗画面显示红色遮罩", intent="Unknown", slot="presentation", subject="战斗画面", chapter="PRESENTATION"), "ruleType": "presentation", "publicationEligibility": "blocked"},
        ],
        "gaps": [],
    })
    text = document_to_markdown(document)

    assert "接触载具后造成伤害" in text
    assert "红色遮罩" not in text
    assert "战斗表现" not in text


def test_production_adapter_uses_only_reconstructed_flows_and_carries_specific_gaps_from_source_chapters():
    model = {
        "ruleIntelligenceProjection": {
            "authorityMode": "structured_rules",
            "publication": {
                "mechanicFlows": [{
                    "mechanicId": "MECH-MONSTER", "chapterId": "SPAWN",
                    "sourceChapterIds": ["SPAWN", "MOVE"], "subject": "怪物",
                    "steps": [{"ruleId": "S", "text": "怪物生成。"}, {"ruleId": "M", "text": "怪物移动。"}],
                }],
                "finalPlanningGaps": [{
                    "gapId": "G", "chapterId": "MOVE", "specificity": "concrete_decision",
                    "question": "怪物接触载具后如何处理？",
                }],
                "chapters": [
                    {"chapterId": "SPAWN", "title": "刷新", "system": "关卡", "object": "怪物", "publicationEligibility": "eligible", "ruleDefinitions": [], "references": [], "gaps": []},
                    {"chapterId": "MOVE", "title": "移动", "system": "关卡", "object": "怪物", "publicationEligibility": "eligible", "ruleDefinitions": [], "references": [], "gaps": []},
                    {"chapterId": "P", "title": "战斗表现", "system": "关卡", "object": "关卡", "publicationEligibility": "eligible", "ruleDefinitions": [{"ruleId": "P", "behavior": "显示红色遮罩"}], "references": [], "gaps": []},
                ],
            },
        }
    }

    adapted = authoritative_gameplay_model(model)
    assert len(adapted["chapters"]) == 1
    assert [item["text"] for item in adapted["chapters"][0]["plannerSections"]["normalFlow"]] == ["怪物生成。", "怪物移动。"]
    assert adapted["chapters"][0]["unknowns"][0]["gapId"] == "G"


def test_confirmed_overview_result_rule_recovers_required_slot_once_and_closes_gap():
    chapters = [{
        "chapterId": "RESULT", "title": "结果判定", "system": "任务",
        "entityScope": ["任务"], "schemaResponsibilities": ["victory_condition"],
    }]
    result = build_rule_intelligence_projection(
        approved_data={
            "rules": [], "facts": [], "parameters": [], "gaps": [{
                "gapId": "MISSING-RESULT", "chapterId": "RESULT", "intent": "VictoryCondition",
                "schemaSlot": "victory_condition", "status": "reviewed_open", "gapDomain": "planning",
                "question": "任务以什么事件判定胜利？", "specificity": "concrete_decision",
            }],
            "approvedNarratives": [{
                "narrativeId": "OVERVIEW-RESULT", "sourceType": "gameplay_overview",
                "text": "当全部目标节点激活时，任务成功。", "reviewStatus": "confirmed",
                "confirmation": {"confirmed": True, "revision": 8},
            }],
        },
        chapters=chapters,
    )

    recovered = [rule for rule in result["rules"] if rule.get("recoverySourceId") == "OVERVIEW-RESULT"]
    assert len(recovered) == 1
    assert recovered[0]["intent"] == "VictoryCondition"
    assert recovered[0]["canonicalOwner"] == "RESULT"
    assert recovered[0]["definitionMode"] == "full_definition"
    assert recovered[0]["confirmationStatus"] == "confirmed"
    assert result["closures"][0]["slots"]["VictoryCondition"] == "confirmed"
    assert not any(gap.get("intent") == "VictoryCondition" for gap in result["gaps"])

    text = document_to_markdown(build_final_document(result["publication"], title="任务规则"))
    assert text.count("当全部目标节点激活时，任务成功") == 1
    assert "以什么事件判定胜利" not in text
    assert result["guard"]["duplicateFullDefinitionFingerprints"] == []


def test_unreviewed_overview_cannot_recover_project_rule_or_close_required_slot():
    chapters = [{
        "chapterId": "RESULT", "title": "结果判定", "system": "任务",
        "entityScope": ["任务"], "schemaResponsibilities": ["victory_condition"],
    }]
    result = build_rule_intelligence_projection(
        approved_data={
            "rules": [], "facts": [], "parameters": [], "gaps": [],
            "approvedNarratives": [{
                "narrativeId": "DRAFT-RESULT", "sourceType": "gameplay_overview",
                "text": "当全部目标节点激活时，任务成功。", "reviewStatus": "unreviewed",
            }],
        },
        chapters=chapters,
    )

    assert not any(rule.get("recoverySourceId") == "DRAFT-RESULT" for rule in result["rules"])
    assert result["closures"][0]["slots"]["VictoryCondition"] == "unresolved"
    assert any(gap.get("intent") == "VictoryCondition" for gap in result["gaps"])


def test_confirmed_directory_understanding_is_an_authoritative_recovery_source():
    chapters = [{
        "chapterId": "OUTCOME", "title": "结果", "system": "关卡",
        "entityScope": ["关卡"], "schemaResponsibilities": ["victory_condition"],
    }]
    result = build_rule_intelligence_projection(
        approved_data={
            "rules": [], "facts": [], "parameters": [], "gaps": [],
            "directory": {
                "status": "confirmed", "revision": 12,
                "understanding": {"basicFlow": "当全部检查点完成时，关卡胜利。"},
            },
        },
        chapters=chapters,
    )

    recovered = next(rule for rule in result["rules"] if rule.get("inferenceLevel") == "approved_information_recovery")
    assert recovered["recoverySourceField"] == "directory.understanding.basicFlow"
    assert recovered["recoveryRevision"] == 12
    assert recovered["canonicalOwner"] == "OUTCOME"
    assert result["closures"][0]["status"] == "complete"


def test_recovered_victory_rule_closes_referenced_mechanics_instead_of_dangling():
    chapters = [{
        "chapterId": "OUTCOME", "title": "结果判定", "system": "任务",
        "entityScope": ["任务"], "schemaResponsibilities": ["victory_condition"],
    }]
    result = build_rule_intelligence_projection(
        approved_data={
            "rules": [], "facts": [], "parameters": [], "gaps": [],
            "approvedNarratives": [
                {
                    "narrativeId": "OVERVIEW", "sourceType": "gameplay_overview",
                    "text": "当指挥官已被击败、场上存活守卫数量为0且运输器仍存活时，任务成功并进入成功结算。",
                    "reviewStatus": "confirmed", "confirmation": {"confirmed": True, "revision": 9},
                },
                {
                    "narrativeId": "COMMANDER", "sourceType": "confirmed_basic_flow",
                    "text": "指挥官耐久归零后被击败，并停止行动。", "reviewStatus": "confirmed",
                },
                {
                    "narrativeId": "GUARD", "sourceType": "confirmed_chapter_summary",
                    "text": "守卫被击败后离场；场上剩余守卫全部离场后，存活守卫数量为0。", "reviewStatus": "confirmed",
                },
                {
                    "narrativeId": "TRANSPORT", "sourceType": "confirmed_chapter_summary",
                    "text": "运输器拥有耐久；耐久大于0时处于存活状态。", "reviewStatus": "confirmed",
                },
                {
                    "narrativeId": "SETTLEMENT", "sourceType": "confirmed_basic_flow",
                    "text": "任务成功后进入成功结算，结算本次任务结果。", "reviewStatus": "confirmed",
                },
            ],
        },
        chapters=chapters,
    )

    closure = result["dependencyClosure"]
    assert closure["unresolvedMechanicReferences"] == []
    assert {item["referenceKind"] for item in closure["references"]} == {
        "defeated_state", "remaining_count_zero", "alive_state", "settlement",
    }
    assert all(item["status"] == "resolved" for item in closure["references"])
    published_objects = {chapter.get("object") for chapter in result["publication"]["chapters"]}
    assert {"指挥官", "守卫", "运输器", "成功结算"}.issubset(published_objects)

    text = document_to_markdown(build_final_document(result["publication"], title="任务规则"))
    for phrase in ("指挥官耐久归零后被击败", "存活守卫数量为0", "运输器拥有耐久", "进入成功结算"):
        assert phrase in text
    assert text.count("任务成功并进入成功结算") == 1


def test_attack_execution_text_repairs_legacy_target_selection_misclassification():
    chapters = [{"chapterId": "WEAPON", "title": "攻击", "object": "武器", "entityScope": ["武器"]}]
    result = _projection([
        _rule(
            "EXECUTE", "武器向当前目标发射投射物", intent="TargetSelection",
            slot="attack_target", subject="武器", chapter="WEAPON",
        ),
        _rule(
            "AIM", "武器无需玩家手动瞄准", intent="AttackTrigger",
            slot="attack_trigger", subject="武器", chapter="WEAPON",
        ),
    ], chapters)

    intents = {rule["ruleId"]: rule["intent"] for rule in result["rules"]}
    assert intents == {"EXECUTE": "AttackMode", "AIM": "AttackMode"}


def test_trivial_removed_entity_target_consequence_is_suppressed_from_final():
    chapters = [{"chapterId": "BOSS", "title": "首领", "entityScope": ["首领"]}]
    result = _projection([
        _rule("REMOVED", "首领被击败后移出战场", intent="Death", slot="death", subject="首领", chapter="BOSS"),
        {**_rule("TARGET", "首领被移除后不再作为攻击目标", intent="TargetSelection", slot="attack_target", subject="首领", chapter="BOSS"),
         "derivationKind": "logical_consequence", "sourceRuleIds": ["REMOVED"]},
    ], chapters)
    published = [step["ruleId"] for flow in result["publication"]["mechanicFlows"] for step in flow["steps"]]
    assert "REMOVED" in published
    assert "TARGET" not in published
    assert result["reconstructionAudit"]["trivialDerivedRulesSuppressed"] == 1


def test_non_trivial_targetability_exception_is_retained():
    chapters = [{"chapterId": "BOSS", "title": "首领", "entityScope": ["首领"]}]
    result = _projection([
        _rule("REMOVED", "首领生命值归零后播放死亡动画", intent="Death", slot="death", subject="首领", chapter="BOSS"),
        {**_rule("EXCEPTION", "首领在死亡动画期间仍可被攻击", intent="TargetSelection", slot="attack_target", subject="首领", chapter="BOSS"),
         "derivationKind": "exception", "sourceRuleIds": ["REMOVED"]},
    ], chapters)
    published = [step["ruleId"] for flow in result["publication"]["mechanicFlows"] for step in flow["steps"]]
    assert "EXCEPTION" in published


def test_trivial_target_clause_is_removed_without_dropping_non_trivial_death_processing():
    chapters = [{"chapterId": "BOSS", "title": "首领", "entityScope": ["首领"]}]
    result = _projection([
        _rule(
            "DEATH", "首领生命值归零后停止移动和新的攻击结算，将首领不再作为武器攻击目标，并取消尚未生效的接触攻击",
            intent="Death", slot="death", subject="首领", chapter="BOSS",
        ),
    ], chapters)
    text = "\n".join(step["text"] for flow in result["publication"]["mechanicFlows"] for step in flow["steps"])
    assert "停止移动和新的攻击结算" in text
    assert "取消尚未生效的接触攻击" in text
    assert "不再作为武器攻击目标" not in text
    assert result["reconstructionAudit"]["trivialDerivedClausesSuppressed"] == 1


def test_run_specific_reward_value_is_not_promoted_to_general_rule():
    chapters = [{"chapterId": "RESULT", "title": "结算", "entityScope": ["结算"]}]
    result = _projection([
        {**_rule("REWARD", "成功结算发放100基础货币并结算本局道具", intent="Reward", slot="reward", subject="结算", chapter="RESULT"),
         "valueAuthority": "observed_run_value"},
    ], chapters)
    text = "\n".join(step["text"] for flow in result["publication"]["mechanicFlows"] for step in flow["steps"])
    assert "100" not in text
    assert "结算本局" in text
    assert result["reconstructionAudit"]["runSpecificValuesSuppressed"] == 1


def test_planner_confirmed_reward_value_is_retained_as_general_rule():
    chapters = [{"chapterId": "RESULT", "title": "结算", "entityScope": ["结算"]}]
    result = _projection([
        {**_rule("REWARD", "成功结算固定发放100基础货币", intent="Reward", slot="reward", subject="结算", chapter="RESULT"),
         "valueAuthority": "planner_confirmed_value"},
    ], chapters)
    text = "\n".join(step["text"] for flow in result["publication"]["mechanicFlows"] for step in flow["steps"])
    assert "固定发放100基础货币" in text
    assert result["reconstructionAudit"]["configuredValuesRetained"] == 1


def test_selection_rules_use_semantic_narrative_order_not_input_or_rule_id_order():
    chapters = [{"chapterId": "SELECT", "title": "选择", "chapterType": "randomization", "entityScope": ["选择"]}]
    rules = [
        _rule("Z-NUM", "强化使攻击范围扩大30%", intent="CandidateGeneration", slot="effect_parameter", subject="选择", chapter="SELECT"),
        _rule("A-REFRESH", "玩家刷新后替换当前选项", intent="CandidateGeneration", slot="refresh_rule", subject="选择", chapter="SELECT"),
        _rule("Y-EFFECT", "确认后应用所选效果", intent="CandidateGeneration", slot="candidate_effect", subject="选择", chapter="SELECT"),
        _rule("B-SELECT", "玩家选择一项", intent="CandidateGeneration", slot="candidate_selection", subject="选择", chapter="SELECT"),
        _rule("X-CANDIDATE", "系统生成三个候选", intent="CandidateGeneration", slot="candidate_pool_source", subject="选择", chapter="SELECT"),
        _rule("C-TRIGGER", "升级时触发选择", intent="CandidateGeneration", slot="random_trigger", subject="选择", chapter="SELECT"),
    ]
    flow = _projection(rules, chapters)["publication"]["mechanicFlows"][0]

    assert [step["ruleId"] for step in flow["steps"]] == [
        "C-TRIGGER", "X-CANDIDATE", "B-SELECT", "Y-EFFECT", "A-REFRESH", "Z-NUM",
    ]
    assert [group["groupId"] for group in flow["semanticGroups"]] == [
        "trigger", "candidate_generation", "selection", "effect", "refresh", "numeric_examples",
    ]


def test_selection_document_places_candidate_types_and_exit_before_refresh_and_inlines_button_action():
    chapters = [{
        "chapterId": "SELECT", "title": "选择", "object": "选择",
        "system": "成长", "chapterType": "randomization", "entityScope": ["选择", "玩家"],
    }]
    rules = [
        _rule("NUM", "强化使攻击范围扩大30%", intent="CandidateGeneration", slot="effect_parameter", subject="选择", chapter="SELECT"),
        {**_rule("BUTTON", "玩家点击刷新按钮", intent="CandidateGeneration", slot="refresh_rule", subject="玩家", chapter="SELECT"), "ruleType": "interaction"},
        _rule("REFRESH", "刷新后替换当前候选", intent="CandidateGeneration", slot="refresh_rule", subject="选择", chapter="SELECT"),
        _rule("EXIT", "玩家确认后退出选择界面", intent="ResultTransition", slot="selection_interface_exit", subject="选择", chapter="SELECT"),
        _rule("EFFECT", "确认后应用所选效果", intent="CandidateGeneration", slot="candidate_effect", subject="选择", chapter="SELECT"),
        _rule("SELECT", "玩家选择一项", intent="CandidateGeneration", slot="candidate_selection", subject="选择", chapter="SELECT"),
        _rule("CANDIDATE", "系统生成新武器候选", intent="CandidateGeneration", slot="candidate_pool_source", subject="选择", chapter="SELECT"),
        _rule("PAUSE", "进入选择状态时暂停战斗", intent="CandidateGeneration", slot="selection_pause", subject="选择", chapter="SELECT"),
        _rule("TRIGGER", "升级时触发选择", intent="CandidateGeneration", slot="random_trigger", subject="选择", chapter="SELECT"),
    ]
    publication = _projection(rules, chapters)["publication"]
    text = document_to_markdown(build_final_document(publication, title="选择系统"))

    markers = [
        "升级时触发选择", "进入选择状态时暂停战斗", "系统生成新武器候选",
        "当前已观察到的候选内容包括", "玩家选择一项", "确认后应用所选效果",
        "玩家确认后退出选择界面", "玩家点击刷新按钮，随后刷新后替换当前候选",
        "强化使攻击范围扩大30%",
    ]
    assert [text.index(marker) for marker in markers] == sorted(text.index(marker) for marker in markers)
    assert text.count("刷新按钮") == 1
    refresh_step = next(
        step for flow in publication["mechanicFlows"] for step in flow["steps"]
        if "刷新按钮" in step.get("text", "")
    )
    assert set(refresh_step["sourceRuleIds"]) == {"BUTTON", "REFRESH"}


def test_compound_trigger_generation_is_decomposed_into_stable_narrative_order():
    chapters = [{
        "chapterId": "SELECT", "title": "选择", "object": "选择",
        "system": "成长", "chapterType": "randomization", "entityScope": ["选择"],
    }]
    rules = [
        _rule("NUM", "强化使攻击范围扩大30%", intent="CandidateGeneration", slot="effect_parameter", subject="选择", chapter="SELECT"),
        _rule("REFRESH", "刷新后替换当前选项", intent="CandidateGeneration", slot="refresh_rule", subject="选择", chapter="SELECT"),
        _rule("EXIT", "玩家确认后退出选择界面并恢复战斗", intent="ResultTransition", slot="selection_interface_exit", subject="选择", chapter="SELECT"),
        _rule("EFFECT", "确认后应用所选效果", intent="CandidateGeneration", slot="candidate_effect", subject="选择", chapter="SELECT"),
        _rule("SELECT", "玩家选择一项", intent="CandidateGeneration", slot="candidate_selection", subject="选择", chapter="SELECT"),
        _rule("PAUSE", "进入选择状态时暂停战斗", intent="CandidateGeneration", slot="selection_pause", subject="选择", chapter="SELECT"),
        _rule("COMPOUND", "系统升级触发时生成三个候选", intent="CandidateGeneration", slot="random_trigger", subject="选择", chapter="SELECT"),
    ]
    publication = _projection(rules, chapters)["publication"]
    flow = publication["mechanicFlows"][0]
    text = document_to_markdown(build_final_document(publication, title="选择系统"))

    markers = [
        "系统升级时触发选择", "进入选择状态时暂停战斗", "生成三个候选", "玩家选择一项",
        "确认后应用所选效果", "玩家确认后退出选择界面并恢复战斗", "刷新后替换当前选项",
        "强化使攻击范围扩大30%",
    ]
    assert [text.index(marker) for marker in markers] == sorted(text.index(marker) for marker in markers)
    assert [group["groupId"] for group in flow["semanticGroups"]] == [
        "trigger", "state_entry", "candidate_generation", "selection", "effect", "state_exit", "refresh", "numeric_examples",
    ]
    compound_steps = [step for step in flow["steps"] if "COMPOUND" in step.get("sourceRuleIds", [])]
    assert {step["semanticGroup"] for step in compound_steps} == {"trigger", "candidate_generation"}
