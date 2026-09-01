import json

from scripts.generate_phase55_game_rule_groups import generate_phase55


def test_phase55_real_six_chapter_reconstruction_is_read_only_and_scope_safe(tmp_path):
    summary = generate_phase55(tmp_path)
    assert summary["granularityGate"] == "pass"
    assert summary["sourceFilesUnchanged"] is True
    assert summary["modifiedApprovedRuleCount"] == summary["modifiedApprovedGapCount"] == 0
    assert summary["finalDocumentGenerated"] is False
    assert summary["parameterResolverInvoked"] is False
    groups = json.loads((tmp_path / "game-rule-groups.json").read_text(encoding="utf-8"))
    assert len({group["mechanicId"] for group in groups}) == 6
    assert all(group["title"] not in {"breakpoint", "node", "edge", "contract", "pipeline"} for group in groups)
    assert "解锁规则" not in {group["title"] for group in groups}
