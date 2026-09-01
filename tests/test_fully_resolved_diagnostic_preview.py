import json
from pathlib import Path

from backend.fully_resolved_diagnostic import apply_temporary_review_overrides


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.5.5-fully-resolved-diagnostic-2026-08-18"
def test_temporary_override_replaces_pending_without_changing_source_preview():
    source = "## 武器\n\n### 攻击\n\n- 攻击范围：待确认。\n"
    overrides = [{"decisionId": "D1", "matchLines": ["- 攻击范围：待确认。"],
                  "replacementLines": ["- 每种武器独立配置攻击范围。", "- 仅攻击范围内敌人。"]}]
    result = apply_temporary_review_overrides(source, overrides)
    assert "待确认" not in result
    assert "每种武器独立配置攻击范围" in result
    assert source.endswith("待确认。\n")


def test_diagnostic_artifact_uses_all_11_overrides_but_keeps_reviews_unreviewed():
    audit = json.loads((ARTIFACT_DIR / "diagnostic-override-audit.json").read_text(encoding="utf-8"))
    preview = (ARTIFACT_DIR / "fully-resolved-diagnostic-preview.md").read_text(encoding="utf-8")
    assert audit["overrideCount"] == 11
    assert audit["sourceUnreviewedBefore"] == 11
    assert audit["sourceUnreviewedAfter"] == 11
    assert audit["sourceClosureHashUnchanged"] is True
    assert all(item["temporary"] and not item["writeBackAllowed"] for item in audit["overrides"])
    assert "待确认" not in preview
    assert "武器伤害占比 =" not in preview


def test_diagnostic_preview_contains_given_rules_without_unapproved_failure_rule():
    preview = (ARTIFACT_DIR / "fully-resolved-diagnostic-preview.md").read_text(encoding="utf-8")
    assert "获得新武器后优先填入空武器栏" in preview
    assert "每日最多通过观看广告刷新候选1次" in preview
    assert "击败怪物后获得局内成长进度" in preview
    assert "完成当前关卡的前置战斗阶段后进入首领战" in preview
    assert "击败首领后本关挑战成功，并进入结算" in preview
    assert "载具生命值归零时关卡失败" not in preview


def test_diagnostic_gap_report_uses_only_six_allowed_categories():
    report = json.loads((ARTIFACT_DIR / "diagnostic-gve16-gap-audit.json").read_text(encoding="utf-8"))
    metrics = report["diagnosticMetrics"]
    assert set(report["gapCategories"]) == {"A", "B", "C", "D", "E", "F"}
    assert metrics["effectiveExecutionRuleCount"] == 40
    assert metrics["ruleGroups"] == 16
    assert metrics["formulae"] == 0
    assert metrics["tables"] == 1
    assert metrics["orderedProcesses"] == 1
    assert report["gapCategories"]["D"]["count"] == 1
