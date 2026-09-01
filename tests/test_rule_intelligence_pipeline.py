from backend.rule_intelligence_pipeline import build_rule_intelligence_projection
from backend.requirement_temporal_probe import analyze_persistent_state


def _rule(rule_id, behavior, *, subject="系统", slot="", chapter="C1", **values):
    return {
        "ruleId": rule_id, "subject": subject, "behavior": behavior,
        "schemaSlot": slot, "ownerChapterId": chapter,
        "reviewStatus": values.pop("reviewStatus", "approved"),
        "semanticValidity": "valid", "evidenceIds": [f"E-{rule_id}"],
        **values,
    }


def _projection(rules, *, chapters=None, facts=None, parameters=None, entities=None, observations=None):
    return build_rule_intelligence_projection(
        approved_data={"rules": rules, "facts": facts or [], "parameters": parameters or [], "gaps": []},
        chapters=chapters or [{"chapterId": "C1", "chapterType": "attack", "title": "任意标题"}],
        entity_declarations=entities or [], temporal_observations=observations or [],
    )


def test_attack_direction_interval_and_range_have_distinct_intents():
    result = _projection([
        _rule("R1", "武器朝目标方向旋转", slot="attack_method"),
        _rule("R2", "武器每1秒攻击一次", slot="attack_frequency"),
        _rule("R3", "武器射程为8", slot="attack_range"),
    ])
    assert [rule["intent"] for rule in result["rules"]] == ["AttackDirection", "AttackInterval", "Range"]


def test_attack_mode_semantic_correction_also_repairs_legacy_schema_slot():
    result = _projection([
        _rule("METHOD", "武器向目标发射投射物", slot="attack_target", intent="TargetSelection"),
        _rule("AIM", "武器无需玩家手动瞄准", slot="attack_trigger", intent="AttackTrigger"),
    ])

    assert [(rule["intent"], rule["schemaSlot"]) for rule in result["rules"]] == [
        ("AttackMode", "attack_method"),
        ("AttackMode", "attack_method"),
    ]


def test_ownerless_result_transition_uses_unique_outcome_schema_owner():
    chapters = [
        {"chapterId": "BOSS", "chapterType": "boss", "schemaResponsibilities": ["boss_result"]},
        {"chapterId": "OUTCOME", "chapterType": "level_flow"},
        {"chapterId": "SELECT", "chapterType": "randomization"},
    ]
    result = _projection([
        _rule("WIN", "目标被击败后挑战成功", slot="victory_condition", chapter="OUTCOME"),
        _rule("FAIL", "玩家生命值归零后挑战失败", slot="failure_condition", chapter="OUTCOME"),
        _rule(
            "SIMULTANEOUS", "胜利与失败条件同时成立时，先完成结果判定再进入对应结算",
            slot="result_transition", chapter="", intent="ResultTransition",
        ),
        _rule("SELECT_EXIT", "完成选择后退出界面", slot="selection_exit", chapter="SELECT", intent="ResultTransition"),
    ], chapters=chapters)

    transition = next(rule for rule in result["rules"] if rule["ruleId"] == "SIMULTANEOUS")
    assert transition["schemaSlot"] == "result_transition"
    assert transition["canonicalOwner"] == "OUTCOME"
    assert transition["publicationEligibility"] == "eligible"


def test_review_proposal_only_addresses_gap_in_same_canonical_owner():
    chapters = [
        {"chapterId": "WEAPON", "chapterType": "attack", "title": "武器"},
        {"chapterId": "MONSTER", "chapterType": "attack", "title": "怪物"},
    ]
    result = build_rule_intelligence_projection(
        approved_data={
            "rules": [
                _rule("TARGET", "武器选择射程内目标", slot="attack_target", chapter="WEAPON"),
                _rule("METHOD", "武器向目标发射投射物", slot="attack_target", chapter="WEAPON", intent="TargetSelection"),
            ],
            "facts": [], "parameters": [],
            "gaps": [{
                "gapId": "MONSTER-EXIT", "chapterId": "MONSTER", "schemaSlot": "attack_exit_condition",
                "status": "open", "gapDomain": "planning",
            }],
        },
        chapters=chapters,
    )

    gap = next(gap for gap in result["gaps"] if gap["gapId"] == "MONSTER-EXIT")
    assert gap["status"] == "open"
    assert not gap.get("proposalId")


def test_combat_entity_without_spawn_evidence_gets_gap_not_rule():
    result = _projection(
        [_rule("MOVE", "敌人向目标移动", subject="敌人", slot="movement_direction"),
         _rule("ATTACK", "敌人接触目标后攻击", subject="敌人", slot="attack_trigger")],
        entities=[{"entityId": "enemy", "name": "敌人", "entityType": "combat_entity", "existenceStatus": "confirmed"}],
    )
    assert not any(rule["intent"] == "Spawn" for rule in result["rules"])
    assert any(gap["gapKind"] == "missing_lifecycle_node" and gap["intent"] == "Spawn" for gap in result["gaps"])


