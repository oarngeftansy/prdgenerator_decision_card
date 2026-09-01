from copy import deepcopy

import pytest

from backend.gameplay_review_model import build_gameplay_review_model, gameplay_gate, normalize_gameplay_structure, required_parameter_fields
from backend.gameplay_review_service import (
    GameplayReviewConflict,
    apply_gameplay_operations,
    add_targeted_temporal_probe_result,
    confirm_gameplay_chapter,
    redo_gameplay,
    reopen_gameplay_chapter,
    undo_gameplay,
)
from backend.rule_normalizer import build_rule_intelligence_v1


def gameplay_model():
    job = {"id": "job-gameplay-service", "interactionModel": {"revision": 7}, "frames": [{"id": "F0001"}, {"id": "F0002"}]}
    return build_gameplay_review_model(job, [
        {"scope": "combat", "claims": [{"id": "GCL-001", "text": "Attack", "sourceType": "material", "sourceFrameIds": ["F0001"]}], "mechanism": {"type": "core_loop", "name": "Attack"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"]},
        {"scope": "rewards", "claims": [{"id": "GCL-002", "text": "Reward", "sourceType": "material", "sourceFrameIds": ["F0002"]}], "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0002"]},
    ])


def test_operations_increment_once_invalidate_diagrams_and_keep_input_immutable():
    model = gameplay_model()
    model["diagrams"] = [{"id": "GDI-001", "status": "reviewed", "chapterIds": ["GCH-001"]}]
    original = deepcopy(model)

    result = apply_gameplay_operations(model, [{"type": "set_chapter_field", "chapterId": "GCH-001", "field": "scope", "value": "combat loop"}], model["revision"])

    assert model == original
    assert result["revision"] == 2
    assert result["chapters"][0]["status"] == "chapter_review"
    assert result["chapters"][0]["confirmation"] == {"confirmed": False, "revision": None}
    assert result["diagrams"][0]["status"] == "stale"
    assert result["reviewState"]["previewRevision"] is None


def test_v2_rule_review_validates_shape_and_preserves_provenance_on_edit():
    model = gameplay_model()
    model["contentModelVersion"] = 2
    model["approvedData"] = {
        "contentModelVersion": 2, "schemaVersion": "chapter-schema-v2",
        "chapters": [{"chapterId": "V2CH-001", "matchedSchema": "chapter-schema-v2:attack:base"}],
        "slots": [{"chapterId": "V2CH-001", "slotId": "attack_trigger", "factIds": ["FACT-1"], "status": "confirmed"}],
        "facts": [], "gaps": [], "approvalRevision": 0,
        "rules": [{
            "ruleId": "RULE-1", "semanticKey": "stable-key", "ownerChapterId": "V2CH-001",
            "definitionMode": "primary", "ruleType": "logic", "schemaSlot": "attack_trigger",
            "subject": "武器", "trigger": None, "conditions": [], "behavior": "自动攻击目标",
            "result": None, "stateChange": None, "exitCondition": None, "exception": None,
            "parameterRefs": [], "evidenceIds": ["F0001"], "reviewStatus": "unreviewed",
        }],
    }
    changed = apply_gameplay_operations(model, [{
        "type": "review_rule", "ruleId": "RULE-1", "decision": "approved",
        "patch": {"behavior": "目标进入射程后自动攻击"},
    }], 1)
    rule = changed["approvedData"]["rules"][0]
    assert rule["behavior"] == "目标进入射程后自动攻击"
    assert rule["reviewStatus"] == "approved"
    assert (rule["semanticKey"], rule["ownerChapterId"], rule["evidenceIds"]) == ("stable-key", "V2CH-001", ["F0001"])
    assert changed["approvedData"]["reviewHistory"][0]["ruleId"] == "RULE-1"

    for patch, message in [({"ruleType": "story"}, "ruleType"), ({"behavior": ""}, "behavior"), ({"schemaSlot": "missing"}, "schemaSlot")]:
        with pytest.raises(ValueError, match=message):
            apply_gameplay_operations(model, [{"type": "review_rule", "ruleId": "RULE-1", "decision": "approved", "patch": patch}], 1)

    model["approvedData"]["rules"][0].update(semanticValidity="invalid", validationErrors=["fragment"], reviewStatus="needs_revision")
    with pytest.raises(ValueError, match="semantic validity"):
        apply_gameplay_operations(model, [{"type": "review_rule", "ruleId": "RULE-1", "decision": "approved"}], 1)


def test_v2_rule_review_undo_and_redo_keep_projection_confirmation_in_sync():
    model = gameplay_model()
    model["contentModelVersion"] = 2
    model["approvedData"] = {
        "contentModelVersion": 2, "schemaVersion": "chapter-schema-v2",
        "chapters": [{"chapterId": "V2CH-001", "matchedSchema": "chapter-schema-v2:attack:base", "title": "攻击"}],
        "slots": [{"chapterId": "V2CH-001", "slotId": "attack_trigger", "factIds": ["FACT-1"], "status": "confirmed"}],
        "facts": [], "gaps": [], "approvalRevision": 0,
        "rules": [{
            "ruleId": "RULE-1", "semanticKey": "stable-key", "ownerChapterId": "V2CH-001",
            "definitionMode": "primary", "ruleType": "logic", "schemaSlot": "attack_trigger",
            "subject": "武器", "trigger": None, "conditions": [], "behavior": "目标进入射程后攻击",
            "result": None, "stateChange": None, "exitCondition": None, "exception": None,
            "parameterRefs": [], "evidenceIds": ["F0001"], "reviewStatus": "unreviewed",
        }],
    }
    model["ruleIntelligenceProjection"] = build_rule_intelligence_v1(model, model["approvedData"])

    approved = apply_gameplay_operations(model, [{
        "type": "review_rule", "ruleId": "RULE-1", "decision": "approved",
    }], 1)
    undone = undo_gameplay(approved, 2)
    redone = redo_gameplay(undone, 3)

    assert [rule["ruleId"] for rule in approved["ruleIntelligenceProjection"]["publication"]["rules"]] == ["RULE-1"]
    assert undone["approvedData"]["rules"][0]["reviewStatus"] == "unreviewed"
    assert undone["ruleIntelligenceProjection"]["publication"]["rules"] == []
    assert redone["approvedData"]["rules"][0]["reviewStatus"] == "approved"
    assert [rule["ruleId"] for rule in redone["ruleIntelligenceProjection"]["publication"]["rules"]] == ["RULE-1"]


def test_temporal_review_candidate_uses_existing_review_promotion_and_undo_redo():
    model = gameplay_model()
    model["contentModelVersion"] = 2
    model["approvedData"] = {
        "contentModelVersion": 2, "schemaVersion": "chapter-schema-v2",
        "chapters": [{"chapterId": "V2CH-001", "matchedSchema": "chapter-schema-v2:attack:base", "title": "攻击"}],
        "slots": [{"chapterId": "V2CH-001", "slotId": "attack_trigger", "factIds": [], "status": "missing"}],
        "facts": [], "gaps": [], "approvalRevision": 0, "rules": [],
    }
    model["temporalEvidence"] = {
        "facts": [{
            "factId": "TF-1", "subject": "武器", "predicate": "attack_started", "object": "开始攻击",
            "evidenceIds": ["VF-1"], "evidenceTimestamps": [1.0], "reviewStatus": "unreviewed",
            "observationMode": "targeted_temporal_probe", "inferenceLevel": "observed",
        }],
        "ruleCandidates": [{
            "ruleId": "TRC-1", "semanticKey": "temporal-attack-start", "ownerChapterId": "V2CH-001",
            "ruleType": "logic", "schemaSlot": "attack_trigger", "subject": "武器",
            "behavior": "武器在目标出现后开始攻击", "evidenceIds": ["VF-1"], "sourceFactIds": ["TF-1"],
            "reviewStatus": "unreviewed", "candidateKind": "temporal_rule_candidate",
        }],
    }
    model["ruleIntelligenceProjection"] = build_rule_intelligence_v1(model, model["approvedData"])

    assert [item["ruleId"] for item in model["ruleIntelligenceProjection"]["ruleCandidates"]] == ["TRC-1"]
    assert model["approvedData"]["rules"] == []
    assert model["ruleIntelligenceProjection"]["publication"]["rules"] == []

    approved = apply_gameplay_operations(model, [{
        "type": "review_rule", "ruleId": "TRC-1", "decision": "approved",
    }], 1)
    undone = undo_gameplay(approved, 2)
    redone = redo_gameplay(undone, 3)

    assert [item["ruleId"] for item in approved["approvedData"]["rules"]] == ["TRC-1"]
    assert [item["ruleId"] for item in approved["ruleIntelligenceProjection"]["publication"]["rules"]] == ["TRC-1"]
    assert undone["approvedData"]["rules"] == []
    assert undone["ruleIntelligenceProjection"]["publication"]["rules"] == []
    assert [item["ruleId"] for item in redone["ruleIntelligenceProjection"]["publication"]["rules"]] == ["TRC-1"]


def test_speed_change_review_promotes_fact_and_rule_then_keeps_trigger_gap_specific():
    model = gameplay_model()
    model["contentModelVersion"] = 2
    model["approvedData"] = {
        "contentModelVersion": 2, "schemaVersion": "chapter-schema-v2",
        "chapters": [{
            "chapterId": "MOVE", "matchedSchema": "chapter-schema-v2:movement:base",
            "title": "移动", "object": "载具", "chapterType": "movement",
        }],
        "slots": [{"chapterId": "MOVE", "slotId": "movement_rate_change", "factIds": [], "status": "missing"}],
        "facts": [], "gaps": [], "approvalRevision": 0, "rules": [],
    }
    model["temporalEvidence"] = {
        "facts": [{
            "factId": "TF-RATE", "subject": "载具", "predicate": "movement_rate_changed",
            "object": "rate_changed", "evidenceIds": ["VF-1", "VF-5"],
            "reviewStatus": "unreviewed", "inferenceLevel": "observed",
        }],
        "ruleCandidates": [{
            "ruleId": "TRC-RATE", "semanticKey": "temporal:rate", "ownerChapterId": "MOVE",
            "ruleType": "logic", "schemaSlot": "movement_rate_change", "subject": "载具",
            "behavior": "载具移动速度会在关卡过程中发生阶段性变化。",
            "evidenceIds": ["VF-1", "VF-5"], "sourceFactIds": ["TF-RATE"],
            "reviewStatus": "unreviewed", "candidateKind": "temporal_rule_candidate",
            "triggerStatus": "unresolved",
        }],
        "gaps": [{
            "gapId": "G-RATE-TRIGGER", "chapterId": "MOVE", "schemaSlot": "movement_rate_change",
            "gapKind": "speed_change_trigger_unknown", "status": "reviewed_open", "gapDomain": "planning",
            "applicabilityStatus": "applicable", "specificity": "concrete_decision",
            "question": "速度变化的触发条件待确认。",
        }],
    }
    model["ruleIntelligenceProjection"] = build_rule_intelligence_v1(model, model["approvedData"])

    approved = apply_gameplay_operations(model, [{
        "type": "review_rule", "ruleId": "TRC-RATE", "decision": "approved",
    }], 1)

    assert [fact["factId"] for fact in approved["approvedData"]["facts"]] == ["TF-RATE"]
    assert approved["approvedData"]["facts"][0]["reviewStatus"] == "approved"
    assert "阶段性变化" in approved["ruleIntelligenceProjection"]["publication"]["rules"][0]["behavior"]
    assert approved["ruleIntelligenceProjection"]["publication"]["finalPlanningGaps"][0]["question"] == "速度变化的触发条件待确认。"


def test_temporal_probe_result_is_a_revisioned_undoable_review_input():
    model = gameplay_model()
    model["contentModelVersion"] = 2
    model["approvedData"] = {
        "contentModelVersion": 2, "schemaVersion": "chapter-schema-v2",
        "chapters": [], "slots": [], "facts": [], "rules": [], "gaps": [], "approvalRevision": 0,
    }
    result = add_targeted_temporal_probe_result(model, {
        "request": {"probeRequestId": "TPR-1", "sourceGapId": "G1", "status": "completed", "attemptCount": 1},
        "temporalFacts": [{"factId": "TF-1", "reviewStatus": "unreviewed"}],
        "ruleCandidates": [], "observations": [], "gaps": [],
    }, 1)
    undone = undo_gameplay(result, 2)
    redone = redo_gameplay(undone, 3)

    assert result["revision"] == 2
    assert result["temporalProbeRequests"][0]["status"] == "completed"
    assert result["temporalEvidence"]["facts"][0]["factId"] == "TF-1"
    assert undone.get("temporalProbeRequests", []) == []
    assert redone["temporalEvidence"]["facts"][0]["factId"] == "TF-1"


def test_moving_one_mechanism_invalidates_only_its_dependent_output():
    model = gameplay_model()
    model["chapters"][0].update(systemName="战斗", subsystemName="核心战斗", status="reviewed", confirmation={"confirmed": True, "revision": 1})
    model["chapters"][1].update(systemName="成长", subsystemName="奖励", status="reviewed", confirmation={"confirmed": True, "revision": 1})
    structured = normalize_gameplay_structure(model)
    model.update(structured)
    model["diagrams"] = [
        {"id": "GDI-001", "status": "reviewed", "chapterIds": ["GCH-001"]},
        {"id": "GDI-002", "status": "reviewed", "chapterIds": ["GCH-002"]},
    ]

    target_system = model["systems"][1]
    target_subsystem = target_system["subsystems"][0]
    changed = apply_gameplay_operations(model, [{
        "type": "move_chapter", "chapterId": "GCH-001",
        "systemId": target_system["id"], "subsystemId": target_subsystem["id"],
    }], model["revision"])

    assert changed["chapters"][0]["confirmation"]["confirmed"] is False
    assert changed["chapters"][1]["confirmation"]["confirmed"] is True
    assert changed["diagrams"][0]["status"] == "stale"
    assert changed["diagrams"][1]["status"] == "reviewed"


def test_noop_conflict_and_invalid_reference_behavior():
    model = gameplay_model()

    assert apply_gameplay_operations(model, [], model["revision"]) == model
    with pytest.raises(GameplayReviewConflict) as conflict:
        apply_gameplay_operations(model, [], 0)
    assert conflict.value.current_revision == 1
    with pytest.raises(ValueError, match="unknown chapter"):
        apply_gameplay_operations(model, [{"type": "upsert_dependency", "chapterId": "GCH-001", "dependencyId": "GCH-999"}], 1)


def test_all_operation_families_apply_to_canonical_content():
    model = gameplay_model()
    operations = [
        {"type": "set_mechanism_field", "chapterId": "GCH-001", "field": "name", "value": "Combat"},
        {"type": "upsert_claim", "chapterId": "GCH-001", "claim": {"id": "GCL-003", "text": "Hit", "sourceType": "material", "sourceFrameIds": ["F0001"]}},
        {"type": "delete_claim", "chapterId": "GCH-001", "id": "GCL-003"},
        {"type": "upsert_parameter", "chapterId": "GCH-001", "name": "playerGoal", "parameter": {"type": "text", "unit": "n/a", "range": "one", "source": "F0001"}},
        {"type": "delete_parameter", "chapterId": "GCH-001", "name": "playerGoal"},
        {"type": "upsert_dependency", "chapterId": "GCH-002", "dependencyId": "GCH-001"},
        {"type": "delete_dependency", "chapterId": "GCH-002", "dependencyId": "GCH-001"},
        {"type": "upsert_acceptance", "chapterId": "GCH-001", "acceptance": {"id": "GAC-001", "text": "attack works"}},
        {"type": "delete_acceptance", "chapterId": "GCH-001", "id": "GAC-001"},
        {"type": "add_chapter", "chapter": {"scope": "new", "claims": [], "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"]}},
        {"type": "reorder_chapters", "chapterIds": ["GCH-003", "GCH-001", "GCH-002"]},
        {"type": "split_chapter", "chapterId": "GCH-003", "chapter": {"scope": "split", "sourceFrameIds": ["F0001"]}},
        {"type": "merge_chapters", "keepId": "GCH-003", "mergeId": "GCH-004"},
        {"type": "delete_chapter", "chapterId": "GCH-003"},
        {"type": "set_finding_resolution", "id": "FND-001", "resolution": "resolved"},
    ]
    model["reviewState"]["findings"] = [{"id": "FND-001", "severity": "blocker", "status": "open"}]

    result = apply_gameplay_operations(model, operations, model["revision"])

    assert result["revision"] == 2
    assert [chapter["id"] for chapter in result["chapters"]] == ["GCH-001", "GCH-002"]
    assert result["reviewState"]["findings"][0]["status"] == "resolved"


