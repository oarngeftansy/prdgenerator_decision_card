import pytest

from backend.feishu_language_quality import language_quality_report
from backend.gameplay_rule_copy import enrich_gameplay_draft, legacy_planner_sections_adapter, migrate_gameplay_rule_copy, normalize_optional_modules, planner_sections, sanitize_generated_optional_modules, sanitize_generated_semantics


def test_keeps_supported_formula_and_omits_empty_optional_modules():
    chapter = normalize_optional_modules({
        "formulae": [{
            "expression": "最终伤害 = 攻击属性 × 武器倍率",
            "variables": [{
                "name": "攻击属性", "evidenceLevel": "material", "sourceFrameIds": ["F0001"],
            }, {
                "name": "武器倍率", "evidenceLevel": "reference_document", "referenceSource": "武器配置表",
            }],
            "evidenceLevel": "inference", "sourceFrameIds": ["F0001"],
        }],
        "workedExamples": [],
        "configurationSources": [{
            "title": "武器基础属性表", "field": "damageRatio",
            "evidenceLevel": "reference_document", "referenceSource": "样例策划案",
        }],
    })

    assert chapter["formulae"][0]["expression"] == "最终伤害 = 攻击属性 × 武器倍率"
    assert "workedExamples" not in chapter
    assert chapter["configurationSources"][0]["field"] == "damageRatio"


def test_rejects_formula_without_evidence_for_itself_and_variables():
    with pytest.raises(ValueError, match="formula evidence"):
        normalize_optional_modules({
            "formulae": [{"expression": "结果 = A × B", "variables": [{"name": "A"}, {"name": "B"}]}],
        })


def test_generated_optional_modules_drop_unsupported_values_without_aborting_chapter():
    chapter, warnings = sanitize_generated_optional_modules({
        "scope": "伤害计算",
        "parameterSchema": [
            {"name": "攻击力", "evidenceLevel": "material", "sourceFrameIds": ["F0001"]},
            {"name": "暴击倍率"},
        ],
        "formulae": [{"expression": "伤害=攻击力×倍率", "variables": [{"name": "攻击力"}]}],
    })

    assert [row["name"] for row in chapter["parameterSchema"]] == ["攻击力"]
    assert "formulae" not in chapter
    assert warnings == ["已移除1项缺少依据的数值字段", "已移除1条缺少依据的计算公式"]


def test_removed_unsupported_modules_become_planner_decision_cards_instead_of_a_retry_loop():
    chapter, warnings = sanitize_generated_optional_modules({
        "scope": "店铺等级与收益",
        "decisionCards": [{
            "id": "GDC-001", "question": "升级入口由哪里触发？", "status": "pending",
            "selectionMode": "single", "options": [{"id": "a", "label": "主界面"}, {"id": "b", "label": "店铺页"}],
        }],
        "parameterSchema": [{"name": "升级消耗"}, {"name": "每秒收益"}],
        "formulae": [{"name": "收益公式", "expression": "收益=等级×系数", "variables": [{"name": "等级"}]}],
    })

    assert "parameterSchema" not in chapter
    assert "formulae" not in chapter
    assert warnings == ["已移除2项缺少依据的数值字段", "已移除1条缺少依据的计算公式"]
    assert [card["id"] for card in chapter["decisionCards"]] == ["GDC-001", "GDC-002", "GDC-003"]
    assert "升级消耗、每秒收益" in chapter["decisionCards"][1]["question"]
    assert chapter["decisionCards"][1]["status"] == "pending"
    assert chapter["decisionCards"][1]["impacts"] == ["参数表", "玩法正文", "验收用例", "最终文档"]
    assert "收益公式" in chapter["decisionCards"][2]["question"]


def test_interface_description_stays_in_evidence_instead_of_gameplay_summary():
    chapter = {
        "scope": "升级选择",
        "mechanism": {"type": "custom"},
        "claims": [{
            "text": "屏幕中央弹出三个卡片按钮",
            "sourceType": "material",
            "sourceFrameIds": ["F0001"],
        }],
    }

    result = planner_sections(chapter)

    assert "弹出三个卡片" not in result["summary"]
    assert "弹出三个卡片" not in "".join(result["normalFlow"])


def test_generated_mixed_copy_routes_visual_clauses_out_of_gameplay_prose():
    chapter = enrich_gameplay_draft({
        "scope": "店铺升级",
        "mechanismType": "progression",
        "mechanism": {
            "type": "progression",
            "description": "玩家满足升级条件后扣除资源，底部红色图标显示升级结果。",
            "unlock": "玩家满足升级条件后进入升级流程。",
            "effect": "升级完成后更新店铺等级，底部播放升级动画。",
        },
        "claims": [],
        "attributeHeading": "底部属性面板",
        "attributeSections": [{
            "heading": "升级结果",
            "items": ["升级完成后更新店铺等级，底部红色图标播放升级动画。"],
        }],
        "acceptanceCases": [{
            "scene": "玩家满足升级条件。",
            "action": "玩家确认升级。",
            "expected": "系统更新店铺等级，底部播放升级动画。",
        }],
    })

    planner_text = str(chapter["plannerSections"])
    assert "满足升级条件" in planner_text
    assert "更新店铺等级" in planner_text
    assert "底部" not in planner_text
    assert "红色" not in planner_text
    assert "动画" not in planner_text
    assert any("底部红色图标" in item for item in chapter["presentationRules"])
    assert any("底部播放升级动画" in item for item in chapter["presentationRules"])
    assert chapter["plannerSections"]["attributeSections"][0]["items"] == ["升级完成后更新店铺等级。"]
    assert chapter["plannerSections"]["attributeHeading"] == ""
    assert chapter["plannerSections"]["acceptanceExamples"][0]["expected"] == "系统更新店铺等级。"
    assert language_quality_report({"chapters": [{"id": "GCH-001", **chapter}]})["passed"] is True


