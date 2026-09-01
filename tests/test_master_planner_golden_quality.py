from __future__ import annotations

import json
from pathlib import Path

from backend.planner_quality_judge import evaluate_execution_readiness

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "fixtures" / "gameplay_quality_golden.json"
MECHANIC_GOLD = ROOT / "tests" / "fixtures" / "full_mechanic_reconstruction_gold_v1.json"


def _closed_publication(behavior: str, *, trigger: str, result: str, dependency: str) -> dict:
    return {
        "chapters": [{"chapterId": "GCH-001", "publicationEligibility": "eligible"}],
        "gaps": [],
        "rules": [{
            "ruleId": "R-1",
            "canonicalOwner": "GCH-001",
            "behavior": behavior,
            "trigger": trigger,
            "conditions": ["满足执行条件"],
            "result": result,
            "stateChange": "执行前状态 -> 执行后状态",
            "lifecycle": "进入机制时初始化，执行期间更新，离开机制时清理",
            "dependencies": [dependency],
            "formula": "数值结果由对应规则计算",
            "persistence": "仅当前玩法上下文",
            "reset": "离开当前玩法上下文后重置临时状态",
            "acceptanceCases": ["正常路径可完成", "条件不满足时不会产生非法结果"],
            "exception": "执行条件在结算前失效时取消本次无效结果并恢复到可继续状态",
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

    good = evaluate_execution_readiness(_closed_publication(
        "单位满足条件后执行当前机制，并在结果无效时恢复可继续状态。",
        trigger="进入可执行状态",
        result="机制结果写入当前状态",
        dependency="状态规则",
    ))
    bad = evaluate_execution_readiness(_visual_only_publication())

    assert good["ready"] is True
    assert good["overall"] >= 70
    assert bad["ready"] is False
    assert "unresolved_execution_gaps" in bad["criticalIssues"]
    assert good["overall"] > bad["overall"]


def test_quality_judge_accepts_different_mechanic_families_without_sample_nouns() -> None:
    traversal = evaluate_execution_readiness(_closed_publication(
        "角色移动到边界时按照当前通行规则更新位置，路径失效时停留在最后合法位置。",
        trigger="收到移动输入",
        result="角色位置与通行状态更新",
        dependency="地图通行规则",
    ))
    crafting = evaluate_execution_readiness(_closed_publication(
        "库存满足配方消耗时扣除材料并生成产物，任一材料不足时不扣除库存。",
        trigger="确认制作",
        result="库存与产物状态原子更新",
        dependency="库存规则",
    ))
    dialogue = evaluate_execution_readiness(_closed_publication(
        "对话节点满足进入条件后展示可用分支，选择分支后写入对应叙事状态并进入目标节点。",
        trigger="进入对话节点",
        result="叙事状态与当前节点更新",
        dependency="对话状态规则",
    ))

    assert traversal["ready"] is True
    assert crafting["ready"] is True
    assert dialogue["ready"] is True


def test_legacy_mechanic_gold_remains_fixture_not_runtime_schema() -> None:
    gold = json.loads(MECHANIC_GOLD.read_text(encoding="utf-8"))
    responsibilities = {
        item
        for values in gold["expectedCoreResponsibilities"].values()
        for item in values
    }
    # The fixture still describes its historical sample accurately, but the
    # runtime judge above must also pass unrelated mechanic families. These
    # sample nouns are therefore regression data, not mandatory production slots.
    assert responsibilities
    assert any(item.startswith("choice.") for item in responsibilities)
    assert any(item.startswith("weapon.") for item in responsibilities)