def test_undo_and_redo_restore_content_while_advancing_revision():
    model = gameplay_model()
    changed = apply_gameplay_operations(model, [{"type": "set_chapter_field", "chapterId": "GCH-001", "field": "scope", "value": "changed"}], 1)
    undone = undo_gameplay(changed, 2)
    redone = redo_gameplay(undone, 3)

    assert undone["revision"] == 3
    assert undone["chapters"][0]["scope"] == "combat"
    assert redone["revision"] == 4
    assert redone["chapters"][0]["scope"] == "changed"


def test_reopening_an_already_stale_chapter_is_a_true_noop():
    model = gameplay_model()
    model["chapters"][0].update(status="chapter_review", confirmation={"confirmed": False, "revision": None})
    model["reviewState"]["previewRevision"] = None
    model["editHistory"] = [{"undo": [], "redo": [{"scope": "preserve redo"}]}]

    result = reopen_gameplay_chapter(model, "GCH-001", 1)

    assert result == model
    assert result is not model


@pytest.mark.parametrize("operation", [
    {"type": "upsert_claim", "chapterId": "GCH-001", "claim": {"id": "claim-1", "text": "bad", "sourceType": "material", "sourceFrameIds": ["F0001"]}},
    {"type": "upsert_acceptance", "chapterId": "GCH-001", "acceptance": {"id": "acceptance-1", "text": "bad"}},
])
def test_nested_entity_operations_reject_malformed_ids_without_mutating_input(operation):
    model = gameplay_model()
    original = deepcopy(model)

    with pytest.raises(ValueError, match="id"):
        apply_gameplay_operations(model, [operation], 1)

    assert model == original


