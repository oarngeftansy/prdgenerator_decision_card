import json
from pathlib import Path

from backend.execution_rule_closure import (
    audit_execution_rule_closure,
    render_execution_closure_preview,
)


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.3.5-execution-closure-2026-08-18"


def _contract(mechanic="怪物攻击"):
    return {
        "ruleSemanticId": "RSC-MONSTER", "mechanic": mechanic, "ownerChapter": "怪物",
        "confirmedCoreRule": [{"ruleId": "RULE-CONTACT", "statement": "怪物接触载具后造成伤害。"}],
        "requiredRuleDimensions": [{"dimensionId": "contact_damage", "status": "observed",
                                     "displayText": "怪物接触载具后造成伤害。"}],
    }


def test_template_dimension_without_project_basis_is_not_applicable():
    specs = [{"ruleSemanticId": "RSC-MONSTER", "dimensions": [{
        "dimensionId": "attack_interval", "disposition": "not_applicable",
        "reason": "现有素材未证明怪物存在独立攻击状态或周期攻击。",
        "basis": [],
    }]}]
    report = audit_execution_rule_closure([_contract()], specs)
    mechanic = report["mechanics"][0]
    assert mechanic["reviewRequiredGaps"] == []
    assert mechanic["notApplicableDimensions"][0]["dimensionId"] == "attack_interval"
    assert mechanic["closureStatus"] == "closed"


def test_evidence_resolvable_dimension_requires_concrete_evidence_and_stays_candidate():
    specs = [{"ruleSemanticId": "RSC-MONSTER", "dimensions": [{
        "dimensionId": "damage_share_formula", "disposition": "evidence_resolvable",
        "question": "武器伤害占比如何计算？",
        "candidateRule": "武器伤害占比 = 该武器本局伤害 ÷ 本局总伤害。",
        "basis": [{"evidenceId": "F0015", "reason": "结算页同时显示本局总伤害，且四个武器伤害占比合计100%。"}],
    }]}]
    report = audit_execution_rule_closure([_contract("伤害统计")], specs)
    gap = report["mechanics"][0]["evidenceResolvableGaps"][0]
    assert gap["candidateOnly"] is True
    assert gap["basis"][0]["evidenceId"] == "F0015"
    assert report["approvedRuleWrites"] == 0


def test_review_required_needs_confirmed_mechanic_and_actionable_rule_dimension():
    specs = [{"ruleSemanticId": "RSC-MONSTER", "dimensions": [{
        "dimensionId": "contact_damage_mode", "disposition": "review_required",
        "question": "接触伤害方式：待确认。", "reviewStage": "P4",
        "basis": [], "mechanicExistenceBasis": [],
    }]}]
    report = audit_execution_rule_closure([_contract()], specs)
    assert report["mechanics"][0]["reviewRequiredGaps"] == []
    assert report["rejectedDimensions"][0]["reason"] == "review_gap_without_confirmed_mechanic_basis"


def test_preview_adds_only_evidence_candidates_and_review_pending_without_internal_labels():
    native = {"chapters": [{"title": "结算", "sections": [{"title": "伤害统计", "items": [{
        "text": "统计本局总伤害。", "supportingRuleIds": ["RULE"],
        "sourceDimensionIds": ["total_damage"]}]}]}]}
    report = {"mechanics": [{"ownerChapter": "结算", "ruleSemanticId": "RSC-STATS",
        "evidenceResolvableGaps": [{"candidateRule": "武器伤害占比 = 该武器本局伤害 ÷ 本局总伤害。",
                                    "dimensionId": "damage_share_formula", "basis": [{"evidenceId": "F0015"}]}],
        "reviewRequiredGaps": [{"displayText": "持续伤害归属：待确认。", "dimensionId": "dot_attribution",
                                "reviewStage": "P4"}]}]}
    preview = render_execution_closure_preview(native, report)
    assert "武器伤害占比 = 该武器本局伤害 ÷ 本局总伤害。" in preview
    assert "持续伤害归属：待确认。" in preview
    assert "evidence_resolvable" not in preview
    assert "review_required" not in preview


def test_phase635_artifact_has_no_template_pending_or_approved_write():
    quality = json.loads((ARTIFACT_DIR / "phase635-quality-gate.json").read_text(encoding="utf-8"))
    report = json.loads((ARTIFACT_DIR / "execution-closure-report.json").read_text(encoding="utf-8"))
    preview = (ARTIFACT_DIR / "human-planning-preview.md").read_text(encoding="utf-8")
    assert quality["templateOnlyPendingCount"] == 0
    assert quality["unsupportedCandidateRuleCount"] == 0
    assert quality["approvedRuleWrites"] == 0
    assert quality["pass"] is True
    assert all(mechanic["closureStatus"] in {"closed", "partially_closed", "open"}
               for mechanic in report["mechanics"])
    assert "权重：待确认" not in preview
    assert "不放回" not in preview
    assert "满级过滤" not in preview

