from __future__ import annotations

from backend.master_planner import _compact_context, _prompt
from backend.planning_skill_contract import load_production_skill, production_skill_manifest


def test_only_canonical_planning_skills_are_in_production_manifest() -> None:
    manifest = production_skill_manifest()
    assert manifest == {
        "gameplay_understanding": "skills/gameplay-understanding-v1.2/SKILL.md",
        "execution_planning": "skills/execution-planning-v2/SKILL.md",
        "interaction_planning": "skills/interaction-planning-v2/SKILL.md",
        "quality_judge": "skills/planner-quality-judge-v2/SKILL.md",
    }
    assert all("planning-quality-auditor" not in path for path in manifest.values())
    assert all("planning-sample-calibrator" not in path for path in manifest.values())
    assert all("gameplay-reconstruction-v2" not in path for path in manifest.values())


def test_canonical_skills_encode_non_blocking_inference_and_execution_closure() -> None:
    understanding = load_production_skill("gameplay_understanding")
    execution = load_production_skill("execution_planning")
    interaction = load_production_skill("interaction_planning")
    judge = load_production_skill("quality_judge")

    assert "GameplayUnderstandingModel" in understanding
    assert "System -> Subsystem -> Mechanism -> RuleGroup" in understanding
    assert "Evidence insufficiency does not prevent" in understanding
    assert "Evidence insufficiency is never a planning stop condition" in execution
    assert "inferred" in execution and "proposed" in execution
    assert "must never impose its nouns" in interaction
    assert "system_context" in interaction and "gameplay_context" in interaction
    assert "Do not block merely because a rule is `inferred` or `proposed`" in judge
    assert "Golden Sample" in judge


def test_runtime_master_planner_prompt_is_mechanic_agnostic() -> None:
    prompt = _prompt(
        {"chapters": [], "existingRules": []},
        [{
            "gapId": "G-TRAVEL",
            "chapterId": "TRAVEL",
            "intent": "TraversalResolution",
            "schemaSlot": "movement_resolution",
            "gapKind": "missing_rule",
            "question": "角色越过移动边界后如何处理？",
        }],
    )
    assert "evidence 不足不是停止条件" in prompt
    assert "publicationState=inferred" in prompt
    assert "publicationState=proposed" in prompt
    assert "不套用任何固定玩法模板" in prompt
    assert "Golden Sample 只用于判断执行深度" in prompt
    assert "禁止注入“技能/武器/怪物/候选池”等无关概念" in prompt
    assert "必须明确候选池、资格过滤" not in prompt
    assert "不得出现“待确认" in prompt


def test_compact_context_preserves_dynamic_mechanic_graph() -> None:
    context = _compact_context(
        {
            "publication": {
                "systemGraph": {"systems": [{"id": "ECON"}]},
                "mechanisms": [{"mechanicId": "CRAFT"}],
                "ruleGroups": [{"ruleGroupId": "CRAFT-COST"}],
                "chapters": [{
                    "chapterId": "ECON-CRAFT",
                    "system": "经济",
                    "subsystem": "制作",
                    "mechanism": "配方制作",
                    "title": "制作流程",
                }],
                "rules": [{
                    "ruleId": "R-COST",
                    "canonicalOwner": "ECON-CRAFT",
                    "ownerMechanicId": "CRAFT",
                    "behavior": "满足配方消耗后生成产物",
                    "dependencies": ["库存"],
                }],
            }
        },
        {"CoreLoop": ["收集", "制作", "使用"]},
    )
    assert context["systemGraph"]["systems"][0]["id"] == "ECON"
    assert context["mechanisms"][0]["mechanicId"] == "CRAFT"
    assert context["ruleGroups"][0]["ruleGroupId"] == "CRAFT-COST"
    assert context["chapters"][0]["mechanism"] == "配方制作"
    assert context["existingRules"][0]["ownerMechanicId"] == "CRAFT"
