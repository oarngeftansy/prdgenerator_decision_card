from copy import deepcopy

from backend.approved_information_recovery import recover_approved_information
from backend.mechanic_reconstruction import reconstruct_publication
from backend.recovered_rule_dependency_closure import close_recovered_rule_dependencies
from backend.system_lesson_registry import SystemLessonRegistry, load_system_lesson_registry


def _without(lesson_id: str) -> SystemLessonRegistry:
    payload = deepcopy(load_system_lesson_registry().payload)
    next(item for item in payload["lessons"] if item["lessonId"] == lesson_id)["status"] = "candidate"
    return SystemLessonRegistry.from_payload(payload)


def test_confirmed_overview_recovery_depends_on_approved_lesson():
    data = {"rules": [], "facts": [], "directory": {
        "status": "confirmed", "revision": 3,
        "understanding": {"basicFlow": "当守卫核心被击破后，挑战成功并进入结算。"},
    }}
    chapters = [{"chapterId": "RESULT", "title": "结果", "schemaResponsibilities": ["victory_condition"]}]

    enabled = recover_approved_information(data, chapters)
    disabled = recover_approved_information(
        data, chapters, lesson_registry=_without("LESSON-APPROVED-NARRATIVE-RECOVERY")
    )

    assert enabled["rules"][0]["intent"] == "VictoryCondition"
    assert disabled["rules"] == []
    assert disabled["policyStatus"] == "disabled"


def test_trivial_clause_suppression_depends_on_rule_value_lesson():
    rule = {
        "ruleId": "R-DEATH", "behavior": "单位死亡后停止攻击，取消尚未结算的伤害，并不再作为攻击目标。",
        "intent": "Death", "schemaSlot": "death", "ruleType": "logic", "subject": "单位",
        "canonicalOwner": "ENTITY", "definitionMode": "full_definition", "confirmationStatus": "confirmed",
        "publicationEligibility": "eligible", "reviewStatus": "approved",
    }
    chapters = [{"chapterId": "ENTITY", "title": "单位", "entityScope": ["单位"]}]

    enabled = reconstruct_publication(rules=[rule], chapters=chapters, gaps=[])
    disabled = reconstruct_publication(
        rules=[rule], chapters=chapters, gaps=[], lesson_registry=_without("LESSON-RULE-PUBLICATION-VALUE")
    )

    assert "不再作为攻击目标" not in enabled["mechanicFlows"][0]["steps"][0]["text"]
    assert "不再作为攻击目标" in disabled["mechanicFlows"][0]["steps"][0]["text"]


def test_dependency_closure_and_run_specific_value_depend_on_their_lessons():
    recovered = {
        "ruleId": "R-RESULT", "behavior": "当守卫被击败后挑战成功", "intent": "VictoryCondition",
        "schemaSlot": "victory_condition", "subject": "关卡", "ownerChapterId": "RESULT",
        "reviewStatus": "approved", "inferenceLevel": "approved_information_recovery",
        "referencedEntities": [{"name": "守卫", "requiredState": "defeated_state"}],
    }
    chapters = [
        {"chapterId": "ENTITY", "title": "守卫", "entityScope": ["守卫"], "status": "approved"},
        {"chapterId": "RESULT", "title": "结果", "entityScope": ["关卡", "结算"], "status": "approved"},
    ]
    data = {"rules": [], "facts": [], "approvedNarratives": []}
    enabled_closure = close_recovered_rule_dependencies(approved_data=data, chapters=chapters, rules=[recovered])
    disabled_closure = close_recovered_rule_dependencies(
        approved_data=data, chapters=chapters, rules=[recovered],
        lesson_registry=_without("LESSON-RECOVERED-DEPENDENCY-CLOSURE"),
    )
    assert enabled_closure["references"]
    assert disabled_closure["references"] == []

    reward = {
        "ruleId": "R-REWARD", "behavior": "本次结算发放100金币。", "intent": "Reward",
        "schemaSlot": "reward", "ruleType": "logic", "subject": "结算", "canonicalOwner": "RESULT",
        "definitionMode": "full_definition", "confirmationStatus": "confirmed", "publicationEligibility": "eligible",
        "reviewStatus": "approved", "valueAuthority": "observed_run_value",
    }
    enabled_value = reconstruct_publication(rules=[reward], chapters=chapters, gaps=[])
    disabled_value = reconstruct_publication(
        rules=[reward], chapters=chapters, gaps=[],
        lesson_registry=_without("LESSON-RUN-SPECIFIC-EVIDENCE-BOUNDARY"),
    )
    assert "100" not in enabled_value["mechanicFlows"][0]["steps"][0]["text"]
    assert "100" in disabled_value["mechanicFlows"][0]["steps"][0]["text"]
