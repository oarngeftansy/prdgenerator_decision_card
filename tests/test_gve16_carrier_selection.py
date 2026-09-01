import json
from pathlib import Path

from backend.gve16_carrier_selection import (
    append_synthesis_rules_to_chapters,
    build_carrier_plan,
    enrich_structured_chapters,
    parse_human_preview,
    render_carrier_preview,
)


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.4-carrier-selection-2026-08-18"


def _section(title, items, chapter="测试"):
    return [{"title": chapter, "sections": [{"title": title, "items": [{"text": text} for text in items]}]}]


def _structured_section(relations):
    items = []
    for position, rule_id in enumerate(("R1", "R2", "R3"), 1):
        items.append({
            "text": f"规则{position}。", "supportingRuleIds": [rule_id],
            "sourceDimensionIds": [f"D{position}"], "chainIds": ["CHAIN-1"],
            "chainPosition": position, "relations": relations.get(rule_id, []),
            "primaryOwner": "MECHANIC-1", "chapterOwner": "CHAPTER-1",
            "ownerPath": ["系统", "子系统", "机制"],
        })
    return [{"title": "旧分组", "sections": [{"title": "执行链", "items": items}]}]


def test_structured_rule_chain_identity_owner_and_relations_survive_carrier_selection():
    chapters = _structured_section({
        "R1": [{"type": "sequence", "targetRuleId": "R2"}],
        "R2": [{"type": "sequence", "targetRuleId": "R3"}],
    })
    plan = build_carrier_plan(chapters)
    assert len(plan) == 1
    assert plan[0]["selectedCarrier"] == "ordered_steps"
    assert plan[0]["sourceRuleIds"] == ["R1", "R2", "R3"]
    assert plan[0]["chainIds"] == ["CHAIN-1"]
    assert plan[0]["chainPositions"] == [1, 2, 3]
    assert plan[0]["relationTypes"] == ["sequence"]
    assert plan[0]["ownerPath"] == ["系统", "子系统", "机制"]
    assert plan[0]["primaryOwners"] == ["MECHANIC-1"]
    assert plan[0]["chapterOwners"] == ["CHAPTER-1"]


def test_relation_shape_changes_carrier_without_reinterpreting_rule_text():
    no_relation = build_carrier_plan(_structured_section({}))[0]
    sequence = build_carrier_plan(_structured_section({
        "R1": [{"type": "sequence", "targetRuleId": "R2"}],
    }))[0]
    branch = build_carrier_plan(_structured_section({
        "R1": [{"type": "branch", "targetRuleId": "R2"}],
    }))[0]
    assert no_relation["selectedCarrier"] == "rule_bullets"
    assert sequence["selectedCarrier"] == "ordered_steps"
    assert branch["selectedCarrier"] == "condition_branch"


def test_structured_publication_metadata_uses_existing_rule_and_owner_sources():
    chapters = _section("候选", ["升级时生成候选。", "候选范围：待确认。"], "旧分组")
    chapters[0]["sections"][0]["items"][0].update({
        "supportingRuleIds": ["R1"], "sourceDimensionIds": ["D1"], "itemType": "coreRule"})
    chapters[0]["sections"][0]["items"][1].update({
        "supportingRuleIds": ["R1"], "sourceDimensionIds": ["D2"],
        "itemType": "pending", "semanticType": "gameplay_parameter"})
    typed_rules = [{"ruleId": "R1", "primaryOwner": "选择机制", "chapterOwner": "成长",
                    "ruleRelations": ["level_up_to_selection"]}]
    owner_audit = {"systems": [{"title": "成长", "subsystems": [{
        "title": "选择机制", "ruleGroups": ["候选"]}]}], "ownerCorrections": []}
    enriched = enrich_structured_chapters(chapters, typed_rules, owner_audit)
    items = enriched[0]["sections"][0]["items"]
    assert len(items) == 1
    assert items[0]["ownerPath"] == ["成长", "选择机制"]
    assert items[0]["primaryOwner"] == "选择机制"
    assert items[0]["chapterOwner"] == "成长"
    assert items[0]["relations"][0]["type"] == "sequence"
    assert items[0]["parameterAttachments"] == [{
        "consumerRuleId": "R1", "text": "候选范围：待确认。"}]


def test_append_synthesis_rule_obeys_dynamic_owner_fields():
    base = _section("旧机制", ["既有规则。"], "旧章节")
    rule = {"ruleId": "SYN-REQ-1", "ownerChapter": "战斗数据", "ruleGroup": "伤害统计",
            "statement": "伤害统计以武器为统计单位。", "sourceDimensions": ["statistics.attribution"],
            "sourceRuleIds": ["RULE-1"], "classification": "game_rule"}
    first = append_synthesis_rules_to_chapters(base, [rule])
    assert first[-1]["title"] == "战斗数据"
    assert first[-1]["sections"][0]["title"] == "伤害统计"
    rule["ownerChapter"] = "关卡结束"
    rule["ruleGroup"] = "战斗统计"
    second = append_synthesis_rules_to_chapters(base, [rule])
    assert second[-1]["title"] == "关卡结束"
    assert second[-1]["sections"][0]["title"] == "战斗统计"


def test_append_rule_removes_only_explicitly_superseded_native_items():
    base = _section("旧机制", ["旧统计规则。", "其他规则。"], "结算")
    base[0]["sections"][0]["items"][0]["supportingRuleIds"] = ["SYN-OLD"]
    base[0]["sections"][0]["items"][1]["supportingRuleIds"] = ["SYN-KEEP"]
    rule = {"ruleId": "SYN-REQ", "ownerChapter": "结算", "ruleGroup": "统计",
            "statement": "新统计规则。", "sourceDimensions": [], "sourceRuleIds": ["RULE-NEW"],
            "supersedesSynthesisRuleIds": ["SYN-OLD"]}
    result = append_synthesis_rules_to_chapters(base, [rule])
    texts = [item["text"] for chapter in result for section in chapter["sections"] for item in section["items"]]
    assert texts == ["其他规则。", "新统计规则。"]