def test_visual_position_change_is_candidate_not_confirmed_movement():
    result = _projection([], entities=[{"entityId": "vehicle", "name": "载具", "entityType": "combat_entity", "existenceStatus": "confirmed"}], observations=[{
        "observationId": "OBS-1", "entityId": "vehicle", "observationType": "VisualPositionChange",
        "samples": [{"timestamp": 1, "position": [10, 10]}, {"timestamp": 3, "position": [20, 10]}],
        "coordinateFrame": "unknown", "confidence": .8,
    }])
    assert result["movementCandidates"]
    assert not any(rule["intent"] == "Movement" for rule in result["rules"])
    assert any(gap["gapKind"] == "coordinate_frame_unknown" for gap in result["gaps"])


def test_observed_sequence_is_inferred_pattern_not_formula():
    result = _projection([], parameters=[{"parameterId": "P1", "observedValues": [10, 15, 20, 25], "sourceKind": "observed_value"}])
    parameter = result["parameters"][0]
    assert parameter["sourceKind"] == "inferred_pattern"
    assert parameter.get("formulaExpression") is None
    assert not result["publication"]["formulae"]


def test_random_does_not_imply_probability_replacement_weight_priority_or_guarantee():
    result = _projection([_rule("R1", "系统随机抽取候选", slot="random_trigger")], chapters=[{
        "chapterId": "C1", "chapterType": "randomization", "mechanicVariant": "three_choice", "title": "任意标题",
    }])
    rule = result["rules"][0]
    assert rule["intent"] == "CandidateGeneration"
    assert all(term not in rule["behavior"] for term in ("等概率", "无放回", "权重", "优先", "保底"))
    states = result["closures"][0]["slots"]
    assert states["WeightRule"] in {"not_observed", "not_applicable"}
    assert states["PriorityRule"] in {"not_observed", "not_applicable"}
    assert states["GuaranteeRule"] in {"not_observed", "not_applicable"}


def test_victory_rule_has_one_full_definition_and_other_uses_are_references():
    chapters = [
        {"chapterId": "BOSS", "chapterType": "boss", "schemaResponsibilities": ["boss_result"]},
        {"chapterId": "LEVEL", "chapterType": "level_flow", "schemaResponsibilities": ["result_reference"]},
        {"chapterId": "OUTCOME", "chapterType": "level_flow", "schemaResponsibilities": ["victory_condition", "failure_condition", "result_transition"]},
    ]
    rules = [_rule("A", "首领生命值归零后挑战胜利", subject="首领", chapter=chapter) for chapter in ("BOSS", "LEVEL", "OUTCOME")]
    result = _projection(rules, chapters=chapters)
    modes = [rule["definitionMode"] for rule in result["rules"]]
    assert modes.count("full_definition") == 1
    assert next(rule for rule in result["rules"] if rule["definitionMode"] == "full_definition")["canonicalOwner"] == "OUTCOME"


def test_victory_failure_without_victory_is_incomplete_without_invention():
    result = _projection([
        _rule("F", "玩家生命值归零后失败", slot="failure_condition"),
        _rule("T", "判定结果后进入结算", slot="level_end_timing"),
    ], chapters=[{"chapterId": "C1", "chapterType": "level_flow", "schemaResponsibilities": ["victory_condition", "failure_condition", "result_transition"]}])
    assert result["closures"][0]["status"] == "incomplete"
    assert not any(rule["intent"] == "VictoryCondition" for rule in result["rules"])
    assert any(gap["intent"] == "VictoryCondition" and gap["blockingScope"] == "chapter" for gap in result["gaps"])


def test_structural_rule_change_invalidates_review_and_final():
    confirmed = _rule("A", "首领死亡后胜利", slot="victory_condition", condition="首领死亡", result="胜利", confirmationFingerprint="stale")
    result = _projection([confirmed], chapters=[{"chapterId": "C1", "chapterType": "level_flow", "schemaResponsibilities": ["victory_condition"]}])
    assert result["rules"][0]["confirmationStatus"] == "stale"
    assert not result["publication"]["rules"]


def test_unreviewed_rule_is_visible_in_review_but_not_final_publication():
    result = _projection([_rule("A", "每1秒攻击一次", slot="attack_frequency", reviewStatus="unreviewed")])

    assert [rule["ruleId"] for rule in result["reviewProjection"]["chapters"][0]["ruleDefinitions"]] == ["A"]
    assert result["publication"]["rules"] == []
    assert result["guard"]["passed"] is False


def test_similar_victory_rules_with_different_conditions_are_not_merged():
    result = _projection([
        _rule("A", "首领死亡后胜利", slot="victory_condition", condition="首领死亡", result="胜利"),
        _rule("B", "首领死亡且普通敌人清空后胜利", slot="victory_condition", condition="首领死亡且普通敌人清空", result="胜利"),
    ], chapters=[{"chapterId": "C1", "chapterType": "level_flow", "schemaResponsibilities": ["victory_condition"]}])
    assert result["rules"][0]["exactSemanticFingerprint"] != result["rules"][1]["exactSemanticFingerprint"]
    assert result["possibleDuplicates"]
    assert any(rule["publicationEligibility"] == "review_required" for rule in result["rules"])


