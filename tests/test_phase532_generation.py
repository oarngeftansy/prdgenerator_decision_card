import json

from scripts.generate_phase532_semantic_grounding import generate_phase532


def test_phase532_generates_six_chapter_readable_audit_without_mutating_authorities(tmp_path):
    summary = generate_phase532(tmp_path)
    assert summary["mechanicCount"] == 6
    assert summary["semanticComponentCount"] > summary["approvedRuleCount"]
    assert summary["rendererInvoked"] is summary["parameterResolverInvoked"] is False
    assert summary["modifiedApprovedRuleCount"] == summary["closedGapCount"] == 0
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
    body = (tmp_path / "six-chapter-semantic-grounding-audit.md").read_text(encoding="utf-8")
    assert "Approved Rule → Semantic decomposition" in body
    assert "Graph Grounding Quality" in body
