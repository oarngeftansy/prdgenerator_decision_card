import json

from scripts.generate_phase541_decision_worthiness import generate_phase541


def test_phase541_audits_all_candidates_without_rendering_planner_questions(tmp_path):
    summary = generate_phase541(tmp_path)
    assert summary["candidateCount"] == 32
    assert sum(summary["counts"].values()) == 32
    assert summary["counts"]["suppress"] > 0
    assert summary["counts"]["defer"] > 0
    assert summary["candidateQualityScore"] < summary["keptQualityScore"]
    assert summary["plannerQuestionGeneratedCount"] == 0
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
    assert provenance["modifiedReasoningGapCount"] == provenance["modifiedApprovedGapCount"] == 0
    body = (tmp_path / "candidate-gap-decision-audit.md").read_text(encoding="utf-8")
    assert "common_sense_deterministic" in body
    assert "over_defensive_edge_case" in body
