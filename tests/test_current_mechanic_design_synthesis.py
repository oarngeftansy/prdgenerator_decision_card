import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/mechanic-design-synthesis-2026-08-18"
FORMAL = ROOT / "artifacts/mechanic-requirement-closure-publication-2026-08-18/human-planning-preview.md"


def test_current_benchmark_has_seven_complete_mechanic_review_units():
    payload = json.loads((ART / "mechanic-design-syntheses.json").read_text(encoding="utf-8"))
    assert payload["metrics"]["mechanicCount"] == 7
    assert payload["metrics"]["atomicProposalCount"] == 18
    assert payload["metrics"]["uniquePrimaryOwnerProposalCount"] == 18
    assert payload["metrics"]["confirmedRuleMutationCount"] == 0
    assert payload["metrics"]["requirementStatusMutationCount"] == 0
    assert payload["metrics"]["formalPublicationMutationCount"] == 0
    assert len(payload["syntheses"]) == 7
    all_ids = [pid for item in payload["syntheses"] for pid in item["atomicProposalIds"]]
    assert len(all_ids) == len(set(all_ids)) == 18
    assert all(item["publicationEligible"] is False for item in payload["syntheses"])
    assert all("score" in item["executionCompleteness"] for item in payload["syntheses"])
    assert all(item["confirmedRules"] for item in payload["syntheses"])


def test_draw_reuses_weapon_result_processing_instead_of_redefining_it():
    payload = json.loads((ART / "mechanic-design-syntheses.json").read_text(encoding="utf-8"))
    draw = next(item for item in payload["syntheses"] if item["mechanicDesignId"] == "MDES-DRAW")
    assert any(ref["relation"] == "uses_weapon_result_processing" for ref in draw["ruleReferences"])
    draw_text = " ".join(item["text"] for item in draw["recommendedDesign"])
    assert "同武器转为强化" not in draw_text
    assert "新武器进入空栏" not in draw_text


def test_preview_uses_natural_mechanic_titles_and_hides_atomic_ids_by_default():
    markdown = (ART / "mechanic-level-ai-design-review-preview.md").read_text(encoding="utf-8")
    for forbidden in ("attack.entry", "attack.exit", "statistics.end", "proposalId",
                      "requirementId", "assumptionLevel"):
        assert forbidden not in markdown
    assert "## 普通怪物行为" in markdown
    assert "## 伤害统计" in markdown
    assert not re.search(r"^#{1,6}\s+[a-z][a-z0-9_]+\.[a-z0-9_.]+$", markdown, re.M)


def test_formal_publication_is_not_replaced_by_review_preview():
    review = (ART / "mechanic-level-ai-design-review-preview.md").read_text(encoding="utf-8")
    payload = json.loads((ART / "mechanic-design-syntheses.json").read_text(encoding="utf-8"))
    assert payload["metrics"]["formalPublicationMutationCount"] == 0
    assert "内部主策审核产物" in review
    if FORMAL.exists():
        formal = FORMAL.read_text(encoding="utf-8")
        assert formal != review
        assert "Accept Mechanic" not in formal


def test_review_and_planning_hierarchies_are_decoupled_with_natural_content_bearing_nodes():
    review = json.loads((ART / "review-hierarchy.json").read_text(encoding="utf-8"))
    planning = json.loads((ART / "planning-hierarchy.json").read_text(encoding="utf-8"))
    preview = (ART / "planning-hierarchy-preview.md").read_text(encoding="utf-8")
    assert len(review["reviewUnits"]) == 7
    assert planning["metrics"]["assignmentRate"] == 100.0
    assert planning["metrics"]["compositePlanningTitleCount"] == 0
    assert planning["metrics"]["duplicatePrimaryPlanningNodeCount"] == 0
    assert planning["metrics"]["gatePassed"] is True
    assert "武器获取、栏位与攻击" in str(review)
    assert "武器获取、栏位与攻击" not in preview
    assert "Boss 与关卡阶段" not in preview
    assert "胜负与结算" not in preview
    assert "# 核心战斗" in preview and "## 武器" in preview
    assert "### 武器栏" in preview and "### 攻击" in preview
    assert "# 关卡结束" in preview and "## 战斗统计" in preview and "## 结算" in preview
    assert "怪物进入战区后以载具为移动目标" in preview
    assert all(node["designItemSummaries"] or node["sourceRuleIds"]
               for node in planning["planningNodes"] if node["nodeRole"] == "mechanic_responsibility")


def test_planning_audit_keeps_lineage_and_owner_findings_without_source_mutation():
    planning = json.loads((ART / "planning-hierarchy.json").read_text(encoding="utf-8"))
    payload = json.loads((ART / "mechanic-design-syntheses.json").read_text(encoding="utf-8"))
    assert planning["metrics"]["ownerStructureFindingCount"] >= 1
    assert all(finding["ownerChanged"] is False for finding in planning["ownerStructureFindings"])
    assert all(item.get("planningNodeId") and item.get("planningOwnerPath")
               for synthesis in payload["syntheses"] for item in synthesis["recommendedDesign"])
    assert payload["metrics"]["confirmedRuleMutationCount"] == 0
    assert payload["metrics"]["requirementStatusMutationCount"] == 0
    assert payload["metrics"]["formalPublicationMutationCount"] == 0
