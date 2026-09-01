import json

from scripts.generate_phase531_mechanic_graphs import generate_phase531


def test_phase531_generates_six_read_only_graph_audit_artifacts(tmp_path):
    summary = generate_phase531(tmp_path)
    assert summary["mechanicCount"] == 6
    assert summary["templateReasoningCoverageScore"] == 95
    assert summary["mechanicReconstructionDepth"] < 95
    assert summary["rendererInvoked"] is False
    assert summary["parameterResolverInvoked"] is False
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
    assert provenance["modifiedRuleCount"] == provenance["modifiedGapCount"] == 0
    assert (tmp_path / "six-chapter-directed-reconstruction.md").exists()
