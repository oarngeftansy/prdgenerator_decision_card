from __future__ import annotations

import json
from pathlib import Path

from backend.planner_quality_judge import evaluate_execution_readiness

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "gameplay_quality_golden.json"
MECHANIC_GOLD = ROOT / "tests" / "fixtures" / "full_mechanic_reconstruction_gold_v1.json"


def _closed_battle_publication() -> dict:
    return {
        "chapters": [{"chapterId": "GCH-001", "publicationEligibility": "eligible"}],
        "gaps": [],
        "rules": [{
            "ruleId": "R-1",
            "canonicalOwner": "GCH-001",
            "behavior": "单位选择有效目标并攻击；目标失效后重新选取目标，没有有效目标时保持待机。",
            "trigger": "进入可攻击状态",
            "conditions": ["存在有效目标"],
            "result": "目标生命值更新并触发目标有效性复核",
            "stateChange": "目标有效 -> 目标失效/存活",
            "lifecycle": "进入战斗时初始化，目标失效时重选，战斗结束时清理",
            "dependencies": ["目标有效性", "伤害结算"],
            "formula": "最终伤害由伤害结算规则计算",
            "persistence": "仅当前战斗",
            "reset": "战斗结束重置目标状态",
            "acceptanceCases": [
                "击败目标后继续推进",
                "没有有效目标时不产生无效攻击",
            ],
            "exception": "目标在攻击结算前失效时取消本次无效命中并重新选取目标",
        }],
    }


def _visual_only_publication() -> dict:
    return {
        "chapters": [{"chapterId": "GCH-001", "publicationEligibility": "eligible"}],
        "gaps": [{"gapId": "G-1", "chapterId": "GCH-001", "status": "open"}],
        "rules": [{
            "ruleId": "R-1",
            "canonicalOwner": "GCH-001",
            "behavior": "画面中出现一个按钮",
        }],
    }


def test_new_quality_judge_preserves_committed_golden_good_bad_polarity() -> None:
    cases = json.loads(GOLDEN.read_text(encoding="utf-8"))
    assert [case["expectedPassed"] for case in cases] == [True, False]

    good = evaluate_execution_readiness(_closed_battle_publication())
    bad = evaluate_execution_readiness(_visual_only_publication())

    assert good["ready"] is True
    assert good["overall"] >= 70
    assert bad["ready"] is False
    assert "unresolved_execution_gaps" in bad["criticalIssues"]
    assert good["overall"] > bad["overall"]


def test_new_skill_dimensions_cover_existing_full_mechanic_gold_categories() -> None:
    gold = json.loads(MECHANIC_GOLD.read_text(encoding="utf-8"))
    responsibilities = {
        item
        for values in gold["expectedCoreResponsibilities"].values()
        for item in values
    }
    # Existing gold requires candidate eligibility/generation, lifecycle/reset,
    # targeting/attack/damage, contact/death/cleanup and parameter contracts.
    assert "choice.eligibility" in responsibilities
    assert "choice.reset" in responsibilities
    assert "weapon.target_validity" in responsibilities
    assert "weapon.damage_handoff" in responsibilities
    assert "monster.contact_evaluation" in responsibilities
    assert "monster.death_interrupt" in responsibilities
    assert "monster.parameter_contract" in responsibilities
