import json

from backend.gameplay_quality_reference import find_quality_reference


def test_reference_uses_only_approved_high_quality_structure_and_never_copies_game_facts(tmp_path):
    jobs = tmp_path / "jobs"
    job_dir = jobs / "golden"
    job_dir.mkdir(parents=True)
    model = {
        "systems": [{"name": "成长系统"}],
        "directory": {"understanding": {"summary": "玩家通过选择强化改变本局能力。"}, "entries": []},
        "chapters": [{
            "id": "GCH-001", "scope": "强化选择", "systemName": "成长系统", "subsystemName": "局内成长",
            "status": "approved", "confirmation": {"confirmed": True}, "sourceFrameIds": ["F0001"],
            "mechanism": {"type": "custom", "rules": "秘密武器会改变攻击方式。"},
            "plannerSummary": "秘密武器会改变攻击方式。",
            "plannerSections": {
                "summary": "秘密武器会改变攻击方式。", "normalFlow": ["玩家选择强化后提交结果。", "系统应用强化效果并继续战斗。"],
                "keyRules": ["规则三"], "specialCases": ["边界一"], "acceptanceExamples": ["验收一"],
            },
            "acceptanceCases": [{"scene": "正常", "action": "选择", "expected": "生效"}],
            "dependencies": [],
        }],
    }
    (job_dir / "job.json").write_text(json.dumps({"gameplayReviewModel": model}, ensure_ascii=False), encoding="utf-8")

    reference = find_quality_reference(jobs, {"scope": "奖励选择", "systemName": "成长系统", "subsystemName": "局内成长"})

    assert reference["normalFlowItems"] == 2
    assert reference["keyRuleItems"] == 1
    assert reference["acceptanceItems"] == 1
    assert "秘密武器" not in json.dumps(reference, ensure_ascii=False)
