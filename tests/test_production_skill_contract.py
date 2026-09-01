from __future__ import annotations

from backend.master_planner import _prompt
from backend.planning_skill_contract import load_production_skill, production_skill_manifest


def test_only_v2_planning_skills_are_in_production_manifest() -> None:
    manifest = production_skill_manifest()
    assert manifest == {
        "gameplay_reconstruction": "skills/gameplay-reconstruction-v2/SKILL.md",
        "execution_planning": "skills/execution-planning-v2/SKILL.md",
        "quality_judge": "skills/planner-quality-judge-v2/SKILL.md",
    }
    assert all("planning-quality-auditor" not in path for path in manifest.values())
    assert all("planning-sample-calibrator" not in path for path in manifest.values())


def test_v2_skills_encode_non_blocking_inference_and_execution_closure() -> None:
    reconstruction = load_production_skill("gameplay_reconstruction")
    execution = load_production_skill("execution_planning")
    judge = load_production_skill("quality_judge")

    assert "Missing evidence does not prohibit mechanism reconstruction" in reconstruction
    assert "Evidence insufficiency is never a planning stop condition" in execution
    assert "inferred" in execution and "proposed" in execution
    assert "Do not block merely because a rule is `inferred` or `proposed`" in judge
    assert "Golden Sample" in judge


def test_runtime_master_planner_prompt_matches_v2_execution_authority() -> None:
    prompt = _prompt(
        {"chapters": [], "existingRules": []},
        [{
            "gapId": "G-1",
            "chapterId": "CHOICE",
            "intent": "CandidateSelection",
            "schemaSlot": "candidate_pool",
            "gapKind": "missing_rule",
            "question": "候选技能如何抽取？",
        }],
    )
    assert "evidence 不足不是停止条件" in prompt
    assert "publicationState=inferred" in prompt
    assert "publicationState=proposed" in prompt
    assert "候选池、资格过滤、抽取数量、重复规则" in prompt
    assert "不得出现“待确认" in prompt
