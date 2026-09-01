import json
from copy import deepcopy
from pathlib import Path

from backend.rule_intelligence_pipeline import build_rule_intelligence_projection
from backend.system_lesson_registry import SystemLessonRegistry, load_system_lesson_registry


ROOT = Path(__file__).resolve().parents[1]


def _registry_without(lesson_id: str) -> SystemLessonRegistry:
    payload = deepcopy(load_system_lesson_registry().payload)
    next(item for item in payload["lessons"] if item["lessonId"] == lesson_id)["status"] = "candidate"
    return SystemLessonRegistry.from_payload(payload)


def _rule(rule_id: str, behavior: str, **extra):
    return {
        "ruleId": rule_id,
        "behavior": behavior,
        "intent": extra.pop("intent", "CandidateGeneration"),
        "schemaSlot": extra.pop("schemaSlot", "candidate_pool_source"),
        "ruleType": "logic",
        "subject": extra.pop("subject", "选择系统"),
        "ownerChapterId": "CHOICE",
        "reviewStatus": "approved",
        "semanticValidity": "valid",
        "evidenceIds": [f"E-{rule_id}"],
        "sourceFactIds": [f"F-{rule_id}"],
        **extra,
    }


def _projection(rules, *, parameters=None, lesson_registry=None):
    return build_rule_intelligence_projection(
        approved_data={"rules": rules, "facts": [], "parameters": parameters or [], "gaps": []},
        chapters=[{"chapterId": "CHOICE", "title": "选择", "entityScope": ["选择系统", "炮塔"]}],
        lesson_registry=lesson_registry,
    )


def test_attack_responsibility_correction_depends_on_approved_system_lesson():
    rule = _rule(
        "R-MODE",
        "炮塔向目标发射能量束",
        intent="TargetSelection",
        schemaSlot="attack_target",
        subject="炮塔",
    )

    enabled = _projection([rule])
    disabled = _projection([rule], lesson_registry=_registry_without("LESSON-RULE-INTENT-RESPONSIBILITY"))

    assert enabled["rules"][0]["intent"] == "AttackMode"
    assert enabled["rules"][0]["schemaSlot"] == "attack_method"
    assert disabled["rules"][0]["intent"] == "TargetSelection"
    assert disabled["rules"][0]["schemaSlot"] == "attack_target"


def test_pattern_inference_depends_on_lesson_but_formula_guard_remains_fail_closed():
    parameter = {"parameterId": "P-1", "sourceKind": "observed_value", "observedValues": [4, 8, 12, 16]}

    enabled = _projection([], parameters=[parameter])
    disabled = _projection(
        [],
        parameters=[parameter],
        lesson_registry=_registry_without("LESSON-EVIDENCE-PARAMETER-AUTHORITY"),
    )

    assert enabled["parameters"][0]["sourceKind"] == "inferred_pattern"
    assert enabled["publication"]["formulae"] == []
    assert disabled["parameters"][0]["sourceKind"] == "observed_value"
    assert disabled["publication"]["formulae"] == []

    random_rule = _rule("R-RANDOM", "系统按等概率无放回抽取内容")
    enabled_random = _projection([random_rule])
    disabled_random = _projection(
        [random_rule], lesson_registry=_registry_without("LESSON-EVIDENCE-PARAMETER-AUTHORITY")
    )
    assert enabled_random["rules"][0]["guardReasons"] == ["unsupported_random_mechanic"]
    assert disabled_random["rules"][0]["guardReasons"] == ["random_strength_policy_unavailable"]
    assert disabled_random["rules"][0]["publicationEligibility"] == "blocked"


def test_explicit_heterogeneous_candidate_types_depend_on_candidate_type_lesson():
    rules = [
        _rule("R-ABILITY", "生成一项技能选择", candidateType="Ability"),
        _rule("R-RELIC", "生成一项遗物选择", candidateType="Relic"),
    ]

    enabled = _projection(rules)
    disabled = _projection(rules, lesson_registry=_registry_without("LESSON-CANDIDATE-TYPE-RESOLUTION"))

    assert enabled["publication"]["mechanicFlows"][0]["candidateTypes"] == ["Ability", "Relic"]
    assert disabled["publication"]["mechanicFlows"][0]["candidateTypes"] == []


def test_runtime_policy_files_reference_system_lessons():
    recovery = json.loads((ROOT / "data/planner_knowledge/approved-narrative-recovery-policies-v1.json").read_text(encoding="utf-8"))
    reconstruction = json.loads((ROOT / "data/planner_knowledge/mechanic-reconstruction-policies-v1.json").read_text(encoding="utf-8"))

    assert recovery["intentCorrections"][0]["lessonRefs"] == ["LESSON-RULE-INTENT-RESPONSIBILITY"]
    assert reconstruction["policyBindings"]["candidateTypeResolution"]["lessonRefs"] == ["LESSON-CANDIDATE-TYPE-RESOLUTION"]


def test_lifecycle_gap_and_canonical_owner_depend_on_their_lessons():
    base = _rule("R-WIN", "核心失效后挑战成功", intent="VictoryCondition", schemaSlot="victory_condition", subject="关卡")
    chapters = [
        {"chapterId": "CHOICE", "title": "来源章节", "entityScope": ["关卡"]},
        {"chapterId": "RESULT", "title": "结果", "entityScope": ["关卡"], "schemaResponsibilities": ["victory_condition"]},
    ]
    entity = [{"entityId": "E-UNIT", "entityType": "combat_entity", "existenceStatus": "confirmed", "name": "单位"}]
    enabled = build_rule_intelligence_projection(
        approved_data={"rules": [base], "facts": [], "parameters": [], "gaps": []},
        chapters=chapters, entity_declarations=entity,
    )
    no_lifecycle = build_rule_intelligence_projection(
        approved_data={"rules": [base], "facts": [], "parameters": [], "gaps": []},
        chapters=chapters, entity_declarations=entity,
        lesson_registry=_registry_without("LESSON-EVIDENCE-BOUNDED-LIFECYCLE"),
    )
    no_owner = build_rule_intelligence_projection(
        approved_data={"rules": [base], "facts": [], "parameters": [], "gaps": []},
        chapters=chapters, entity_declarations=entity,
        lesson_registry=_registry_without("LESSON-CANONICAL-OWNERSHIP-GLOBAL-RECOVERY"),
    )

    assert any(gap.get("subjectEntityId") == "E-UNIT" for gap in enabled["gaps"])
    assert not any(gap.get("subjectEntityId") == "E-UNIT" for gap in no_lifecycle["gaps"])
    assert enabled["rules"][0]["canonicalOwner"] == "RESULT"
    assert no_owner["rules"][0]["canonicalOwner"] == "CHOICE"
