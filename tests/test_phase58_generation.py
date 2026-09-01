import json

from scripts.generate_phase58_native_rule_layouts import generate_phase58


def test_phase58_real_layout_preview_is_dynamic_native_and_read_only(tmp_path):
    summary = generate_phase58(tmp_path)
    assert summary["layoutQualityGate"] == "pass"
    assert summary["previewChapterCount"] == 4
    assert summary["sourceFilesUnchanged"] is True
    assert summary["modifiedApprovedRuleCount"] == summary["modifiedApprovedGapCount"] == 0
    assert summary["finalDocumentGenerated"] is False
    assert summary["parameterResolverInvoked"] is False
    plans = json.loads((tmp_path / "rule-layout-plans.json").read_text(encoding="utf-8"))
    attack = next(p for p in plans if p["ownerChapter"] == "V2CH-005" and p["sectionTitle"] == "攻击规则")
    assert attack["subsectionOrder"] == ["自动攻击", "攻击方式", "伤害结算"]
    random_titles = [p["sectionTitle"] for p in plans if p["ownerChapter"] == "V2CH-009"]
    assert random_titles == ["可获取词条", "触发与选择", "刷新", "选择结果"]
    monster = next(p for p in plans if p["ownerChapter"] == "V2CH-015")
    assert monster["layoutMode"] == "direct_bullets" and monster["subsectionOrder"] == []
    assert all(p["layoutPatternSource"].startswith("current_project_rule_chain > GVE16/") for p in plans)
