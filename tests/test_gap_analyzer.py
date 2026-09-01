from backend.gap_analyzer import analyze_gaps


def _approved(chapter, slots, rules=(), facts=()):
    return {"contentModelVersion": 2, "chapters": [chapter], "slots": list(slots), "rules": list(rules), "facts": list(facts)}


def test_gap_analyzer_uses_applicable_slots_and_ignores_inferred_facts():
    chapter = {"chapterId": "C1", "title": "移动", "chapterType": "movement", "mechanicVariant": None, "classificationEvidence": []}
    data = _approved(chapter, [
        {"chapterId": "C1", "slotId": "movement_trigger", "factIds": ["F1"], "status": "confirmed"},
        {"chapterId": "C1", "slotId": "movement_speed_source", "factIds": [], "status": "missing"},
        {"chapterId": "C1", "slotId": "movement_stop_condition", "factIds": ["F2"], "status": "confirmed"},
    ], facts=[
        {"factId": "F1", "evidenceLevel": "observed", "semanticValidity": "valid"},
        {"factId": "F2", "evidenceLevel": "inferred", "semanticValidity": "valid"},
    ])
    result = analyze_gaps(data)
    assert {gap["schemaSlot"] for gap in result["gaps"]} == {"movement_speed_source", "movement_stop_condition"}
    assert result["metrics"]["inferredFactsClosingGaps"] == 0
    assert all("待确认" not in gap["question"] for gap in result["gaps"])


def test_three_choice_only_generates_applicable_business_questions_without_inventing_optional_mechanics():
    chapter = {"chapterId": "C1", "title": "候选", "chapterType": "randomization", "mechanicVariant": "three_choice", "classificationEvidence": ["mechanicVariant 命中‘三选一’", "evidence 命中‘刷新’"]}
    refresh = {**chapter, "chapterId": "C2", "title": "刷新"}
    data = {
        "contentModelVersion": 2, "chapters": [chapter, refresh], "slots": [], "facts": [],
        "rules": [{"ruleId": "R-REFRESH", "ownerChapterId": "C2", "schemaSlot": "refresh_rule", "behavior": "玩家点击刷新按钮", "semanticValidity": "valid"}],
    }
    result = analyze_gaps(data)
    slots = [gap["schemaSlot"] for gap in result["gaps"]]
    for required in ("candidate_pool_source", "pool_entry_condition", "pool_exit_condition", "empty_result_rule", "refresh_rule", "refresh_count", "refresh_cost", "selection_pause", "confirm_effect_timing"):
        assert required in slots
    for optional_without_evidence in ("duplicate_rule", "replacement_rule", "weight_rule", "max_level_rule", "prerequisite_rule"):
        assert optional_without_evidence not in slots
    assert len(slots) == len(set(slots))
    assert all(not gap.get("answer") for gap in result["gaps"])
    assert {gap["severity"] for gap in result["gaps"]} <= {"implementation_blocking", "qa_blocking", "documentation_gap"}


def test_classification_hint_alone_does_not_activate_weight_gap():
    chapter = {
        "chapterId": "C1", "title": "候选", "chapterType": "randomization",
        "mechanicVariant": "three_choice", "classificationEvidence": ["evidence:1 命中“权重”"],
    }
    result = analyze_gaps({"contentModelVersion": 2, "chapters": [chapter], "slots": [], "rules": [], "facts": []})

    assert not any(gap["schemaSlot"] == "weight_rule" for gap in result["gaps"])


def test_confirmed_movement_with_video_context_activates_rate_change_probe_responsibility():
    chapter = {
        "chapterId": "C1", "title": "移动", "chapterType": "movement", "mechanicVariant": None,
        "classificationEvidence": [], "temporalProbeContext": {
            "subjectEntityId": "vehicle-1",
            "anchor": {"sourceVideoId": "video-v1", "sourceVideoTrackId": "T1"},
            "searchWindow": {"start": 0, "end": 10}, "sourceEvidenceRevision": "video-v1",
        },
    }
    result = analyze_gaps(_approved(chapter, [], rules=[{
        "ruleId": "MOVE", "ownerChapterId": "C1", "schemaSlot": "movement_direction",
        "behavior": "对象持续移动", "reviewStatus": "approved", "semanticValidity": "valid",
        "sourceFactIds": ["F1"],
    }], facts=[{"factId": "F1", "evidenceLevel": "observed", "semanticValidity": "valid"}]))

    gap = next(item for item in result["gaps"] if item["schemaSlot"] == "movement_rate_change")
    assert gap["probeEligible"] is True
    assert gap["targetProperty"] == "movement_rate"
    assert gap["gapKind"] == "missing_temporal_responsibility"
