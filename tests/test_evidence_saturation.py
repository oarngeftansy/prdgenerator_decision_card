from backend.evidence_saturation import (
    build_evidence_coverage_matrix,
    evaluate_default_closure,
)
import json
from pathlib import Path


def _obs(key, status, *, extracted=False, evidence=("F0001",), text="观察结果"):
    return {
        "observationDimension": key,
        "mechanic": "测试机制",
        "observationQuestion": "能否观察到？",
        "observationStatus": status,
        "alreadyExtracted": extracted,
        "observedText": text,
        "evidenceRefs": [
            {"evidenceId": item, "sourcePath": f"C:/evidence/{item}.jpg"}
            for item in evidence
        ],
    }


def test_coverage_counts_only_observable_dimensions_and_exposes_new_candidates():
    report = build_evidence_coverage_matrix([
        _obs("known", "directly_observed", extracted=True),
        _obs("missed", "strongly_supported"),
        _obs("unclear", "ambiguous"),
        _obs("hidden", "not_observable"),
    ])
    assert report["metrics"] == {
        "observableDimensions": 2,
        "extractedObservableDimensions": 1,
        "missedObservableDimensions": 1,
        "ambiguousDimensions": 1,
        "unobservableDimensions": 1,
        "observableExtractionCoverage": 0.5,
    }
    assert [item["observationDimension"] for item in report["newFactCandidates"]] == ["missed"]


def test_ambiguous_observation_never_becomes_fact_or_rule_candidate():
    report = build_evidence_coverage_matrix([
        _obs("attack_frequency", "ambiguous", text="稀疏截图不能证明攻击频率")
    ])
    assert report["newFactCandidates"] == []
    assert report["newRuleCandidates"] == []


def test_candidate_requires_real_evidence_reference_and_source_path():
    broken = _obs("slot_count", "directly_observed")
    broken["evidenceRefs"][0]["sourcePath"] = ""
    try:
        build_evidence_coverage_matrix([broken])
    except ValueError as exc:
        assert "sourcePath" in str(exc)
    else:
        raise AssertionError("missing source path must be rejected")


def test_default_closure_suppresses_theoretical_variants_and_keeps_material_parameters():
    decisions = [
        {"decisionKey": "contact_damage_mode", "route": "P4"},
        {"decisionKey": "resume_combat", "route": "Suppress"},
        {"decisionKey": "attack_range", "route": "P6"},
        {"decisionKey": "weapon_slot_capacity", "route": "P6"},
        {"decisionKey": "displayed_data", "route": "Evidence Recheck"},
        {"decisionKey": "time_limit", "route": "P6"},
    ]
    evidence = {
        "weapon_slot_capacity": {"resolution": "strongly_supported", "value": 6},
        "displayed_data": {"resolution": "directly_observed"},
        "elapsed_time_not_limit": {"resolution": "strongly_supported"},
    }
    report = evaluate_default_closure(decisions, evidence)
    by_key = {item["decisionKey"]: item for item in report["items"]}
    assert by_key["contact_damage_mode"]["disposition"] == "suppress"
    assert by_key["resume_combat"]["disposition"] == "suppress"
    assert by_key["attack_range"]["disposition"] == "keep"
    assert by_key["weapon_slot_capacity"]["disposition"] == "evidence_candidate"
    assert by_key["displayed_data"]["disposition"] == "evidence_candidate"
    assert by_key["time_limit"]["disposition"] == "upstream_conflict"


def test_default_closure_does_not_activate_dependent_contact_interval():
    decisions = [{"decisionKey": "contact_damage_interval", "route": "P6",
                  "dependency": {"decisionId": "D", "whenOption": "continuous"}}]
    report = evaluate_default_closure(decisions, {})
    assert report["items"][0]["disposition"] == "suppress"
    assert report["items"][0]["gateReason"] == "parent_mechanic_not_evidenced"


def test_phase621_artifact_is_read_only_and_keeps_sparse_frame_limit_explicit():
    root = Path(__file__).resolve().parents[1]
    path = root / "artifacts" / "planning-content-phase6.2.1-evidence-saturation-2026-08-17"
    if not (path / "phase621-summary.json").exists():
        return
    summary = json.loads((path / "phase621-summary.json").read_text(encoding="utf-8"))
    assert summary["sourceKind"] == "ordered_screenshots"
    assert summary["continuousVideoAvailable"] is False
    assert summary["writeBack"] == {"approvedFacts": 0, "approvedRules": 0, "approvedGaps": 0}
    assert summary["evidenceSaturation"]["missedObservableDimensions"] > 0


def test_phase621_preview_suppresses_pseudo_pending_and_internal_claim_conflicts():
    root = Path(__file__).resolve().parents[1]
    path = root / "artifacts" / "planning-content-phase6.2.1-evidence-saturation-2026-08-17"
    if not (path / "evidence-saturated-preview.md").exists():
        return
    preview = (path / "evidence-saturated-preview.md").read_text(encoding="utf-8")
    assert "接触伤害方式：待确认" not in preview
    assert "选择完成后何时恢复战斗" not in preview
    assert "关卡时限：待确认" not in preview
    assert "虚拟摇杆或按键" not in preview
    assert "结算按武器展示伤害占比" in preview
