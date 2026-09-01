import json
from pathlib import Path

from backend.gve16_native_planning_language import (
    evaluate_gve16_language_smells,
    render_gve16_native_planning_language,
)


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.3-native-language-2026-08-18"


def _item(text, dimension, subrules=None):
    return {
        "text": text, "sourceDimensionIds": [dimension], "supportingRuleIds": [f"RULE-{dimension}"],
        "subrules": subrules or [], "itemType": "coreRule", "semanticType": "persistent_game_rule",
    }


def _hierarchy(chapter, section, items):
    return {"chapters": [{"title": chapter, "sections": [{
        "title": section, "sourceGroupIds": ["GROUP"], "items": items,
        "headingRetentionReason": "multiple_rules",
    }]}]}


def test_concrete_weapon_rules_replace_abstract_summary_without_losing_provenance():
    source = _hierarchy("武器", "攻击", [_item(
        "不同武器使用不同攻击方式。", "attack_method",
        ["剧毒炮向敌人发射剧毒炮弹。", "火焰喷射器持续向前喷射。"])])
    result = render_gve16_native_planning_language(source)
    items = result["chapters"][0]["sections"][0]["items"]
    assert [item["text"] for item in items] == [
        "剧毒炮：向敌人发射剧毒炮弹。", "火焰喷射器：持续向前喷射。"]
    assert all(item["supportingRuleIds"] == ["RULE-attack_method"] for item in items)
    assert all(item["sourceDimensionIds"] == ["attack_method"] for item in items)
    assert "不同武器使用不同攻击方式" not in result["markdown"]


def test_settlement_summary_splits_into_two_dense_rules_with_same_provenance():
    source = _hierarchy("结算", "伤害统计", [
        _item("结算展示本局总伤害，并按武器统计伤害占比。", "damage_statistics")])
    result = render_gve16_native_planning_language(source)
    items = result["chapters"][0]["sections"][0]["items"]
    assert [item["text"] for item in items] == ["统计本局总伤害。", "按武器统计伤害占比。"]
    assert all(item["sourceDimensionIds"] == ["damage_statistics"] for item in items)


def test_pending_success_result_renders_only_actionable_unknown():
    source = _hierarchy("关卡", "胜负", [_item(
        "关卡可正常通关，通关条件：待确认。", "success_condition")])
    result = render_gve16_native_planning_language(source)
    assert result["chapters"][0]["sections"][0]["items"][0]["text"] == "通关条件：待确认。"
    assert result["chapters"][0]["sections"][0]["items"][0]["sourceDimensionIds"] == ["success_condition"]


def test_visual_spawn_position_is_removed_while_logic_relation_remains():
    source = _hierarchy("怪物", "普通怪物", [_item(
        "怪物从画面上方进入战斗区域，并向载具所在区域移动。", "spawn_movement")])
    result = render_gve16_native_planning_language(source)
    text = result["chapters"][0]["sections"][0]["items"][0]["text"]
    assert text == "怪物进入战区后向载具移动。"
    assert "画面上方" not in result["markdown"]


def test_language_smell_gate_detects_before_and_clears_supported_rewrite():
    before = "- 不同武器使用不同攻击方式。\n- 结算展示伤害。\n- 结算展示奖励。\n"
    after = "- 剧毒炮：向敌人发射剧毒炮弹。\n- 统计本局总伤害。\n- 展示本局获得的道具及数量。\n"
    trace = [{"finalText": line[2:], "supportingRuleIds": ["RULE"], "sourceDimensionIds": ["dim"]}
             for line in after.splitlines()]
    report = evaluate_gve16_language_smells(before, after, trace)
    assert report["before"]["abstract_summary_sentence"] == 1
    assert report["before"]["repeated_subject"] >= 1
    assert report["after"]["abstract_summary_sentence"] == 0
    assert report["after"]["repeated_subject"] == 0
    assert report["hardLosses"] == {"lost_condition": 0, "lost_target": 0, "lost_result": 0,
                                    "lost_number": 0, "ambiguous_rule": 0}


def test_phase63_artifact_passes_language_and_semantic_conservation_gates():
    quality = json.loads((ARTIFACT_DIR / "phase63-quality-gate.json").read_text(encoding="utf-8"))
    report = json.loads((ARTIFACT_DIR / "gve16-language-smell-report.json").read_text(encoding="utf-8"))
    preview = (ARTIFACT_DIR / "human-planning-preview.md").read_text(encoding="utf-8")
    assert quality["lostRuleSemanticCount"] == 0
    assert quality["untraceableFinalSentenceCount"] == 0
    assert quality["unsupportedSemanticAddition"] == 0
    assert quality["pass"] is True
    assert all(value == 0 for value in report["after"].values())
    assert all(value == 0 for value in report["hardLosses"].values())
    assert "不同武器使用不同攻击方式" not in preview
    assert "结算展示" not in preview
    assert "画面上方" not in preview
