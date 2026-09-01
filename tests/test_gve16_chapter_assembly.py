import json
from pathlib import Path

import pytest

from backend.gve16_chapter_assembly import assemble_gve16_chapters


ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts" / "planning-content-phase6.5-chapter-assembly-2026-08-18"


def _plan(chapter, group, carrier, texts, status="publishable"):
    return {"chapter": chapter, "ruleGroup": group, "selectedCarrier": carrier,
            "sourceTexts": texts, "publishStatus": status}


def test_candidate_formula_remains_in_plan_but_is_not_published():
    plans = [
        _plan("结算", "伤害统计", "rule_bullets", ["统计本局总伤害。"]),
        _plan("结算", "伤害统计", "formula", ["占比 = 武器伤害 ÷ 总伤害。"], "candidate_only"),
    ]
    result = assemble_gve16_chapters(plans, ["结算"])
    assert "占比 =" not in result["markdown"]
    assert result["metrics"]["candidateOnlyItemsSuppressed"] == 1
    assert any(item["selectedCarrier"] == "formula" for item in plans)


def test_weapon_parameters_are_grouped_after_confirmed_attack_rules():
    plans = [
        _plan("武器", "攻击", "rule_bullets", ["武器自动攻击射程内敌人。", "剧毒炮：发射炮弹。"]),
        _plan("武器", "攻击", "parameter_list", ["攻击范围：待确认。", "攻击间隔：待确认。"]),
    ]
    markdown = assemble_gve16_chapters(plans, ["武器"])["markdown"]
    assert markdown.index("剧毒炮") < markdown.index("参数：") < markdown.index("攻击范围")


def test_three_choice_pending_is_attached_to_candidate_generation_not_made_a_step():
    plans = [
        _plan("三选一", "主体规则", "ordered_steps", ["升级时生成3项候选。", "从3项中选择1项。"]),
        _plan("三选一", "主体规则", "rule_bullets", ["可获取内容范围：待确认。"]),
    ]
    markdown = assemble_gve16_chapters(plans, ["三选一"])["markdown"]
    assert "1. 升级时生成3项候选。\n   - 可获取内容范围：待确认。\n2. 从3项中选择1项。" in markdown
    assert "3. 可获取内容范围" not in markdown


def test_dynamic_owner_path_creates_natural_system_hierarchy_without_fixed_titles():
    plans = [{**_plan("词条", "词条效果", "rule_bullets", ["范围提升30%。"]),
              "ownerPath": ["核心战斗", "武器", "词条"]}]
    markdown = assemble_gve16_chapters(plans, ["词条"])["markdown"]
    assert "## 核心战斗\n\n### 武器\n\n#### 词条" in markdown
    assert "## 词条" not in markdown.splitlines()


def test_chain_positions_order_groups_and_attach_review_and_parameter_to_their_step():
    plans = [
        {**_plan("武器", "获取", "rule_bullets", ["通过抽取获得武器。"]), "chainPosition": 10},
        {**_plan("武器", "攻击", "rule_bullets", ["武器自动攻击射程内敌人。"]), "chainPosition": 30},
        {**_plan("武器", "武器栏", "rule_bullets", ["获得武器后如何处理栏位：待确认。"]),
         "chainPosition": 20, "attachAfterGroup": "获取"},
        {**_plan("武器", "攻击参数", "parameter_list", ["攻击间隔：待确认。"]),
         "chainPosition": 31, "attachAfterGroup": "攻击"},
    ]
    markdown = assemble_gve16_chapters(plans, ["武器"])["markdown"]
    assert markdown.index("### 获取") < markdown.index("### 武器栏") < markdown.index("### 攻击")
    assert markdown.index("武器自动攻击") < markdown.index("攻击间隔")
    assert "参数：\n- 攻击间隔：待确认。" in markdown


def test_structured_review_and_parameter_remain_attached_to_consumer_mechanic():
    plans = [{
        **_plan("旧分组", "攻击链", "ordered_steps", ["锁定目标。", "造成伤害。"]),
        "ownerPath": ["核心战斗", "武器", "攻击"],
        "sourceRuleIds": ["R1", "R2"], "chainIds": ["C1"],
        "relations": [{"type": "sequence", "sourceRuleId": "R1", "targetRuleId": "R2"}],
        "reviewAttachments": [{"consumerRuleId": "R1", "text": "目标失效条件：待确认。"}],
        "parameterAttachments": [{"consumerRuleId": "R2", "text": "伤害系数：待确认。", "unit": "倍率"}],
    }]
    result = assemble_gve16_chapters(plans, ["旧分组"])
    markdown = result["markdown"]
    assert "## 核心战斗\n\n### 武器\n\n#### 攻击" in markdown
    assert "1. 锁定目标。\n   - 待确认：目标失效条件：待确认。\n2. 造成伤害。\n   - 参数：伤害系数：待确认。（单位：倍率）" in markdown
    assert markdown.count("锁定目标。") == markdown.count("造成伤害。") == 1


