import json
from pathlib import Path

import pytest

from backend.gve16_alignment_corpus import load_gve16_alignment_corpus


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data/quality/gve16-alignment-corpus-v1.json"


def test_corpus_is_sanitized_provisional_and_separates_hard_constraints():
    corpus = load_gve16_alignment_corpus(CORPUS_PATH)
    assert corpus["corpusVersion"] == "gve16-alignment-corpus-v1"
    assert all(item["provisional"] is True for item in corpus["provisionalReferences"].values())
    assert corpus["hardConstraints"]["crossSemanticDomainParagraphCount"] == 0
    assert corpus["hardConstraints"]["ruleToFinalOutputTraceability"] == 1.0
    assert corpus["contentAuthority"] == "none"


def test_corpus_is_recursively_immutable():
    corpus = load_gve16_alignment_corpus(CORPUS_PATH)
    with pytest.raises(TypeError):
        corpus["hardConstraints"]["crossSemanticDomainParagraphCount"] = 1
    with pytest.raises(TypeError):
        corpus["provisionalReferences"]["titleLength"]["median"] = 99


def test_serialized_corpus_contains_no_project_content_or_runtime_rules():
    raw = CORPUS_PATH.read_text(encoding="utf-8")
    for forbidden in ("一路狂飙", "载具", "武器", "怪物", "RULE-", "GAP-", "05:14"):
        assert forbidden not in raw
    data = json.loads(raw)
    assert "rawSentences" not in data
    assert "chapterTree" not in data
    assert "projectFields" not in data


def test_loader_rejects_mutable_or_content_authority_corpus(tmp_path):
    bad = {
        "corpusVersion": "gve16-alignment-corpus-v1", "contentAuthority": "rules",
        "provisionalReferences": {}, "hardConstraints": {},
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="content authority"):
        load_gve16_alignment_corpus(path)
