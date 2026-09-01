import json
from pathlib import Path

import pytest

from backend.closure_taxonomy_correction import (
    apply_closure_taxonomy_corrections,
    calculate_active_closure_metrics,
)


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.3.5a-closure-taxonomy-2026-08-18"


def _report():
    return {"mechanics": [{
        "ruleSemanticId": "RSC-RANDOM", "mechanic": "三选一", "ownerChapter": "三选一",
        "confirmedRuleDimensions": [{"dimensionId": "candidate_count", "status": "observed"},
                                    {"dimensionId": "selection_count", "status": "observed"}],
        "evidenceResolvableGaps": [{"dimensionId": "candidate_labels"}],
        "reviewRequiredGaps": [{"dimensionId": "candidate_eligibility"}],
        "notApplicableDimensions": [{"dimensionId": "random_extensions", "reason": "未观察到。"}],
    }]}


def test_missing_evidence_cannot_remain_not_applicable():
    corrected = apply_closure_taxonomy_corrections(_report(), [{
        "legacyDimensionId": "random_extensions", "dimensionId": "candidate_weight",
        "newStatus": "evidence_unknown", "evidence": ["三选一候选已确认，但随机方式不可见。"],
        "reason": "候选生成已存在；看不见权重不等于权重不适用。",
    }])
    mechanic = corrected["mechanics"][0]
    assert mechanic["evidenceUnknownDimensions"][0]["dimensionId"] == "candidate_weight"
    assert mechanic["notApplicableDimensions"] == []


def test_true_not_applicable_requires_a_strong_exclusion_basis():
    correction = {"legacyDimensionId": "random_extensions", "dimensionId": "candidate_weight",
                  "newStatus": "not_applicable", "evidence": [], "reason": "没有看到。"}
    with pytest.raises(ValueError, match="strong exclusion basis"):
        apply_closure_taxonomy_corrections(_report(), [correction])


def test_unknown_and_dormant_dimensions_do_not_pollute_active_denominator():
    report = _report()
    report["mechanics"][0]["notApplicableDimensions"].append(
        {"dimensionId": "optional_filter", "reason": "未观察到。"})
    corrected = apply_closure_taxonomy_corrections(report, [
        {"legacyDimensionId": "random_extensions", "dimensionId": "candidate_weight",
         "newStatus": "evidence_unknown", "evidence": ["候选生成机制存在"], "reason": "算法不可见。"},
        {"legacyDimensionId": "optional_filter", "dimensionId": "max_level_filter",
         "newStatus": "dormant_optional", "evidence": [], "reason": "未确认词条等级子机制。"},
    ])
    metrics = calculate_active_closure_metrics(corrected)
    assert metrics["activeExecutionDimensions"] == 4
    assert metrics["resolved"] == 2
    assert metrics["activeClosureRate"] == 50.0
    assert metrics["evidenceUnknown"] == 1
    assert metrics["dormantOptional"] == 1


def test_probe_is_excluded_and_review_promotion_enters_active_denominator_once():
    report = _report()
    report["mechanics"][0]["notApplicableDimensions"].extend([
        {"dimensionId": "kill_to_progress", "reason": "未观察到。"},
        {"dimensionId": "acquisition_to_slot_relation", "reason": "未观察到。"},
    ])
    corrected = apply_closure_taxonomy_corrections(report, [
        {"legacyDimensionId": "random_extensions", "dimensionId": "contact_damage_interval",
         "newStatus": "dormant_optional", "evidence": [], "reason": "持续接触子机制未激活。"},
        {"legacyDimensionId": "kill_to_progress", "dimensionId": "kill_to_progress",
         "newStatus": "evidence_probe", "evidence": ["战斗等级存在"],
         "reason": "仅作为成长来源的素材回查假设。"},
        {"legacyDimensionId": "acquisition_to_slot_relation", "dimensionId": "acquisition_to_slot_relation",
         "newStatus": "review_required", "evidence": ["武器获取和六个栏位均已确认"],
         "reason": "两个已激活系统之间缺少核心衔接规则。", "reviewStage": "P4",
         "displayText": "获得武器后如何处理武器栏位？", "controlType": "structured_custom"},
    ])
    metrics = calculate_active_closure_metrics(corrected)
    assert metrics["activeExecutionDimensions"] == 5
    assert metrics["reviewRequired"] == 2
    assert metrics["evidenceProbe"] == 1
    assert metrics["unknownMechanicDetailCount"] == 0
    review = corrected["mechanics"][0]["reviewRequiredGaps"][-1]
    assert review["displayText"] == "获得武器后如何处理武器栏位？"
    assert review["options"] == []
    assert review["controlType"] == "structured_custom"


def test_phase635a_artifact_reaudits_all_legacy_records_and_preserves_preview():
    quality = json.loads((ARTIFACT_DIR / "phase635a-quality-gate.json").read_text(encoding="utf-8"))
    metrics = json.loads((ARTIFACT_DIR / "closure-taxonomy-metrics.json").read_text(encoding="utf-8"))
    audit = json.loads((ARTIFACT_DIR / "not-applicable-correction-audit.json").read_text(encoding="utf-8"))
    assert audit["legacyNotApplicableRecordCount"] == 13
    assert audit["coveredLegacyRecordCount"] == 13
    assert metrics["activeExecutionDimensions"] == 38
    assert metrics["reviewRequired"] == 11
    assert metrics["evidenceUnknown"] == 4
    assert metrics["dormantOptional"] == 10
    assert metrics["evidenceProbe"] == 1
    assert metrics["activeClosureRate"] == 68.42
    assert metrics["trueNotApplicable"] < 13
    assert quality["previewHashUnchanged"] is True
    assert quality["approvedRuleWrites"] == 0
    assert quality["pass"] is True
