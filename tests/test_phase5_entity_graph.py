import json
from pathlib import Path

from scripts.generate_phase5_entity_graph import main


ROOT = Path(__file__).resolve().parents[1]


def test_phase5_reference_graph_has_locked_entities_and_no_presentation_backflow(tmp_path, monkeypatch):
    import scripts.generate_phase5_entity_graph as generator

    monkeypatch.setattr(generator, "OUT", tmp_path)
    main()
    graph = json.loads((tmp_path / "entity-graph.json").read_text(encoding="utf-8"))
    ownership = json.loads((tmp_path / "owner-reference-audit.json").read_text(encoding="utf-8"))
    assert len(graph["entities"]) == 10
    assert {e["entityType"] for e in graph["entities"]} == {
        "runtime_object", "container", "content_item", "candidate_set",
        "runtime_context", "process", "report",
    }
    assert graph["pollutionAudit"]["passed"] is True
    assert graph["pollutionAudit"]["presentationBackflowCount"] == 0
    assert graph["pollutionAudit"]["presentationCreatedEntityCount"] == 0
    assert ownership["duplicatePrimaryDefinitionCount"] == 0
    assert any(ref["ruleId"] == "RULE-F15E69B46EF3" and "ENT-VEHICLE" in ref["relatedEntityIds"] for ref in graph["presentationRuleReferences"])


def test_phase5_does_not_modify_phase43_reference_or_source_job(tmp_path, monkeypatch):
    import scripts.generate_phase5_entity_graph as generator

    monkeypatch.setattr(generator, "OUT", tmp_path)
    before_job = generator._sha(generator.JOB)
    before_reference = generator._sha(generator.REFERENCE)
    main()
    assert generator._sha(generator.JOB) == before_job
    assert generator._sha(generator.REFERENCE) == before_reference
    provenance = json.loads((tmp_path / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["modifiedRuleCount"] == 0
    assert provenance["modifiedGapCount"] == 0
    assert provenance["modifiedReferenceDocumentCount"] == 0
    assert provenance["modifiedP7Count"] == 0