def test_nested_entity_operations_generate_ids_unique_across_chapters():
    model = gameplay_model()

    result = apply_gameplay_operations(model, [
        {"type": "upsert_claim", "chapterId": "GCH-002", "claim": {"text": "new", "sourceType": "material", "sourceFrameIds": ["F0002"]}},
        {"type": "upsert_acceptance", "chapterId": "GCH-001", "acceptance": {"text": "first"}},
        {"type": "upsert_acceptance", "chapterId": "GCH-002", "acceptance": {"text": "second"}},
    ], 1)

    assert result["chapters"][1]["claims"][-1]["id"] == "GCL-003"
    assert [chapter["acceptanceCases"][0]["id"] for chapter in result["chapters"]] == ["GAC-001", "GAC-002"]


def test_legacy_check_methods_without_ids_can_be_edited_and_deleted_by_position():
    model = gameplay_model()
    model["chapters"][0]["acceptanceCases"] = [
        {"case": "点击刷新", "expected": "选项重新生成"},
        {"case": "选择强化", "expected": "强化立即生效"},
    ]

    edited = apply_gameplay_operations(model, [{
        "type": "upsert_acceptance", "chapterId": "GCH-001", "acceptanceIndex": 0,
        "acceptance": {"case": "点击刷新按钮", "expected": "三个选项重新生成"},
    }], 1)
    assert edited["chapters"][0]["acceptanceCases"][0] == {
        "id": "GAC-001", "case": "点击刷新按钮", "expected": "三个选项重新生成",
    }
    assert len(edited["chapters"][0]["acceptanceCases"]) == 2

    deleted = apply_gameplay_operations(edited, [{
        "type": "delete_acceptance", "chapterId": "GCH-001", "acceptanceIndex": 1,
    }], 2)
    assert len(deleted["chapters"][0]["acceptanceCases"]) == 1


