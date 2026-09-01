from copy import deepcopy

from backend.gameplay_review_model import build_gameplay_review_model
from backend.gameplay_review_service import apply_gameplay_operations, redo_gameplay, undo_gameplay
from backend.planner_feedback_assimilation import assimilate_planner_feedback, build_feedback_trace
from backend.rule_intelligence_pipeline import build_rule_intelligence_projection


def _approved():
    return {
        "approvalRevision": 7,
        "feedbackRevision": 0,
        "facts": [], "parameters": [{"parameterId": "P1", "sourceKind": "observed_value"}],
        "gaps": [{"gapId": "G1", "chapterId": "C1", "schemaSlot": "victory_condition", "status": "open"}],
        "rules": [{
            "ruleId": "R1", "subject": "武器", "behavior": "武器向目标发射投射物",
            "intent": "TargetSelection", "schemaSlot": "attack_target", "ownerChapterId": "C1",
            "reviewStatus": "approved", "semanticValidity": "valid", "evidenceIds": ["E1"],
        }],
        "chapters": [{"chapterId": "C1", "chapterType": "attack", "title": "攻击"}],
    }


def _feedback(scope="project_feedback", review="approved"):
    return {
        "feedbackId": "PF-1", "scope": scope, "text": "该规则描述攻击方式，不是目标选择。",
        "sourceRevision": 7, "reviewStatus": review,
        "requestedOperations": [{
            "operationId": "PFO-1", "operationType": "patch_rule_intent", "targetRuleId": "R1",
            "after": {"intent": "AttackMode"}, "status": review,
        }, {
            "operationId": "PFO-2", "operationType": "move_rule_schema_slot", "targetRuleId": "R1",
            "after": {"schemaSlot": "attack_method"}, "status": review,
        }],
    }


def test_project_feedback_applies_approved_operations_with_revision_lineage():
    source = _approved(); source["plannerFeedback"] = [_feedback()]
    result = assimilate_planner_feedback(source)

    rule = result["effectiveApprovedData"]["rules"][0]
    assert rule["intent"] == "AttackMode"
    assert rule["schemaSlot"] == "attack_method"
    assert len(result["appliedOperations"]) == 2
    assert result["effectiveApprovedData"]["feedbackRevision"] == 1
    assert result["lineage"][0] == {
        "feedbackId": "PF-1", "operationId": "PFO-1", "operation": "patch_rule_intent",
        "targetRuleId": "R1", "schemaResponsibility": None,
        "before": {"intent": "TargetSelection"}, "after": {"intent": "AttackMode"},
        "sourceRevision": 7, "appliedRevision": 1,
    }
    assert source["rules"][0]["intent"] == "TargetSelection"


def test_unreviewed_project_feedback_is_reviewable_but_not_applied():
    source = _approved(); source["plannerFeedback"] = [_feedback(review="proposed")]
    result = assimilate_planner_feedback(source)

    assert result["effectiveApprovedData"]["rules"][0]["intent"] == "TargetSelection"
    assert len(result["proposedOperations"]) == 2
    assert result["appliedOperations"] == []


def test_system_feedback_only_creates_architecture_candidate():
    source = _approved(); source["plannerFeedback"] = [_feedback(scope="system_feedback")]
    result = assimilate_planner_feedback(source)

    assert result["effectiveApprovedData"]["rules"] == source["rules"]
    assert result["appliedOperations"] == []
    assert result["architectureImprovementCandidates"][0]["feedbackId"] == "PF-1"


def test_feedback_can_resolve_gap_and_patch_parameter_with_lineage():
    feedback = {
        "feedbackId": "PF-2", "scope": "project_feedback", "text": "确认缺口和参数来源。",
        "sourceRevision": 7, "reviewStatus": "approved", "requestedOperations": [
            {"operationId": "PFO-3", "operationType": "resolve_gap", "targetGapId": "G1", "after": {"status": "resolved"}, "status": "approved"},
            {"operationId": "PFO-4", "operationType": "patch_parameter", "targetParameterId": "P1", "after": {"sourceKind": "configured_value"}, "status": "approved"},
        ],
    }
    source = _approved(); source["plannerFeedback"] = [feedback]
    result = assimilate_planner_feedback(source)

    assert result["effectiveApprovedData"]["gaps"][0]["status"] == "resolved"
    assert result["effectiveApprovedData"]["parameters"][0]["sourceKind"] == "configured_value"
    assert {item["operation"] for item in result["lineage"]} == {"resolve_gap", "patch_parameter"}


def test_rule_pipeline_reprojects_assimilated_feedback_and_exposes_lineage():
    source = _approved(); source["plannerFeedback"] = [_feedback()]
    result = build_rule_intelligence_projection(approved_data=source, chapters=source["chapters"])

    assert result["rules"][0]["intent"] == "AttackMode"
    assert result["rules"][0]["schemaSlot"] == "attack_method"
    assert result["feedbackAssimilation"]["lineage"][0]["feedbackId"] == "PF-1"


def test_feedback_review_operation_is_revisioned_undoable_and_redoable():
    model = build_gameplay_review_model(
        {"id": "feedback-job", "contentModelVersion": 2, "frames": [{"id": "F0001"}]},
        [{"scope": "attack", "claims": [{"id": "GCL-001", "text": "武器向目标发射投射物", "sourceType": "material", "sourceFrameIds": ["F0001"]}], "mechanism": {"type": "core_loop"}, "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"]}],
    )
    target = model["approvedData"]["rules"][0]
    original_intent = model["ruleIntelligenceProjection"]["rules"][0]["intent"]
    feedback = _feedback(review="proposed")
    feedback["requestedOperations"] = [feedback["requestedOperations"][0]]
    feedback["requestedOperations"][0]["targetRuleId"] = target["ruleId"]
    registered = apply_gameplay_operations(model, [{"type": "register_planner_feedback", "feedback": feedback}], 1)
    approved_model = apply_gameplay_operations(registered, [{
        "type": "review_planner_feedback_operation", "feedbackId": "PF-1", "operationId": "PFO-1", "decision": "approved",
    }], 2)
    undone = undo_gameplay(approved_model, 3)
    redone = redo_gameplay(undone, 4)

    assert registered["revision"] == 2
    assert approved_model["ruleIntelligenceProjection"]["rules"][0]["intent"] == "AttackMode"
    assert undone["ruleIntelligenceProjection"]["rules"][0]["intent"] == original_intent
    assert redone["ruleIntelligenceProjection"]["rules"][0]["intent"] == "AttackMode"


def test_feedback_trace_persists_verification_anchors_without_mutating_rule_authority():
    source = _approved()
    original = deepcopy(source)
    trace = build_feedback_trace([{
        "feedbackId": "PF-1",
        "affected": {
            "policyIds": ["POLICY-ATTACK-OWNERSHIP"],
            "ruleIds": ["R1"],
            "gapIds": ["G1"],
            "testIds": ["test_attack_mode_slot"],
            "finalAnchors": ["武器/攻击"],
        },
        "verificationStatus": "fully_reflected",
    }], last_verified_revision=12)

    assert trace == {
        "schemaVersion": "feedback-trace-v1",
        "records": [{
            "feedbackId": "PF-1",
            "affected": {
                "policyIds": ["POLICY-ATTACK-OWNERSHIP"],
                "ruleIds": ["R1"],
                "gapIds": ["G1"],
                "testIds": ["test_attack_mode_slot"],
                "finalAnchors": ["武器/攻击"],
            },
            "verificationStatus": "fully_reflected",
            "lastVerifiedRevision": 12,
        }],
    }
    assert source == original
