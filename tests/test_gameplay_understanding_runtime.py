from __future__ import annotations

from backend.gameplay_understanding_runtime import _first_class_model, _runtime_prompt, _validate_response


def test_runtime_prompt_uses_gameplay_understanding_v1_2_without_fixed_cap() -> None:
    prompt = _runtime_prompt(["F0001", "F0002"])
    assert "# Gameplay Understanding Skill v1.2" in prompt
    assert "GameplayUnderstandingModel" in prompt
    assert "System -> Subsystem -> Mechanism -> RuleGroup" in prompt
    assert "there is no maximum mechanism count per subsystem" in prompt
    assert "Do not cap mechanisms per subsystem" in prompt
    assert "每个子系统最多包含 8 个机制" not in prompt
    assert "mechanismType must be exactly one of" not in prompt


def test_validator_accepts_more_than_eight_real_mechanisms_without_schema_cap() -> None:
    mechanisms = [
        {
            "name": f"机制{i}",
            "reason": f"行为责任{i}",
            "sourceFrameIds": ["F0001"],
            "ruleGroups": [{"name": f"规则组{i}", "summary": f"责任{i}"}],
        }
        for i in range(1, 11)
    ]
    value = {
        "summary": "复杂模拟玩法",
        "coreLoop": ["观察", "操作", "反馈"],
        "systems": [{
            "name": "模拟系统",
            "reason": "同一模拟域",
            "subsystems": [{"name": "运行子系统", "mechanisms": mechanisms}],
        }],
    }
    validated = _validate_response(value, {"F0001"})
    assert len(validated["systems"][0]["subsystems"][0]["mechanisms"]) == 10


def test_first_class_model_preserves_dynamic_rule_groups() -> None:
    structure = {
        "summary": "经营循环",
        "coreLoop": ["采购", "生产", "出售"],
        "systems": [{
            "name": "经营",
            "reason": "资源转换",
            "subsystems": [{
                "name": "生产",
                "mechanisms": [{
                    "name": "批次生产",
                    "reason": "投入资源后经过周期产出",
                    "sourceFrameIds": ["F0001"],
                    "ruleGroups": [
                        {"name": "投入", "summary": "生产所需资源"},
                        {"name": "周期", "summary": "生产时序"},
                        {"name": "产出", "summary": "结算结果"},
                    ],
                }],
            }],
        }],
    }
    model = _first_class_model(structure, source_revision=2)
    assert model["version"] == "gameplay_understanding_model_v1_2"
    assert model["skillContract"] == "gameplay-understanding-v1.2"
    assert model["mechanisms"][0]["name"] == "批次生产"
    assert len(model["ruleGroups"]) == 3
    assert model["digest"]
