from backend.gameplay_directory import directory_errors, ensure_directory, synthesize_directory
from backend.gameplay_review_model import build_gameplay_review_model
from backend.gameplay_review_service import apply_gameplay_operations, confirm_gameplay_directory, undo_gameplay


def _draft(title, mechanism, claim_id, text):
    return {"scope": title, "mechanism": {"type": mechanism}, "claims": [{"id": claim_id, "text": text, "sourceType": "material", "sourceFrameIds": ["F0001"]}], "parameters": {}, "dependencies": [], "acceptanceCases": [], "unknowns": [], "sourceFrameIds": ["F0001"]}


def _model():
    drafts = [_draft("场景 1", "spatial_drag", "GCL-001", "玩家拖动方块进入目标位置"), _draft("场景 2", "progression", "GCL-002", "完成拼合后解锁下一项")]
    return build_gameplay_review_model({"id": "directory-test", "reviewModel": {"revision": 7}, "frames": [{"id": "F0001"}]}, drafts, synthesize_directory(drafts))


def test_synthesis_uses_observed_mechanics_without_fixed_combat_sections():
    model = _model()
    titles = [item["title"] for item in model["directory"]["entries"]]
    assert "武器系统" not in titles and "敌人及首领" not in titles
    assert len([item for item in model["directory"]["understanding"]["summary"].split("。") if item.strip()]) <= 4


def test_synthesis_publishes_phase1_classification_and_stable_naming_tree():
    drafts = [_draft("武器命中、反馈与伤害归集", "custom", "GCL-001", "武器进入射程后自动索敌并发射投射物。")]

    directory = synthesize_directory(drafts)

    assert directory["contentModelVersion"] == 2
    assert directory["entries"][0]["chapterType"] == "attack"
    assert directory["entries"][0]["mechanicVariant"] == "ranged"
    assert directory["entries"][0]["matchedSchema"].endswith(":attack:ranged")
    assert directory["entries"][0]["title"] == "武器"
    assert directory["entries"][0]["legacyTitle"] == "武器命中、反馈与伤害归集"
    assert directory["classifiedTree"][0]["objects"][0]["chapters"][0]["title"] == "攻击"
    assert directory["titleQualityReport"]["customCount"] == 0


def test_rename_and_reorder_preserve_chapter_confirmations():
    model = _model()
    for chapter in model["chapters"]:
        chapter.update(status="approved", confirmation={"confirmed": True, "revision": 1, "decision": "approved"})
    entries = model["directory"]["entries"]
    changed = apply_gameplay_operations(model, [{"type": "rename_directory_entry", "entryId": entries[0]["id"], "title": "空间拼合"}, {"type": "reorder_directory_entries", "entryIds": [entries[1]["id"], entries[0]["id"]]}], model["revision"])
    assert all(item["confirmation"]["confirmed"] for item in changed["chapters"])
    assert changed["reviewState"]["previewRevision"] is None


def test_update_directory_summary_keeps_directory_and_chapter_scope_in_sync():
    model = _model()
    entry = model["directory"]["entries"][0]

    changed = apply_gameplay_operations(model, [{
        "type": "update_directory_entry_summary",
        "entryId": entry["id"],
        "summary": "玩家拖动方块完成空间拼合，落位后立即结算。",
    }], model["revision"])

    updated = changed["directory"]["entries"][0]
    assert updated["summary"] == "玩家拖动方块完成空间拼合，落位后立即结算。"
    assert changed["directory"]["status"] == "draft"
    assert changed["reviewState"]["previewRevision"] is None


def test_move_directory_entry_to_system_persists_the_selected_module():
    model = _model()
    model["systems"] = [{"id": "GSY-001", "name": "核心战斗"}, {"id": "GSY-002", "name": "局内成长"}]
    entry = model["directory"]["entries"][0]
    entry["sectionTitle"] = "核心战斗"

    changed = apply_gameplay_operations(model, [{
        "type": "move_directory_entry_to_system",
        "entryId": entry["id"],
        "systemName": "局内成长",
    }], model["revision"])

    assert changed["directory"]["entries"][0]["sectionTitle"] == "局内成长"
    assert changed["directory"]["status"] == "draft"


def test_add_gameplay_system_creates_a_unique_empty_group_that_can_be_undone():
    model = _model()
    model["systems"] = [{"id": "GSY-001", "name": "核心战斗", "subsystems": []}]
    changed = apply_gameplay_operations(model, [{"type": "add_gameplay_system", "name": "局内成长"}], model["revision"])
    assert changed["systems"][-1] == {"id": "GSY-002", "name": "局内成长", "subsystems": []}
    restored = undo_gameplay(changed, changed["revision"])
    assert [item["name"] for item in restored["systems"]] == ["核心战斗"]


def test_move_claim_reopens_only_source_and_target_then_directory_confirms():
    model = _model(); entries = model["directory"]["entries"]
    for chapter in model["chapters"]:
        chapter.update(status="approved", confirmation={"confirmed": True, "revision": 1, "decision": "approved"})
    changed = apply_gameplay_operations(model, [{"type": "move_claim_between_entries", "claimId": "GCL-001", "targetEntryId": entries[1]["id"]}], model["revision"])
    assert [item["confirmation"]["confirmed"] for item in changed["chapters"]] == [False, False]
    confirmed = confirm_gameplay_directory(changed, changed["revision"])
    assert confirmed["directory"]["status"] == "confirmed"
    assert directory_errors(confirmed, require_confirmed=True) == []


