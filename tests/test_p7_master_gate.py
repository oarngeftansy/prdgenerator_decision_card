from backend.p7_master_gate import combine_master_p7_gate, is_planner_superseded_blocker, merge_completion_snapshot


def test_only_planner_depth_blockers_are_superseded():
    assert is_planner_superseded_blocker("GCH-001:RULES_MISSING")
    assert is_planner_superseded_blocker("GCH-001:LEAD_PLANNER_RULE_DEPTH_INSUFFICIENT")
    assert is_planner_superseded_blocker("STRUCTURED_SCHEMA_CLOSURE_INCOMPLETE")
    assert not is_planner_superseded_blocker("INTERACTION_REVISION_STALE")
    assert not is_planner_superseded_blocker("GDI-001")
    assert not is_planner_superseded_blocker("TABLE_INVALID")
    assert not is_planner_superseded_blocker("MODEL_INVALID")


def test_master_ready_does_not_bypass_delivery_safety():
    legacy = {
        "blockerIds": [
            "GCH-001:RULES_MISSING",
            "GCH-001:VERIFICATION_MISSING",
            "INTERACTION_REVISION_STALE",
            "GDI-001",
        ]
    }
    gate = combine_master_p7_gate(legacy, master_ready=True, master_quality={"ready": True})
    assert gate["plannerSupersededBlockerIds"] == [
        "GCH-001:RULES_MISSING",
        "GCH-001:VERIFICATION_MISSING",
    ]
    assert gate["blockerIds"] == ["INTERACTION_REVISION_STALE", "GDI-001"]
    assert gate["ready"] is False


def test_master_ready_can_close_legacy_planner_only_gate():
    legacy = {
        "blockerIds": ["GCH-001:GAMEPLAY_DEPTH_INSUFFICIENT", "GCH-001:BOUNDARY_OR_CONFIGURATION_MISSING"],
        "completionSnapshot": {
            "checks": [
                {"id": "rules", "label": "规则审核", "done": False, "detail": "未通过"},
                {"id": "interaction", "label": "交互审核", "done": True, "detail": "已通过"},
            ],
            "steps": [{"id": "rules", "done": False}, {"id": "export", "done": False}],
        },
    }
    quality = {"ready": True, "overall": 91, "criticalIssues": []}
    gate = combine_master_p7_gate(legacy, master_ready=True, master_quality=quality)
    assert gate["ready"] is True
    assert gate["blockerIds"] == []
    snapshot = merge_completion_snapshot(legacy["completionSnapshot"], gate, master_quality=quality)
    assert snapshot["ready"] is True
    assert snapshot["percent"] == 100
    assert next(item for item in snapshot["checks"] if item["id"] == "rules")["done"] is True
    assert next(item for item in snapshot["steps"] if item["id"] == "export")["done"] is True


def test_master_not_ready_is_explicit_blocker():
    quality = {"ready": False, "criticalIssues": ["mechanic_closure_incomplete"]}
    gate = combine_master_p7_gate({"blockerIds": []}, master_ready=False, master_quality=quality)
    assert gate["ready"] is False
    assert "MASTER_PLANNING_NOT_READY" in gate["blockerIds"]
    assert "MASTER_PLANNING:mechanic_closure_incomplete" in gate["blockerIds"]
