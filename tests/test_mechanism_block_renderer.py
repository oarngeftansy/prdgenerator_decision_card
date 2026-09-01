from backend.mechanism_block_renderer import render_mechanism_block


def entry(rule_id, text, subject="武器", rule_type="logic"):
    return {"ruleId": rule_id, "text": text, "subject": subject, "ruleType": rule_type, "schemaSlot": "attack_target", "semanticKey": f"K-{rule_id}"}


def blank_block():
    return {
        "blockId": "MB-1", "mechanismSemantic": "自动索敌", "status": "partial_mechanism_chain",
        "definition": [], "input_constraint": [], "trigger": [], "condition": [], "target_selection": [],
        "processing": [], "effect": [], "state_change": [], "result": [], "exit_boundary": [],
        "presentation": [], "config_reference": [],
        "ruleIds": [], "emptyFields": [], "unabsorbedGapIds": ["G1"],
    }


def test_renderer_stitches_same_block_rules_and_keeps_all_rule_ids():
    block = blank_block()
    block["input_constraint"] = [entry("R1", "武器无需玩家手动瞄准")]
    block["target_selection"] = [entry("R2", "武器选择射程内敌人作为攻击目标")]
    block["processing"] = [entry("R3", "武器向目标发射投射物或生成持续伤害区域")]
    block["input_constraint"][0]["semanticRole"] = "input_constraint"
    block["target_selection"][0]["semanticRole"] = "target_selection"
    block["processing"][0]["semanticRole"] = "processing"
    block["ruleIds"] = ["R1", "R2", "R3"]
    rendered = render_mechanism_block(block, {"organization_rules": {"contextual_subject_omission": True}, "raw_gve16_sentences": ["不得读取的句子"]})
    assert len(rendered["paragraphs"]) == 1
    paragraph = rendered["paragraphs"][0]
    assert paragraph["ruleIds"] == ["R1", "R2", "R3"]
    assert paragraph["text"] == "武器无需玩家手动瞄准，选择射程内敌人作为攻击目标，并向目标发射投射物或生成持续伤害区域。"
    assert "不得读取的句子" not in paragraph["text"]


def test_presentation_is_adjacent_but_not_mixed_into_logic_paragraph():
    block = blank_block()
    block["processing"] = [entry("R1", "怪物接触载具后造成伤害", "怪物")]
    block["presentation"] = [entry("R2", "首领显示独立长血条", "首领", "presentation")]
    block["ruleIds"] = ["R1", "R2"]
    rendered = render_mechanism_block(block, {"organization_rules": {}})
    assert [p["carrier"] for p in rendered["paragraphs"]] == ["mechanism", "presentation"]
    assert rendered["paragraphs"][0]["ruleIds"] == ["R1"]
    assert rendered["paragraphs"][1]["ruleIds"] == ["R2"]


def test_evidence_insufficient_block_renders_status_without_fake_paragraph():
    block = blank_block()
    block["status"] = "evidence_insufficient"
    rendered = render_mechanism_block(block, {"organization_rules": {}})
    assert rendered["paragraphs"] == []
    assert rendered["unsupportedSemanticAdditionCount"] == 0


def test_schema_slot_controlled_variant_removes_structured_field_wording():
    block = blank_block()
    pause = entry("R1", "系统升级触发时暂停游戏", "系统", "flow")
    pause["schemaSlot"] = "selection_pause"
    draw = entry("R2", "三选一升级触发时生成三张候选卡", "三选一")
    draw["schemaSlot"] = "random_trigger"
    block["trigger"] = [pause, draw]
    block["ruleIds"] = ["R1", "R2"]
    rendered = render_mechanism_block(block, {"organization_rules": {}})
    assert rendered["paragraphs"][0]["text"] == "升级触发后，暂停战斗并生成三张候选卡。"
    assert rendered["paragraphs"][0]["ruleIds"] == ["R1", "R2"]


def test_controlled_variant_does_not_replace_different_project_semantics():
    block = blank_block()
    pause = entry("R1", "回合升级时锁定操作", "系统", "flow")
    pause["schemaSlot"] = "selection_pause"
    draw = entry("R2", "升级时生成五张候选卡", "候选")
    draw["schemaSlot"] = "random_trigger"
    block["trigger"] = [pause, draw]
    block["ruleIds"] = ["R1", "R2"]
    section = render_mechanism_block(block, {"organization_rules": {}})["paragraphs"][0]
    assert section["format"] == "bullets"
    text = "".join(item["text"] for item in section["items"])
    assert text == "回合升级时锁定操作。升级时生成五张候选卡。"
    assert "三张" not in text


def test_unresolved_dependency_is_excluded_from_confirmed_paragraphs():
    block = blank_block()
    unresolved = entry("R1", "刷新操作存在消耗或替代条件", "刷新操作", "config")
    unresolved.update({"resolutionStatus": "unresolved_dependency", "semanticRole": "config_reference"})
    block["config_reference"] = [unresolved]
    block["ruleIds"] = ["R1"]
    rendered = render_mechanism_block(block, {"organization_rules": {}})
    assert rendered["paragraphs"] == []
    assert rendered["openDecisionSummary"][0]["ruleIds"] == ["R1"]


def test_parallel_presentation_uses_bullets_without_semicolon_stitching():
    block = blank_block()
    block["mechanismSemantic"] = "界面表现"
    block["presentation"] = [entry("R1", "显示长血条", "首领", "presentation"), entry("R2", "展示不同攻击形态", "首领", "presentation")]
    block["ruleIds"] = ["R1", "R2"]
    rendered = render_mechanism_block(block, {"organization_rules": {}})
    assert rendered["paragraphs"][0]["format"] == "bullets"
    assert [item["text"] for item in rendered["paragraphs"][0]["items"]] == ["显示长血条。", "展示不同攻击形态。"]
    assert "；" not in "".join(item["text"] for item in rendered["paragraphs"][0]["items"])
