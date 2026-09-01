from pathlib import Path

from scripts.generate_phase43_semantic_samples import generate


def test_phase43_samples_report_role_refinement_and_clean_final_markdown(tmp_path: Path):
    result = generate(tmp_path)
    metrics = result["metrics"]
    assert list(result["chapters"]) == ["载具移动", "武器攻击", "三选一", "怪物攻击", "关卡流程", "结算"]
    assert metrics["semanticRoleCorrectionCount"] >= 4
    assert metrics["unresolvedDependencyCount"] == 1
    assert metrics["finalMarkdownInternalTypeLabelCount"] == 0
    assert metrics["unsupportedSemanticAdditionCount"] == 0
    assert metrics["ruleToRoleToBlockToFinalParagraphTraceabilityRate"] == 1.0
    audit = {item["ruleId"]: item for item in result["roleAudit"]}
    assert audit["RULE-477C6F80B92D"]["newRole"] == "input_constraint"
    assert audit["RULE-067BCCFED927"]["newRole"] == "target_selection"
    assert audit["RULE-4CC81AFEE84D"]["newRole"] == "processing"
    assert audit["RULE-03FA5C2E3EF6"]["resolution_status"] == "unresolved_dependency"
    markdown = (tmp_path / "six-chapter-final.md").read_text(encoding="utf-8")
    assert all(label not in markdown for label in ("mechanism", "presentation", "config_reference"))
    assert (tmp_path / "role-audit.md").exists()