def test_confirmation_requires_complete_chapter_and_reopen_stales_diagrams():
    model = gameplay_model()
    chapter = model["chapters"][0]
    chapter["parameters"] = {"伤害数值": {"type": "number", "unit": "点", "range": "", "source": "F0001"}}
    with pytest.raises(ValueError, match="parameter"):
        confirm_gameplay_chapter(model, "GCH-001", 1)
    chapter["parameters"]["伤害数值"]["range"] = "1-9999"
    model["diagrams"] = [{"id": "GDI-001", "status": "reviewed", "chapterIds": ["GCH-001"]}]

    confirmed = confirm_gameplay_chapter(model, "GCH-001", 1)
    reopened = reopen_gameplay_chapter(confirmed, "GCH-001", 2)

    assert confirmed["chapters"][0]["status"] == "approved"
    assert confirmed["chapters"][0]["confirmation"] == {"confirmed": True, "revision": 2}
    assert reopened["chapters"][0]["status"] == "chapter_review"
    assert reopened["diagrams"][0]["status"] == "stale"


def test_confirmation_does_not_require_mechanism_rules_as_numeric_parameters():
    model = gameplay_model()
    model["chapters"][0]["parameters"] = {
        "选项数量": {"type": "number", "unit": "个", "range": "3", "source": "F0001"},
    }

    confirmed = confirm_gameplay_chapter(model, "GCH-001", 1)

    assert confirmed["chapters"][0]["confirmation"]["confirmed"] is True


