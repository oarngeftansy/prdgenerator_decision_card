from __future__ import annotations

from backend.canonical_prepublication import PREPUBLICATION_STAGE_ORDER, prepare_publication_input


def test_prepublication_stage_order_stops_before_p7(monkeypatch) -> None:
    import backend.canonical_prepublication as module

    monkeypatch.setattr(module, "build_gameplay_understanding_model", lambda model: {"digest": "u"})
    monkeypatch.setattr(module, "build_interaction_model", lambda understanding, source: {"digest": "i", "sourceRevision": 2})
    monkeypatch.setattr(module, "build_p1_directory_projection", lambda understanding: {"version": "p1"})
    monkeypatch.setattr(module, "build_p2_interaction_projection", lambda interaction: {"version": "p2"})
    monkeypatch.setattr(module, "build_p3_planning_snapshot", lambda gameplay, understanding, interaction, p1, p2: {"digest": "p3"})
    monkeypatch.setattr(module, "build_execution_rule_model", lambda gameplay, p3, config, transport=None: {"digest": "erm"})
    monkeypatch.setattr(module, "build_p4_review", lambda erm: {"ready": True, "digest": "p4"})
    monkeypatch.setattr(module, "build_p5_diagram_projection", lambda gameplay, erm: {"digest": "p5"})
    monkeypatch.setattr(module, "build_p6_parameter_projection", lambda gameplay, erm: {"digest": "p6"})
    monkeypatch.setattr(module, "build_publication_input_snapshot", lambda *args: {"digest": "snapshot"})

    prepared = prepare_publication_input({}, {}, object())

    assert tuple(prepared["stageTrace"]) == PREPUBLICATION_STAGE_ORDER
    assert "p7Delivery" not in prepared
    assert prepared["publicationInputSnapshot"]["digest"] == "snapshot"
    assert PREPUBLICATION_STAGE_ORDER[-1] == "publication_input_snapshot"
