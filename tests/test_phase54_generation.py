import json

from scripts.generate_phase54_reasoning_gap_expansion import generate_phase54


def test_phase54_generates_read_only_six_chapter_gap_audit(tmp_path):
    summary = generate_phase54(tmp_path)
    assert summary["mechanicCount"] == 6
    assert summary["reasoningGapCount"] > 0
    assert summary["qualityFailedCount"] == 0
    assert summary["modifiedApprovedGapCount"] == summary["modifiedApprovedRuleCount"] == 0
    assert summary["p4WriteCount"] == 0
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["sourceFilesUnchanged"] is True
    body = (tmp_path / "six-chapter-reasoning-gap-audit.md").read_text(encoding="utf-8")
    assert "Graph breakpoint → Existing Gap → ReasoningGap" in body
    assert "无 grounded node；禁止从模板扩写" in body
