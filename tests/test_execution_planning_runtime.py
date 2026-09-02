from __future__ import annotations

from backend.execution_planning_runtime import _runtime_prompt


def test_execution_runtime_prompt_contains_checked_in_skill_contract() -> None:
    prompt = _runtime_prompt(
        {
            "systems": [{"name": "建造"}],
            "mechanisms": [{"mechanicId": "PLACE", "name": "放置"}],
            "existingRules": [],
        },
        [{
            "gapId": "G-PLACE",
            "chapterId": "BUILD-PLACE",
            "mechanicId": "PLACE",
            "intent": "PlacementBoundary",
            "schemaSlot": "placement_boundary",
            "gapKind": "missing_rule",
            "question": "放置位置无效时如何处理？",
        }],
    )
    assert "# Execution Planning v2" in prompt
    assert "Evidence insufficiency is never a planning stop condition" in prompt
    assert "System -> Subsystem -> Mechanism -> RuleGroup" in prompt
    assert "Do not copy mechanism nouns or structures from examples/Golden Samples" in prompt
    assert '"gapId": "G-PLACE"' in prompt
    assert "待确认、可能、或许" in prompt