def test_confirmed_approved_chapter_satisfies_the_gameplay_gate():
    model = gameplay_model()
    model["chapters"] = [model["chapters"][0]]
    chapter = model["chapters"][0]
    chapter["parameters"] = {field: {"type": "text", "unit": "n/a", "range": "one", "source": "F0001"} for field in required_parameter_fields("core_loop")}

    confirmed = confirm_gameplay_chapter(model, "GCH-001", 1)

    assert gameplay_gate(confirmed, {"revision": 7})["exportReady"] is True


def test_conditional_confirmation_persists_a_reviewed_chapter_without_blocking_unknowns():
    model = gameplay_model()
    model["chapters"] = [model["chapters"][0]]
    chapter = model["chapters"][0]
    chapter["unknowns"] = ["动画时机待确认"]
    chapter["parameters"] = {field: {"type": "text", "unit": "n/a", "range": "one", "source": "F0001"} for field in required_parameter_fields("core_loop")}
    model["reviewState"]["findings"] = [{"id": "FND-001", "severity": "warning", "status": "open"}]

    conditional = confirm_gameplay_chapter(model, "GCH-001", 1, decision="conditional")

    assert conditional["chapters"][0]["status"] == "conditional"
    assert conditional["chapters"][0]["confirmation"] == {"confirmed": True, "revision": 2, "decision": "conditional"}
    assert gameplay_gate(conditional, {"revision": 7})["exportReady"] is True
    with pytest.raises(ValueError, match="decision"):
        confirm_gameplay_chapter(model, "GCH-001", 1, decision="unsupported")