def test_dynamic_structure_requires_system_then_mechanism_confirmation():
    model = _model()
    model["reviewState"].update({
        "status": "system_directory_review",
        "structurePhase": "systems",
        "depthContractVersion": 1,
    })

    systems_confirmed = confirm_gameplay_directory(model, model["revision"])

    assert systems_confirmed["reviewState"]["status"] == "mechanism_directory_review"
    assert systems_confirmed["reviewState"]["structurePhase"] == "mechanisms"
    assert systems_confirmed["directory"]["status"] == "draft"
    assert systems_confirmed["reviewState"]["systemsConfirmedAtRevision"] == systems_confirmed["revision"]

    mechanisms_confirmed = confirm_gameplay_directory(systems_confirmed, systems_confirmed["revision"])

    assert mechanisms_confirmed["reviewState"]["status"] == "detail_generation_pending"
    assert mechanisms_confirmed["reviewState"]["structurePhase"] == "confirmed"
    assert mechanisms_confirmed["directory"]["status"] == "confirmed"
    assert mechanisms_confirmed["reviewState"]["mechanismsConfirmedAtRevision"] == mechanisms_confirmed["revision"]


def test_confirm_directory_upgrades_historical_chapter_shape_and_decision_ids():
    model = _model()
    chapter = model["chapters"][0]
    for field in ("claims", "mechanism", "parameters", "dependencies", "acceptanceCases", "unknowns", "status", "confirmation"):
        chapter.pop(field, None)
    chapter["decisionCards"] = [{
        "id": "GDC-GCH-001-legacy-choice",
        "question": "历史规则采用哪一种处理方式？",
        "options": [{"id": "a", "label": "方案 A"}, {"id": "b", "label": "方案 B"}],
        "status": "pending",
    }]
    entry = model["directory"]["entries"][0]
    entry["claimIds"] = []
    model["directory"]["unassignedClaimIds"] = []

    confirmed = confirm_gameplay_directory(model, model["revision"])

    upgraded = confirmed["chapters"][0]
    assert upgraded["mechanism"] == {"type": "custom"}
    assert upgraded["claims"] == []
    assert upgraded["confirmation"] == {"confirmed": False, "revision": None}
    assert upgraded["decisionCards"][0]["id"] == "GDC-001"
    assert confirmed["directory"]["status"] == "confirmed"


def test_ensure_directory_backfills_historical_claim_ownership_without_reopening_review():
    model = _model()
    original_status = model["directory"]["status"]
    original_revision = model["directory"]["revision"]
    for entry in model["directory"]["entries"]:
        entry["claimIds"] = []
    model["directory"]["unassignedClaimIds"] = ["GCL-001", "GCL-002"]

    directory = ensure_directory(model)

    claims_by_chapter = {
        chapter["id"]: [claim["id"] for claim in chapter["claims"]]
        for chapter in model["chapters"]
    }
    assert all(entry["claimIds"] == claims_by_chapter[entry["chapterId"]] for entry in directory["entries"])
    assert directory["unassignedClaimIds"] == []
    assert directory["status"] == original_status
    assert directory["revision"] == original_revision


def test_historical_claims_without_ids_become_splittable_when_model_is_loaded():
    from backend.gameplay_review_model import ensure_gameplay_review_model

    model = _model()
    for chapter in model["chapters"]:
        for claim in chapter["claims"]:
            claim.pop("id", None)
    for entry in model["directory"]["entries"]:
        entry["claimIds"] = []
    job = {"id": "legacy-claim-test", "frames": [{"id": "F0001"}], "gameplayReviewModel": model}

    loaded = ensure_gameplay_review_model(job)

    claim_ids = [claim["id"] for chapter in loaded["chapters"] for claim in chapter["claims"]]
    assert len(claim_ids) == len(set(claim_ids))
    assert all(claim_id.startswith("GCL-") for claim_id in claim_ids)
    claims_by_chapter = {chapter["id"]: [claim["id"] for claim in chapter["claims"]] for chapter in loaded["chapters"]}
    assert all(entry["claimIds"] == claims_by_chapter[entry["chapterId"]] for entry in loaded["directory"]["entries"])


def test_historical_decision_ids_are_normalized_before_the_browser_can_submit_them():
    from backend.gameplay_review_model import ensure_gameplay_review_model

    model = _model()
    model["chapters"][0]["decisionCards"] = [{
        "id": "GDC-GCH-001-legacy-choice",
        "question": "历史规则采用哪一种处理方式？",
        "options": [{"id": "a", "label": "方案 A"}, {"id": "b", "label": "方案 B"}],
        "status": "pending",
    }]
    job = {"id": "directory-test", "frames": [{"id": "F0001"}], "gameplayReviewModel": model}

    loaded = ensure_gameplay_review_model(job)

    assert loaded["chapters"][0]["decisionCards"][0]["id"] == "GDC-001"
    assert loaded["chapters"][0]["decisionCards"][0]["legacyIds"] == ["GDC-GCH-001-legacy-choice"]
