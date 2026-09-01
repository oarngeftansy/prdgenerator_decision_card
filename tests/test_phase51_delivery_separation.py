import json

from scripts.generate_phase51_delivery_separation import generate_phase51_artifacts


def test_reference_generation_covers_six_chapters_and_all_presentation_rules(tmp_path):
    report = generate_phase51_artifacts(tmp_path)
    assert report["focusChapterCount"] == 6
    assert report["presentationRuleCount"] == report["visualBlockCount"]
    assert report["presentationToVisualBlockCoverage"] == 1.0
    assert report["visualBlockEntityResolutionRate"] == 1.0


def test_reference_generation_passes_delivery_hard_gates(tmp_path):
    report = generate_phase51_artifacts(tmp_path)
    assert report["presentationBackflowCount"] == 0
    assert report["presentationRuleCountInExecution"] == 0
    assert report["logicPresentationDuplicateDescriptionCount"] == 0
    assert report["unsupportedSemanticAdditionCount"] == 0
    assert report["gapRenderedAsConfirmedRuleCount"] == 0
    assert report["visualReferenceResolutionRate"] == 1.0
    assert report["ruleToFinalOutputTraceability"] == 1.0
    markdown = (tmp_path / "logic-only-execution.md").read_text(encoding="utf-8")
    assert "相关表现见策划草图" not in markdown
    assert all(prefix not in markdown for prefix in ("VIS-RULE-", "RULE-", "MB-", "GAP-"))
    delivery = json.loads((tmp_path / "phase51-delivery.json").read_text(encoding="utf-8"))
    assert delivery["traceability"]["logicRuleToVisualBlocks"]
    assert any(
        paragraph["relatedVisualBlockIds"]
        for chapter in delivery["chapters"]
        for paragraph in chapter["paragraphs"]
    )


def test_reference_generation_is_independent_and_records_non_mutation(tmp_path):
    generate_phase51_artifacts(tmp_path)
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["modifiedP7Count"] == 0
    assert provenance["modifiedUiCount"] == 0
    assert provenance["modifiedEntityGraphCount"] == 0
    assert provenance["modifiedRuleCount"] == 0
    assert provenance["modifiedGapCount"] == 0
    assert (tmp_path / "six-chapter-comparison.md").exists()
    assert (tmp_path / "visual-blocks.json").exists()
