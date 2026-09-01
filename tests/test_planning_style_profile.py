from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROFILE = ROOT / "artifacts/planning-style-distillation-2026-08-17/planning_style_profile.yaml"
SPEC = ROOT / "artifacts/planning-style-distillation-2026-08-17/PlanningStyleSpec.md"
EVIDENCE = ROOT / "artifacts/planning-style-distillation-2026-08-17/planning_style_evidence.json"


def test_planning_style_profile_is_machine_readable_and_content_authority_free():
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    assert profile["schema_version"] == "planning-style-profile-v2"
    assert profile["content_authority"] == "none"
    assert profile["source_summary"] == {
        "document_count": 2, "complete_document_count": 1, "partial_document_count": 1,
        "source_ids": ["DOC-A", "DOC-B"], "cross_document_claims_require_both_sources": True,
    }
    assert len(profile["renderer_allowlist"]) == 6
    assert "linter_only" in profile["runtime_contract"]["readable_only_by_style_linter"]


def test_style_spec_has_renderer_boundary_examples_and_linter_without_phase4_code():
    text = SPEC.read_text(encoding="utf-8")
    assert "七组表达对比" in text
    assert text.count("| 结构化 Rule | 普通 AI 写法 | Spec 约束后的策划写法 |") == 1
    assert text.count("| subject=") >= 7
    assert "禁止进入生成链路" in text
    assert "Renderer Allowlist" in text


def test_every_style_feature_has_real_evidence_counterexample_and_permission():
    import json

    evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    assert len(evidence["sources"]) == 2
    assert evidence["statistics"]["title_length"]["count"] == 99
    assert evidence["statistics"]["rule_length"]["count"] == 470
    assert evidence["statistics"]["cross_document_execution_verbs"] == ["重置", "刷新"]
    for feature in evidence["features"]:
        assert feature["source_evidence"]
        assert isinstance(feature["occurrence_count"], int)
        assert feature["document_count"] in {1, 2}
        assert feature["counterexample"]
        assert feature["confidence"] and feature["confidence"] != "pending"
        assert feature["permission"] in {"renderer_allowed", "linter_only", "forbidden"}
        if feature["permission"] == "renderer_allowed":
            assert feature["observation_type"] == "cross_document_pattern"
            assert feature["document_count"] == 2
            assert feature["deterministic"] and feature["content_free"] and not feature["can_close_gap"]


def test_distilled_outputs_contain_no_pending_or_placeholder_claims():
    combined = "\n".join(path.read_text(encoding="utf-8") for path in (SPEC, PROFILE, EVIDENCE)).lower()
    assert "confidence: pending" not in combined
    assert "sample_count: 0" not in combined
    assert "placeholder" not in combined
