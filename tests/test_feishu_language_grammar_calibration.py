import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_every_calibrated_sentence_records_content_language_and_omission_logic():
    data = json.loads((ROOT / "data/calibration/gve16/sentence-provenance.json").read_text(encoding="utf-8"))

    assert len(data["records"]) >= 15
    for record in data["records"]:
        assert record.get("contentRole"), record["id"]
        assert record.get("languageLogic"), record["id"]
        assert record.get("omissionLogic"), record["id"]


def test_document_grammar_models_sentence_paragraph_chapter_and_carrier_decisions():
    grammar = json.loads((ROOT / "data/calibration/gve16/document-grammar.json").read_text(encoding="utf-8"))

    assert grammar["sentenceGrammar"]["defaultOrder"] == ["condition", "actor_action", "system_result", "scope_or_boundary"]
    assert "runtime_owner" in grammar["subjectRules"]
    assert grammar["paragraphGrammar"]["mergeSparseSiblings"] is True
    assert grammar["chapterGrammar"]["fixedTemplateForbidden"] is True
    assert grammar["omissionRules"]["alreadyCarriedElsewhere"] == "do_not_repeat"
