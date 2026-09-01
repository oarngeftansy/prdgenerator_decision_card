import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "mechanic-requirement-ai-proposals-2026-08-18"
FINAL = ROOT / "artifacts" / "mechanic-requirement-closure-publication-2026-08-18" / "human-planning-preview.md"


def test_current_unresolved_core_requirements_have_review_only_proposals():
    payload = json.loads((ART / "ai-proposed-rules.json").read_text(encoding="utf-8"))
    expected = {
        "unresolvedCoreRequirementCount": 18,
        "proposalCount": 18,
        "proposalCoverageRate": 100.0,
        "validRuleCount": 0,
        "publicationEligibleCount": 0,
        "confirmedRuleCount": 0,
        "questionOnlyCount": 0,
    }
    assert {key: payload["metrics"][key] for key in expected} == expected
    assert payload["metrics"]["proposalTypeCounts"] == {
        "conservative": 1, "design_inference": 15, "alternative_design": 2}
    assert payload["metrics"]["assumptionLevelCounts"] == {"low": 1, "medium": 17, "high": 0}
    assert payload["metrics"]["returnedToProbeOrPlaceholderCount"] == 0
    assert payload["metrics"]["unsupportedSpecificityProposalCount"] == 17
    assert payload["metrics"]["unsupportedSpecificityHitCount"] == 34
    assert payload["metrics"]["informationGainProposalCount"] == 18
    assert payload["metrics"]["informationGainItemCount"] == 31
    assert payload["metrics"]["informationGainGateFailureCount"] == 0
    assert payload["requirementStatusMutationCount"] == 0
    assert all(item["originRequirementId"] for item in payload["proposals"])
    assert all(item["proposalBases"] and item["uncertainties"] for item in payload["proposals"])
    assert all(item["informationGainCount"] >= 1 for item in payload["proposals"])
    assert all(gain["decision"].strip()
               for item in payload["proposals"] for gain in item["informationGain"])


def test_current_proposals_add_executable_information_instead_of_semantic_filler():
    payload = json.loads((ART / "ai-proposed-rules.json").read_text(encoding="utf-8"))
    rejected_phrases = {
        "战斗开始后开始统计，战斗结束后结束统计",
        "满足攻击条件后攻击",
        "满足升级条件后升级",
        "按规则计算伤害",
    }
    allowed_types = {
        "trigger_condition", "state_change", "object_relation", "data_source",
        "aggregation_calculation", "branch_handling", "lifecycle_result",
        "config_meaning", "exception_boundary",
    }
    for proposal in payload["proposals"]:
        assert proposal["proposalText"] not in rejected_phrases
        assert {item["type"] for item in proposal["informationGain"]} <= allowed_types
        assert proposal["informationGain"]


def test_ai_proposals_do_not_leak_into_formal_publication():
    payload = json.loads((ART / "ai-proposed-rules.json").read_text(encoding="utf-8"))
    approved = json.loads((ROOT / "artifacts/mechanic-design-synthesis-2026-08-18/approved-mechanic-rules.json").read_text(encoding="utf-8"))
    approved_proposal_ids = {
        proposal_id for rule in approved["rules"] for proposal_id in rule.get("sourceProposalIds", [])
    }
    markdown = FINAL.read_text(encoding="utf-8")
    assert all(
        item["proposalText"] not in markdown
        for item in payload["proposals"]
        if item["proposalId"] not in approved_proposal_ids
    )
