from backend.chapter_schema_library import chapter_schema_library
from backend.mechanism_composer import compose_mechanism_blocks


def approved(rule_id, slot, behavior, rule_type="logic", subject="武器", semantic_key=None):
    return {
        "ruleId": rule_id,
        "semanticKey": semantic_key or f"C:{slot}:{rule_id}",
        "ownerChapterId": "C",
        "schemaSlot": slot,
        "ruleType": rule_type,
        "subject": subject,
        "behavior": behavior,
        "trigger": None,
        "conditions": [],
        "result": None,
        "stateChange": None,
        "exitCondition": None,
        "parameterRefs": [],
        "sourceFactIds": [f"F-{rule_id}"],
        "evidenceIds": [f"E-{rule_id}"],
        "reviewStatus": "approved",
        "semanticValidity": "valid",
    }


def test_role_assignment_uses_chapter_slot_and_rule_fields_not_behavior_keywords():
    chapter = {"chapterId": "C", "chapterType": "attack", "mechanicVariant": "ranged", "title": "攻击"}
    schema = chapter_schema_library.resolve("attack", "ranged", "chapter-schema-v2")
    rules = [approved("R1", "attack_target", "完全不含预设关键词的已确认行为")]
    blocks = compose_mechanism_blocks(chapter, rules, [], schema)
    assert blocks[0]["target_selection"][0]["ruleId"] == "R1"
    assert blocks[0]["trigger"] == []
    assert "trigger" in blocks[0]["emptyFields"]


def test_partition_keeps_schema_groups_separate_and_gaps_unabsorbed():
    chapter = {"chapterId": "C", "chapterType": "randomization", "mechanicVariant": "three_choice", "title": "候选"}
    schema = chapter_schema_library.resolve("randomization", "three_choice", "chapter-schema-v2")
    rules = [
        approved("R1", "random_trigger", "升级后生成候选"),
        approved("R2", "refresh_rule", "刷新后替换候选", "interaction"),
    ]
    gaps = [{"gapId": "G1", "chapterId": "C", "schemaSlot": "weight_rule", "status": "reviewed_open"}]
    blocks = compose_mechanism_blocks(chapter, rules, gaps, schema)
    assert [block["mechanismSemantic"] for block in blocks] == ["候选流程", "刷新处理"]
    assert all(block["unabsorbedGapIds"] == ["G1"] for block in blocks)
    assert {rid for block in blocks for rid in block["ruleIds"]} == {"R1", "R2"}


def test_no_approved_rules_produces_evidence_insufficient_without_fake_fields():
    chapter = {"chapterId": "C", "chapterType": "level_flow", "title": "关卡流程"}
    schema = chapter_schema_library.resolve("level_flow", None, "chapter-schema-v2")
    blocks = compose_mechanism_blocks(chapter, [], [{"gapId": "G1", "chapterId": "C", "status": "reviewed_open"}], schema)
    assert len(blocks) == 1
    assert blocks[0]["status"] == "evidence_insufficient"
    assert blocks[0]["ruleIds"] == []
    assert blocks[0]["unabsorbedGapIds"] == ["G1"]
    assert all(blocks[0][field] == [] for field in ("definition", "input_constraint", "trigger", "condition", "target_selection", "processing", "effect", "state_change", "result", "exit_boundary", "presentation", "config_reference"))


def test_layered_role_resolver_disambiguates_attack_semantics_with_reasons():
    chapter = {"chapterId": "C", "chapterType": "attack", "mechanicVariant": "ranged", "title": "攻击"}
    schema = chapter_schema_library.resolve("attack", "ranged", "chapter-schema-v2")
    rules = [
        approved("R1", "attack_trigger", "武器无需玩家手动瞄准"),
        approved("R2", "attack_target", "武器选择射程内敌人作为攻击目标"),
        approved("R3", "attack_target", "武器向目标发射投射物或生成持续伤害区域"),
    ]
    block = compose_mechanism_blocks(chapter, rules, [], schema)[0]
    assert block["input_constraint"][0]["ruleId"] == "R1"
    assert block["target_selection"][0]["ruleId"] == "R2"
    assert block["processing"][0]["ruleId"] == "R3"
    assignments = {item["ruleId"]: item for role in ("input_constraint", "target_selection", "processing") for item in block[role]}
    assert all(item["roleAssignmentReason"] for item in assignments.values())
    assert all(item["resolutionStatus"] == "executable" for item in assignments.values())
    assert block["synonymousBlockMergeCount"] == 2


def test_vague_refresh_cost_is_unresolved_dependency_not_confirmed_prose():
    chapter = {"chapterId": "C", "chapterType": "randomization", "mechanicVariant": "three_choice", "title": "刷新"}
    schema = chapter_schema_library.resolve("randomization", "three_choice", "chapter-schema-v2")
    blocks = compose_mechanism_blocks(chapter, [approved("R1", "refresh_cost", "刷新操作存在消耗或替代条件", "config")], [], schema)
    item = blocks[0]["config_reference"][0]
    assert item["resolutionStatus"] == "unresolved_dependency"
    assert "predicate_pattern_disambiguation" in item["roleAssignmentReason"]