def test_verified_chain_projection_overrides_rule_local_relation_for_publication():
    chapters = _section("执行", ["进入。", "处理。"], "系统")
    for index, item in enumerate(chapters[0]["sections"][0]["items"], 1):
        item.update({"supportingRuleIds": [f"SYN-{index}"], "sourceDimensionIds": [f"D{index}"],
                     "itemType": "coreRule"})
    projection = {
        "SYN-1": [{"chainId": "CHAIN-REAL", "chainPosition": 1, "nodeRole": "entry",
                   "relationTypes": ["sequence"], "predecessorSynRuleIds": [],
                   "successorSynRuleIds": ["SYN-2"], "terminal": False, "resetRelation": False}],
        "SYN-2": [{"chainId": "CHAIN-REAL", "chainPosition": 2, "nodeRole": "exit",
                   "relationTypes": ["sequence"], "predecessorSynRuleIds": ["SYN-1"],
                   "successorSynRuleIds": [], "terminal": True, "resetRelation": False}],
    }
    enriched = enrich_structured_chapters(chapters, [], {}, projection)
    plan = build_carrier_plan(enriched)[0]
    assert plan["selectedCarrier"] == "ordered_steps"
    assert plan["chainIds"] == ["CHAIN-REAL"]
    assert plan["chainPositions"] == [1, 2]
    assert plan["chainPosition"] == 1
    assert plan["sourceItems"][1]["chainNodes"][0]["terminal"] is True


def test_verified_chain_position_controls_render_order_not_append_order():
    chapters = _section("流程", ["进入结算。", "击败后继续清理。"], "关卡")
    items = chapters[0]["sections"][0]["items"]
    items[0].update({"supportingRuleIds": ["SYN-EXIT"], "sourceDimensionIds": [],
                     "chainIds": ["CHAIN"], "chainPosition": 2,
                     "chainNodes": [{"chainId": "CHAIN"}], "relations": [{"type": "sequence"}]})
    items[1].update({"supportingRuleIds": ["SYN-CLEANUP"], "sourceDimensionIds": [],
                     "chainIds": ["CHAIN"], "chainPosition": 1,
                     "chainNodes": [{"chainId": "CHAIN"}], "relations": [{"type": "sequence"}]})
    plan = build_carrier_plan(chapters)[0]
    assert plan["sourceTexts"] == ["击败后继续清理。", "进入结算。"]


def test_sequential_core_rules_can_use_ordered_steps_but_optional_branch_stays_separate():
    chapters = _section("主体规则", ["等级提升时暂停战斗并生成3项。", "从3项中选择1项。"], "三选一")
    plan = build_carrier_plan(chapters)
    assert plan[0]["selectedCarrier"] == "ordered_steps"
    refresh = build_carrier_plan(_section("刷新", ["观看广告后刷新候选。", "刷新次数：待确认。"], "三选一"))[0]
    assert refresh["selectedCarrier"] != "ordered_steps"


def test_two_sparse_objects_do_not_trigger_a_parameter_table():
    plan = build_carrier_plan(_section("攻击", ["剧毒炮：发射炮弹。", "火焰喷射器：持续喷射。"], "武器"))
    assert all(item["selectedCarrier"] != "parameter_table" for item in plan)


def test_homogeneous_affix_rows_use_comparison_table_without_changing_rule_count():
    chapters = _section("词条效果", [
        "火焰扩张：火焰喷射范围+30%。", "雷暴增幅：雷暴枪伤害+100%。",
        "雷暴冷却：雷暴枪冷却时间-20%。", "多点爆炸：火焰爆炸次数+100%，伤害-20%。",
    ], "词条")
    plan = build_carrier_plan(chapters)
    assert plan[0]["selectedCarrier"] == "table"
    rendered = render_carrier_preview(chapters, plan)
    assert "| 词条 | 作用对象 | 效果 |" in rendered["markdown"]
    assert rendered["metrics"]["semanticLoss"] == 0
    assert rendered["metrics"]["sourceRuleItemCount"] == rendered["metrics"]["renderedRuleItemCount"] == 4


def test_formula_candidate_uses_formula_carrier_without_becoming_approved():
    chapters = _section("伤害统计", ["统计本局总伤害。", "武器伤害占比 = 该武器本局伤害 ÷ 本局总伤害。"], "结算")
    plan = build_carrier_plan(chapters)
    assert {item["selectedCarrier"] for item in plan} == {"rule_bullets", "formula"}
    assert next(item for item in plan if item["selectedCarrier"] == "formula")["approvalMutation"] is False


def test_phase64_artifact_has_no_semantic_change_or_unworthy_carrier():
    quality = json.loads((ARTIFACT_DIR / "phase64-quality-gate.json").read_text(encoding="utf-8"))
    metrics = json.loads((ARTIFACT_DIR / "carrier-comparison-metrics.json").read_text(encoding="utf-8"))
    assert quality["semanticLoss"] == 0
    assert quality["unsupportedCarrierChangeCount"] == 0
    assert quality["approvedRuleWrites"] == 0
    assert quality["pass"] is True
    assert metrics["before"]["bulletOnlyGroups"] > metrics["after"]["bulletOnlyGroups"]
    assert metrics["after"]["orderedStepGroups"] >= 1
    assert metrics["after"]["tableGroups"] >= 1
    assert metrics["after"]["formulaGroups"] >= 1
