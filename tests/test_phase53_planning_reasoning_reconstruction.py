import json

from scripts.generate_phase53_planning_reasoning import generate_phase53_planning_reasoning


def test_six_chapter_reconstruction_is_read_only_and_gap_localized(tmp_path):
    summary = generate_phase53_planning_reasoning(tmp_path)
    models = json.loads((tmp_path / "planning-mechanism-models.json").read_text(encoding="utf-8"))
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))

    assert summary["modelCount"] == 6
    assert summary["unmappedGapCount"] == 0
    assert summary["localizedGapCount"] == 29
    assert all(model["nonConfirmedNodesCanGenerateRule"] is False for model in models)
    assert all(node["content"] is None for model in models for node in model["derivedStructureNodes"] + model["hypothesisNodes"] + model["unresolvedNodes"])
    assert provenance["sourceFilesUnchanged"] is True
    assert provenance["modifiedRuleCount"] == provenance["modifiedGapCount"] == 0
    assert provenance["modifiedExecutionDocumentCount"] == 0
    assert provenance["parameterResolverInvoked"] is False


def test_six_chapter_audit_exposes_all_four_reasoning_statuses_and_depth(tmp_path):
    summary = generate_phase53_planning_reasoning(tmp_path)
    assert summary["nodeStatusCounts"]["confirmed"] > 0
    assert summary["nodeStatusCounts"]["derived_structure"] > 0
    assert summary["nodeStatusCounts"]["hypothesis"] > 0
    assert summary["nodeStatusCounts"]["unresolved"] > 0
    assert summary["planningReasoningDepth"] > 0
    assert (tmp_path / "six-chapter-planning-reconstruction.md").exists()