def test_one_legacy_group_can_publish_into_multiple_dynamic_owners_without_loss():
    plans = [
        {**_plan("旧结算", "统计", "rule_bullets", ["统计伤害。"]),
         "ownerPath": ["关卡结束", "战斗统计"]},
        {**_plan("旧结算", "奖励", "rule_bullets", ["展示奖励。"]),
         "ownerPath": ["关卡结束", "结算"]},
    ]
    markdown = assemble_gve16_chapters(plans, ["旧结算"])["markdown"]
    assert "### 战斗统计" in markdown and "统计伤害。" in markdown
    assert "### 结算" in markdown and "展示奖励。" in markdown


def test_bullet_rule_keeps_its_review_and_parameter_attachments():
    plans = [{
        **_plan("武器", "攻击", "rule_bullets", ["自动攻击目标。"]),
        "sourceItems": [{"text": "自动攻击目标。", "supportingRuleIds": ["R1"],
                         "reviewAttachments": [{"consumerRuleId": "R1", "text": "目标范围：待确认。"}],
                         "parameterAttachments": [{"consumerRuleId": "R1", "text": "攻击间隔：待确认。"}]}],
    }]
    markdown = assemble_gve16_chapters(plans, ["武器"])["markdown"]
    assert "- 自动攻击目标。\n  - 待确认：目标范围：待确认。\n  - 参数：攻击间隔：待确认。" in markdown


def test_planning_title_merges_lifecycle_dimensions_and_keeps_review_metadata_out_of_body():
    common = {
        "chapter": "怪物", "ownerPath": ["怪物", "普通怪物"],
        "planningTitle": "行为逻辑", "selectedCarrier": "lifecycle_sequence",
        "publishStatus": "publishable", "proposalType": "design_inference",
        "assumptionLevel": "medium", "proposalId": "PROP-1",
    }
    plans = [
        {**common, "ruleGroup": "movement.state", "sourceTexts": ["怪物向载具移动。"]},
        {**common, "ruleGroup": "attack.entry", "sourceTexts": ["与载具接触后造成伤害。"]},
        {**common, "ruleGroup": "attack.post_exit_state", "sourceTexts": ["接触结束后继续移动。"]},
    ]
    markdown = assemble_gve16_chapters(plans, ["怪物"])["markdown"]
    assert markdown.count("#### 行为逻辑") == 1
    assert "movement.state" not in markdown
    assert "attack.entry" not in markdown
    assert "attack.post_exit_state" not in markdown
    assert "design_inference" not in markdown
    assert "medium" not in markdown
    assert "PROP-1" not in markdown
    assert "1. 怪物向载具移动。" in markdown
    assert "2. 与载具接触后造成伤害。" in markdown
    assert "3. 接触结束后继续移动。" in markdown


def test_internal_dimension_id_cannot_be_used_as_publication_heading():
    with pytest.raises(ValueError, match="internal execution dimension"):
        assemble_gve16_chapters([
            _plan("怪物", "attack.post_exit_state", "rule_bullets", ["继续移动。"])
        ], ["怪物"])


def test_phase65_artifact_passes_assembly_gate():
    quality = json.loads((ARTIFACT_DIR / "phase65-quality-gate.json").read_text(encoding="utf-8"))
    comparison = json.loads((ARTIFACT_DIR / "assembly-comparison-metrics.json").read_text(encoding="utf-8"))
    preview = (ARTIFACT_DIR / "human-planning-preview.md").read_text(encoding="utf-8")
    assert quality["duplicatedRuleDefinition"] == 0
    assert quality["orphanFormula"] == 0
    assert quality["candidateOnlyFormulaPublished"] == 0
    assert quality["AIChapterIntro"] == 0
    assert quality["pass"] is True
    assert comparison["after"]["orphanPending"] < comparison["before"]["orphanPending"]
    assert "武器伤害占比 =" not in preview
