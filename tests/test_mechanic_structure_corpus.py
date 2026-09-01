from pathlib import Path

import pytest

from backend.mechanic_structure_corpus import load_mechanic_structure_corpus


ROOT = Path(__file__).resolve().parents[1]
CORPUS_PATH = ROOT / "data/quality/gve16-mechanic-structure-corpus-v1.json"


def test_corpus_is_content_free_provisional_and_covers_required_chapter_types():
    corpus = load_mechanic_structure_corpus(CORPUS_PATH)
    assert set(corpus["mechanicTypes"]) == {
        "movement", "attack", "damage_death", "randomization",
        "slot", "unlock_progression", "settlement", "level_flow",
    }
    assert corpus["contentAuthority"] == "none"
    assert corpus["provisional"] is True
    assert all(item["sourceEvidence"] for item in corpus["mechanicTypes"].values())
    assert all(item["canCloseGap"] is False for item in corpus["mechanicTypes"].values())


def test_corpus_is_deeply_read_only():
    corpus = load_mechanic_structure_corpus(CORPUS_PATH)
    with pytest.raises(TypeError):
        corpus["mechanicTypes"]["attack"]["nodes"][0]["label"] = "changed"
