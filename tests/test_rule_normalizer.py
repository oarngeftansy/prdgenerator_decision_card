from backend.rule_normalizer import build_approved_data_v2


def test_v2_builds_facts_slots_and_rules_only_from_claims_not_planner_sections():
    model = {"chapters": [{
        "id": "GCH-001", "systemName": "核心战斗", "scope": "武器",
        "claims": [
            {"id": "GCL-001", "text": "武器自动攻击目标。", "sourceFrameIds": ["F0001"]},
            {"id": "GCL-002", "text": "策划建议额外追加连击。", "sourceType": "planner", "sourceFrameIds": []},
        ],
        "plannerSections": {"keyRules": ["这是旧自由正文，不得进入事实链。"]},
    }]}
    approved = build_approved_data_v2(model)
    assert approved["contentModelVersion"] == 2
    assert approved["facts"] and approved["rules"] and approved["slots"]
    serialized = str(approved)
    assert "旧自由正文" not in serialized
    assert "追加连击" not in serialized


def test_slot_assignment_uses_business_semantics_not_incidental_keywords():
    model = {"chapters": [
        {"id": "GCH-1", "scope": "三选一", "systemName": "成长", "claims": [{
            "id": "GCL-1", "text": "选项使火焰喷射范围扩大30%，雷暴枪伤害增加100%。", "sourceFrameIds": ["F1"],
        }]},
        {"id": "GCH-2", "scope": "怪物", "systemName": "战斗", "claims": [{
            "id": "GCL-2", "text": "首领拥有独立长血条并展示不同攻击形态。", "sourceFrameIds": ["F2"],
        }]},
    ]}
    approved = build_approved_data_v2(model)
    rules = approved["rules"]
    effects = [rule for rule in rules if "30%" in rule["behavior"] or "100%" in rule["behavior"]]
    boss = [rule for rule in rules if "长血条" in rule["behavior"] or "攻击形态" in rule["behavior"]]
    assert effects and all(rule["schemaSlot"] != "weight_rule" for rule in effects)
    assert boss and all(rule["schemaSlot"] != "attack_range" for rule in boss)
    assert all(rule["ruleType"] == "presentation" for rule in boss)


def test_semantic_gate_marks_fragment_or_mismatch_needs_revision():
    model = {"chapters": [{
        "id": "GCH-1", "scope": "三选一", "systemName": "成长",
        "claims": [{"id": "GCL-1", "text": "刷新后显示新的三个选项。", "sourceFrameIds": ["F1"]}],
    }]}
    approved = build_approved_data_v2(model)
    assert all(not rule["behavior"].startswith("的") for rule in approved["rules"])
    assert all("semanticValidity" in rule for rule in approved["rules"])


def test_split_facts_route_to_semantic_sibling_chapters_instead_of_legacy_owner(monkeypatch):
    def node(title, chapter_type, claim_id):
        return {"title": title, "chapterType": chapter_type, "mechanicVariant": None,
                "classificationEvidence": [], "sourceItems": [{"source": f"claim:{claim_id}"}]}

    directory = {"tree": [{"title": "关卡推进", "objects": [{
        "title": "怪物", "chapters": [node("刷新", "spawn", "C1"), node("移动", "movement", "C2"), node("攻击", "attack", "C3")],
    }]}]}
    monkeypatch.setattr("backend.rule_normalizer.build_phase1_directory", lambda _model: directory)
    model = {"chapters": [{"claims": [
        {"id": "C1", "text": "怪物从屏幕上方生成并向下移动，接触载具造成伤害。", "sourceFrameIds": ["F1"]},
        {"id": "C2", "text": "怪物向载具移动。", "sourceFrameIds": ["F2"]},
        {"id": "C3", "text": "怪物攻击载具并造成伤害。", "sourceFrameIds": ["F3"]},
    ]}]}
    approved = build_approved_data_v2(model)
    chapter_type = {chapter["chapterId"]: chapter["chapterType"] for chapter in approved["chapters"]}
    split_rules = [rule for rule in approved["rules"] if "F1" in rule["evidenceIds"]]
    assert {chapter_type[rule["ownerChapterId"]] for rule in split_rules} == {"spawn", "movement", "attack"}
    assert next(rule for rule in split_rules if "移动" in rule["behavior"])["schemaSlot"] == "movement_trigger"
    assert next(rule for rule in split_rules if "造成伤害" in rule["behavior"])["schemaSlot"] == "attack_trigger"