def test_rejected_decision_persists_without_bypassing_the_export_gate():
    model = gameplay_model()

    rejected = confirm_gameplay_chapter(model, "GCH-001", 1, decision="rejected")

    assert rejected["chapters"][0]["status"] == "rejected"
    assert rejected["chapters"][0]["confirmation"] == {"confirmed": False, "revision": 2, "decision": "rejected"}
    assert "GCH-001" in gameplay_gate(rejected, {"revision": 7})["blockers"]


def test_not_applicable_chapter_is_confirmed_without_blocking_export():
    model = gameplay_model()
    model["chapters"] = [model["chapters"][0]]

    skipped = confirm_gameplay_chapter(model, "GCH-001", 1, decision="not_applicable")

    assert skipped["chapters"][0]["status"] == "not_applicable"
    assert skipped["chapters"][0]["confirmation"] == {
        "confirmed": True,
        "revision": 2,
        "decision": "not_applicable",
    }
    assert gameplay_gate(skipped, {"revision": 7})["exportReady"] is True


def test_resolve_decision_card_promotes_choice_to_planner_rule_and_clears_pending_question():
    model = gameplay_model()
    chapter = model["chapters"][0]
    chapter["unknowns"] = ["这一环节是如何触发的？"]
    chapter["decisionCards"] = [{
        "id": "GDC-001", "question": "这一环节是如何触发的？", "selectionMode": "single",
        "options": [{"id": "wave", "label": "击败当前一波敌人后自动出现"}, {"id": "level", "label": "经验达到升级条件后自动出现", "recommended": True, "reason": "相邻截图出现升级界面"}],
        "allowCustom": True, "evidence": [{"frameId": "F0001", "label": "升级界面截图"}],
        "impacts": ["玩法正文", "策划草图", "最终文档"], "status": "pending",
    }]
    result = apply_gameplay_operations(model, [{"type": "resolve_decision_card", "chapterId": "GCH-001", "cardId": "GDC-001", "selectedOptionIds": ["level"]}], model["revision"])
    resolved = result["chapters"][0]["decisionCards"][0]
    assert resolved["status"] == "resolved"
    assert resolved["resolvedText"] == "经验达到升级条件后自动出现"
    assert result["chapters"][0]["unknowns"] == []
    assert result["chapters"][0]["claims"][-1]["text"] == "经验达到升级条件后自动出现"
    assert result["chapters"][0]["claims"][-1]["sourceType"] == "planner"
    assert result["chapters"][0]["plannerSections"]["keyRules"][-1] == "这一环节是如何触发的：经验达到升级条件后自动出现"


