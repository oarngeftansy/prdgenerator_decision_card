from copy import deepcopy

from backend.mechanic_reconstruction import reconstruct_publication
from backend.requirement_temporal_probe import run_targeted_temporal_probe
from backend.system_lesson_registry import SystemLessonRegistry, load_system_lesson_registry


def _without(lesson_id: str) -> SystemLessonRegistry:
    payload = deepcopy(load_system_lesson_registry().payload)
    next(item for item in payload["lessons"] if item["lessonId"] == lesson_id)["status"] = "candidate"
    return SystemLessonRegistry.from_payload(payload)


def test_rate_delta_candidate_depends_on_temporal_lesson_and_never_becomes_approved_rule():
    request = {"probeRequestId": "TPR-GENERIC", "status": "pending", "probeType": "PersistentStateProbe", "targetProperty": "movement_rate", "entityId": "E-1", "ownerChapterId": "MOVE"}
    observations = []
    for index, x in enumerate([0, 2, 4, 6, 12, 18]):
        observations.append({"frameId": f"F-{index}", "timestamp": index, "bbox": [x, 0, x + 2, 2], "backgroundDelta": [0, 0], "uiDelta": [0, 0], "anchorEntityMatch": True, "trackId": "T-1"})
    track = {"trackCandidateId": "TTC-1", "entityId": "E-1", "identityStatus": "confirmed", "trackConfidence": .95, "observations": observations}
    index = {"duration": 5, "activityWindows": [{"start": 0, "end": 5, "score": 1}]}

    enabled = run_targeted_temporal_probe(request, temporal_index=index, track_candidate=track)
    disabled = run_targeted_temporal_probe(
        request, temporal_index=index, track_candidate=track,
        lesson_registry=_without("LESSON-PERSISTENT-TEMPORAL-STATE"),
    )

    assert any(rule.get("candidateSubtype") == "MovementSpeedChangeCandidate" for rule in enabled["ruleCandidates"])
    assert enabled.get("approvedRules", []) == []
    assert not any(rule.get("candidateSubtype") == "MovementSpeedChangeCandidate" for rule in disabled["ruleCandidates"])


def _rule(rule_id, text, slot):
    return {"ruleId": rule_id, "behavior": text, "intent": "CandidateGeneration", "schemaSlot": slot,
            "ruleType": "logic", "subject": "选择系统", "canonicalOwner": "CHOICE",
            "definitionMode": "full_definition", "confirmationStatus": "confirmed",
            "publicationEligibility": "eligible", "reviewStatus": "approved"}


def test_semantic_narrative_order_depends_on_ordering_lesson_not_input_order():
    rules = [
        _rule("N", "效果数值提高20%", "effect_parameter"),
        _rule("E", "完成选择后退出界面", "selection_exit"),
        _rule("S", "玩家选择一项内容", "candidate_selection"),
        _rule("T", "进度提升时触发选择", "random_trigger"),
        _rule("G", "系统生成三项内容", "candidate_pool_source"),
    ]
    chapters = [{"chapterId": "CHOICE", "title": "选择", "chapterType": "randomization", "entityScope": ["选择系统"]}]

    enabled = reconstruct_publication(rules=rules, chapters=chapters, gaps=[])
    disabled = reconstruct_publication(
        rules=rules, chapters=chapters, gaps=[], lesson_registry=_without("LESSON-MECHANIC-NARRATIVE-ORDERING")
    )

    assert [step["ruleId"] for step in enabled["mechanicFlows"][0]["steps"]] == ["T", "G", "S", "E", "N"]
    assert [step["ruleId"] for step in disabled["mechanicFlows"][0]["steps"]] == ["N", "E", "S", "T", "G"]