def test_generated_incomplete_flow_becomes_a_rule_fact_and_planner_decision_instead_of_failing_the_batch():
    chapter = enrich_gameplay_draft({
        "scope": "店铺升级",
        "mechanismType": "custom",
        "mechanism": {
            "type": "custom",
            "description": "升级后提高店铺收益。",
        },
        "claims": [{
            "text": "升级后提高店铺收益。",
            "sourceType": "material",
            "sourceFrameIds": ["F0001"],
        }],
        "sourceFrameIds": ["F0001"],
        "decisionCards": [],
    })

    sections = chapter["plannerSections"]
    assert sections["normalFlow"] == []
    assert "升级后提高店铺收益。" in sections["keyRules"]
    cards = [card for card in chapter["decisionCards"] if card["status"] == "pending"]
    assert len(cards) == 1
    assert "触发" in cards[0]["question"]
    assert "系统反馈" in cards[0]["question"]
    assert cards[0]["impacts"] == ["玩法流程", "验收用例", "图解", "最终文档"]


def test_generated_screen_caption_is_evidence_or_presentation_not_gameplay_prose():
    chapter = enrich_gameplay_draft({
        "scope": "店铺收益展示",
        "mechanismType": "custom",
        "mechanism": {"type": "custom", "description": "画面显示当前店铺等级与每秒收益。"},
        "claims": [],
        "acceptanceCases": [],
    })

    assert "画面显示" not in str(chapter["plannerSections"])
    assert chapter["presentationRules"] == ["画面显示当前店铺等级与每秒收益。"]


def test_generated_semantics_publish_only_evidence_backed_copy_and_route_gaps_to_decisions():
    chapter = sanitize_generated_semantics({
        "scope": "店铺等级与收益",
        "sourceFrameIds": ["F0001"],
        "mechanismType": "formula",
        "mechanism": {
            "type": "formula",
            "description": "收益还要乘以员工、设施和科技加成，满级后停止升级。",
        },
        "claims": [{
            "text": "底部显示当前等级2767级，每秒收益4.9万。",
            "sourceType": "material", "sourceFrameIds": ["F0001"],
        }, {
            "text": "升级按钮显示消耗14.25亿金币。",
            "sourceType": "material", "sourceFrameIds": ["F0001"],
        }],
        "parameters": {
            "当前等级": {"value": "2767", "source": "F0001"},
            "等级上限": {"value": "9999", "source": "F0001"},
        },
        "acceptanceCases": [{
            "scene": "金币足够", "action": "点击升级", "expected": "等级变2768且收益按新公式计算",
        }],
        "workedExamples": [{"result": "1级基础收入约422元"}],
        "configurationSources": [{"tableName": "Table_Shop_Level"}],
        "attributeSections": [{"heading": "服务器处理", "items": ["减少服务器交互次数"]}],
        "decisionCards": [],
    })

    assert chapter["mechanism"] == {"type": "formula"}
    assert list(chapter["parameters"]) == ["当前等级"]
    assert chapter["acceptanceCases"] == []
    assert "workedExamples" not in chapter
    assert "configurationSources" not in chapter
    assert "attributeSections" not in chapter
    assert chapter["evidenceSanitized"] is True
    assert any("操作" in card["question"] and card["status"] == "pending" for card in chapter["decisionCards"])

    enriched = enrich_gameplay_draft(chapter)
    published = str(enriched["plannerSections"])
    assert "员工" not in published
    assert "科技加成" not in published
    assert "满级" not in published
    assert "服务器" not in published
    assert "422" not in published
def test_planner_sections_preserve_attribute_prose_as_canonical_content():
    chapter = {
        "scope": "怪物属性",
        "mechanism": {"type": "custom", "description": "怪物按波次刷新并攻击载具。"},
        "attributeSections": [{
            "heading": "生存与防御",
            "items": [
                "生命值：归怪物实例持有，受到最终伤害后扣减；降至 0 时进入死亡流程。",
                "闪避：受击时先判定闪避；成功时免除本次伤害并累计闪避次数。",
            ],
        }],
    }

    result = planner_sections(chapter)

    assert result["attributeSections"] == chapter["attributeSections"]


def test_v2_does_not_generate_planner_sections_while_v1_adapter_remains_available():
    draft = {"scope": "攻击", "claims": [{"text": "武器攻击目标。"}]}
    assert "plannerSections" in enrich_gameplay_draft(draft)
    assert legacy_planner_sections_adapter({"plannerSections": {"keyRules": ["旧规则"]}})["keyRules"] == ["旧规则"]

    job = {"gameplayReviewModel": {"contentModelVersion": 2, "chapters": [{**draft, "plannerSections": {"keyRules": ["不得作为事实源"]}}]}}
    migrate_gameplay_rule_copy(job)
    assert "plannerSections" not in job["gameplayReviewModel"]["chapters"][0]
