from __future__ import annotations

import json
from pathlib import Path

from backend.mechanic_requirement_discovery import evaluate_probe


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts/mechanic-requirement-discovery-2026-08-18"


def test_current_temporal_candidates_have_real_frames_and_requirement_lineage():
    registry = json.loads((ARTIFACT / "current-requirements.json").read_text(encoding="utf-8"))
    payload = json.loads((ARTIFACT / "current-temporal-evidence-candidates.json").read_text(encoding="utf-8"))
    requirement_ids = {item["requirementId"] for item in registry["requirements"]}
    for candidate in payload["candidates"]:
        assert candidate["requirementId"] in requirement_ids
        for field in ("beforeObservation", "transitionObservation", "afterObservation"):
            assert (ARTIFACT / candidate[field]["frameRef"]).is_file()
        assert "eventRecognitionConfidence" in candidate
        assert "transitionCausalityConfidence" in candidate


def test_boss_end_gap_is_not_closed_by_sparse_success_transition():
    payload = json.loads((ARTIFACT / "current-temporal-evidence-candidates.json").read_text(encoding="utf-8"))
    termination = next(item for item in payload["candidates"]
                       if item["executionDimensionId"] == "boss.termination")
    assert evaluate_probe({"candidates": [termination]})["status"] == "evidence_resolvable"
    assert termination["causalSupport"] == "uncertain"
    assert "boss_termination_condition" not in termination["observedFacets"]