def test_stale_browser_can_submit_a_legacy_decision_id_during_normalization():
    model = gameplay_model()
    chapter = model["chapters"][0]
    chapter["decisionCards"] = [{
        "id": "GDC-GCH-001-legacy-choice", "question": "历史规则采用哪一种处理方式？",
        "selectionMode": "single", "options": [{"id": "a", "label": "方案 A"}, {"id": "b", "label": "方案 B"}],
        "allowCustom": True, "status": "pending",
    }]

    result = apply_gameplay_operations(model, [{
        "type": "resolve_decision_card", "chapterId": "GCH-001",
        "cardId": "GDC-GCH-001-legacy-choice", "selectedOptionIds": ["a"],
    }], model["revision"])

    assert result["chapters"][0]["decisionCards"][0]["id"] == "GDC-001"
    assert result["chapters"][0]["decisionCards"][0]["status"] == "resolved"


def test_decision_card_rejects_multiple_single_choice_without_mutation():
    model = gameplay_model()
    model["chapters"][0]["decisionCards"] = [{"id": "GDC-001", "question": "如何触发？", "selectionMode": "single", "options": [{"id": "a", "label": "自动"}, {"id": "b", "label": "手动"}], "allowCustom": True, "status": "pending"}]
    before = deepcopy(model)
    with pytest.raises(ValueError, match="exactly one"):
        apply_gameplay_operations(model, [{"type": "resolve_decision_card", "chapterId": "GCH-001", "cardId": "GDC-001", "selectedOptionIds": ["a", "b"]}], 1)
    assert model == before


def test_adopting_a_field_name_card_marks_the_nearby_mapping_as_confirmed():
    model = gameplay_model()
    chapter = model["chapters"][0]
    chapter["fieldDictionary"] = [{
        "plannerName": "武器名称", "suggestedCodeName": "weaponLabel", "status": "suggested",
    }]
    chapter["decisionCards"] = [{
        "id": "GDC-001", "question": "武器名称使用哪个程序字段？", "selectionMode": "single",
        "options": [{"id": "weapon-name", "label": "weaponName"}, {"id": "weapon-id", "label": "weaponId"}],
        "allowCustom": True, "status": "pending",
        "target": {"type": "field_dictionary", "plannerName": "武器名称"},
    }]

    result = apply_gameplay_operations(model, [{
        "type": "resolve_decision_card", "chapterId": "GCH-001", "cardId": "GDC-001",
        "selectedOptionIds": ["weapon-name"],
    }], model["revision"])

    mapping = result["chapters"][0]["fieldDictionary"][0]
    assert mapping["suggestedCodeName"] == "weaponName"
    assert mapping["status"] == "confirmed"
    assert mapping["decisionStatus"] == "accepted"


def test_skip_decision_card_keeps_it_unresolved_without_promoting_a_conclusion():
    model = gameplay_model()
    model["chapters"][0]["decisionCards"] = [{"id": "GDC-001", "question": "如何触发？", "selectionMode": "single", "options": [{"id": "a", "label": "自动"}, {"id": "b", "label": "手动"}], "allowCustom": True, "status": "pending"}]
    result = apply_gameplay_operations(model, [{"type": "skip_decision_card", "chapterId": "GCH-001", "cardId": "GDC-001"}], 1)
    assert result["chapters"][0]["decisionCards"][0]["status"] == "skipped"
    assert result["chapters"][0]["claims"] == model["chapters"][0]["claims"]


def test_first_decision_card_edit_migrates_historical_chapters_without_the_field():
    model = gameplay_model()
    for chapter in model["chapters"]:
        chapter.pop("decisionCards", None)
    cards = [{
        "id": "GDC-001", "question": "强化如何触发？", "selectionMode": "single", "status": "pending",
        "allowCustom": True, "options": [{"id": "auto", "label": "升级后自动出现"}, {"id": "manual", "label": "玩家手动打开"}],
        "evidence": [{"frameId": "F0001", "label": "强化界面截图"}], "impacts": ["玩法正文", "最终文档"],
    }]

    result = apply_gameplay_operations(model, [{"type": "set_chapter_field", "chapterId": "GCH-001", "field": "decisionCards", "value": cards}], 1)

    assert result["chapters"][0]["decisionCards"] == cards
    assert result["chapters"][1]["decisionCards"] == []