def test_optional_candidate_slots_do_not_expand_into_missing_gaps():
    result = _projection([_rule("R1", "系统从候选列表中生成选项", slot="random_trigger")], chapters=[{
        "chapterId": "C1", "chapterType": "randomization", "schemaResponsibilities": ["candidate_generation"],
    }])
    optional = {"WeightRule", "PriorityRule", "GuaranteeRule", "DuplicateRule"}
    assert not any(gap.get("schemaSlot") in optional for gap in result["gaps"])


def test_ownerless_and_guard_blocked_rules_never_enter_publication():
    result = _projection([
        _rule("OWNERLESS", "每1秒攻击一次", slot="attack_frequency", chapter=""),
        _rule("UNSUPPORTED", "候选项等概率无放回抽取", slot="random_trigger", inferenceLevel="observed"),
    ])

    assert {rule["ruleId"] for rule in result["rules"] if rule["publicationEligibility"] != "eligible"} == {
        "OWNERLESS", "UNSUPPORTED",
    }
    assert result["publication"]["rules"] == []
    assert set(result["guard"]["blockedRuleIds"]) == {"OWNERLESS", "UNSUPPORTED"}


def test_unreviewed_temporal_evidence_creates_candidate_without_authority_or_closure():
    chapters = [{
        "chapterId": "C1", "chapterType": "movement", "title": "移动",
        "schemaResponsibilities": ["movement"],
    }]
    temporal_fact = {
        "factId": "TF-1", "entityId": "vehicle", "subject": "载具",
        "predicate": "position_changed", "propertyPath": "position",
        "beforeValue": [10, 10], "afterValue": [20, 10],
        "evidenceIds": ["VF-1", "VF-2"], "evidenceTimestamps": [1.0, 2.0],
        "sourceKind": "auxiliary_video", "observationMode": "targeted_temporal_probe",
        "temporalPattern": "moving", "referenceFrameStatus": "stable",
        "identityStatus": "confirmed", "reviewStatus": "unreviewed",
        "inferenceLevel": "observed", "confidence": 0.9,
    }
    candidate = _rule(
        "TRC-1", "载具在当前样本中发生持续相对位移", subject="载具",
        slot="movement_direction", reviewStatus="unreviewed",
        sourceFactIds=["TF-1"], candidateKind="temporal_rule_candidate",
    )

    result = build_rule_intelligence_projection(
        approved_data={"rules": [], "facts": [], "parameters": [], "gaps": []},
        chapters=chapters, temporal_facts=[temporal_fact], temporal_rule_candidates=[candidate],
    )

    assert [item["ruleId"] for item in result["ruleCandidates"]] == ["TRC-1"]
    assert result["publication"]["rules"] == []
    assert result["closures"][0]["status"] == "incomplete"
    assert any(gap["intent"] == "Movement" and gap["status"] == "unresolved" for gap in result["gaps"])


def test_targeted_temporal_fact_enters_existing_pipeline_without_second_rule_authority():
    probe_result = analyze_persistent_state({
        "probeRequestId": "TPR-1", "targetProperty": "position",
        "ownerChapterId": "C1", "schemaSlot": "movement_direction",
    }, {
        "trackCandidateId": "TTC-1", "entityId": "entity-1", "candidateEntityId": None,
        "identityStatus": "confirmed", "trackConfidence": .9, "sourceVideoId": "video-v1",
        "observations": [
            {"frameId": "VF-1", "timestamp": 1.0, "sceneId": 1, "bbox": [0, 0, 10, 10], "backgroundDelta": [0, 0], "uiDelta": [0, 0]},
            {"frameId": "VF-2", "timestamp": 2.0, "sceneId": 1, "bbox": [10, 0, 20, 10], "backgroundDelta": [0, 0], "uiDelta": [0, 0]},
            {"frameId": "VF-3", "timestamp": 3.0, "sceneId": 1, "bbox": [20, 0, 30, 10], "backgroundDelta": [0, 0], "uiDelta": [0, 0]},
        ],
    })
    chapters = [{"chapterId": "C1", "chapterType": "movement", "schemaResponsibilities": ["movement"]}]

    result = build_rule_intelligence_projection(
        approved_data={"rules": [], "facts": [], "parameters": [], "gaps": []}, chapters=chapters,
        temporal_facts=probe_result["temporalFacts"],
        temporal_rule_candidates=probe_result["ruleCandidates"],
        temporal_observations=[probe_result["observation"]],
    )

    assert len(result["facts"]) == 1
    assert result["facts"][0]["probeRequestId"] == "TPR-1"
    assert [item["ruleId"] for item in result["ruleCandidates"]] == ["TRC-1-movement"]
    assert result["reviewProjection"]["rules"][0]["intent"] == "Movement"
    assert result["publication"]["rules"] == []
    assert result["closures"][0]["status"] == "incomplete"
