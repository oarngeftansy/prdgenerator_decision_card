import pytest

from backend.gameplay_tables import auto_generate_tables, table_action


def model():
    return {"revision": 3, "reviewState": {}, "tables": [], "chapters": [{"id": "GCH-001", "scope": "载具等级", "confirmation": {"confirmed": True}, "parameterSchema": {"level": {"meaning": "载具等级", "type": "整数", "unit": "级", "default": 1, "source": "配置表"}}}]}


def test_tables_are_generated_as_a_separate_reviewable_artifact():
    generated = auto_generate_tables(model(), 3)
    assert generated["tableReview"]["status"] == "ready"
    assert generated["tables"][0]["title"] == "载具等级参数表"
    assert generated["tables"][0]["columns"] == ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"]
    assert generated["tables"][0]["status"] == "open"


def test_each_table_can_be_approved_regenerated_or_deleted():
    generated = auto_generate_tables(model(), 3)
    reviewed_rows = generated
    for row_index, row in enumerate(generated["tables"][0]["rows"]):
        reviewed_rows = table_action(
            reviewed_rows,
            "GTB-001",
            "confirm_row",
            reviewed_rows["revision"],
            '{"rowIndex": %d, "value": "%s"}' % (row_index, row[3]),
        )
    approved = table_action(reviewed_rows, "GTB-001", "approve", reviewed_rows["revision"])
    assert approved["tables"][0]["status"] == "reviewed"
    revised = table_action(approved, "GTB-001", "regenerate", approved["revision"], "补充上下限")
    assert revised["tables"][0]["revision"] == 2
    deleted = table_action(revised, "GTB-001", "delete", revised["revision"])
    assert deleted["tables"][0]["status"] == "deleted"


def test_no_parameter_or_formula_is_explicitly_recorded_as_no_table():
    source = model(); source["chapters"][0].pop("parameterSchema")
    generated = auto_generate_tables(source, 3)
    assert generated["tables"] == []
    assert generated["tableReview"]["noTableChapterIds"] == ["GCH-001"]


def test_inferred_formula_without_an_explicit_source_is_not_turned_into_a_table():
    source = model()
    source["chapters"][0].pop("parameterSchema")
    source["chapters"][0]["formulae"] = [{
        "meaning": "伤害计算框架", "expression": "最终伤害 = 基础伤害 × 修正",
        "evidenceLevel": "根据素材推断",
    }]

    generated = auto_generate_tables(source, 3)

    assert generated["tables"] == []


def test_list_parameter_schema_is_not_dropped_and_preserves_planner_fields():
    source = model()
    source["chapters"][0]["parameterSchema"] = [{
        "name": "生命", "category": "载具基础属性", "plannerMeaning": "载具可承受的伤害总量",
        "type": "整数", "unit": "点", "defaultValue": 4472, "deliverySource": "载具、战令",
    }]
    generated = auto_generate_tables(source, 3)
    table = next(item for item in generated["tables"] if item.get("kind") == "chapter_parameters")
    assert table["rows"][0] == ["生命", "整数（点）", "4472", "4472", "待确认", "确认"]
    assert table["rowDetails"][0] == {
        "field": "生命", "purpose": "载具可承受的伤害总量", "basis": "载具、战令",
        "source": "载具、战令", "formula": "",
    }


def test_system_attribute_catalog_and_calculation_legend_are_generated():
    source = model()
    source["chapters"][0]["parameterSchema"] = [{
        "name": "暴击率", "category": "载具二阶属性", "plannerMeaning": "触发暴击的概率",
        "type": "百分比", "unit": "%", "defaultValue": "5%", "deliverySource": "词条加成",
    }]
    source["chapters"][0]["formulae"] = [{
        "expression": "暴击伤害 = 基础伤害 × 暴击伤害倍率",
        "source": "参考文档明确说明",
    }]
    generated = auto_generate_tables(source, 3)
    catalog = next(item for item in generated["tables"] if item.get("kind") == "attribute_catalog")
    assert catalog["columns"] == ["属性分类", "属性", "属性说明", "投放来源"]
    assert catalog["rows"] == [["载具二阶属性", "暴击率", "触发暴击的概率", "词条加成"]]
    legend = next(item for item in generated["tables"] if item.get("kind") == "calculation_legend")
    assert legend["columns"] == ["图例", "表示内容", "当前素材中的对应项"]
    assert any(row[0] == "计算关系" and "暴击伤害" in row[2] for row in legend["rows"])


def test_template_only_parameters_do_not_create_fake_tables():
    source = model()
    source["chapters"][0]["parameterSchema"] = {
        "变化前生命值": {"meaning": "参与生命值状态管理计算的数值"},
        "本次承受伤害": {"meaning": "参与生命值状态管理计算的数值"},
    }

    generated = auto_generate_tables(source, 3)

    assert generated["tables"] == []
    assert generated["tableReview"]["noTableChapterIds"] == ["GCH-001"]


def test_names_alone_do_not_create_a_calculation_legend():
    source = model()
    source["chapters"][0]["parameterSchema"] = {
        "当前攻击属性": {"meaning": "参与伤害计算的数值"},
    }

    generated = auto_generate_tables(source, 3)

    assert not any(item.get("kind") == "calculation_legend" for item in generated["tables"])


def test_invalid_generated_catalog_is_retired_even_when_previously_reviewed():
    source = model()
    source["chapters"][0]["parameterSchema"] = {
        "变化前生命值": {"meaning": "参与生命值状态管理计算的数值"},
    }
    source["tables"] = [{
        "id": "GTB-099", "kind": "attribute_catalog", "title": "属性分类与投放来源",
        "chapterIds": ["GCH-001"], "columns": ["属性分类", "属性", "属性说明", "投放来源"],
        "rows": [["角色与载具控制", "变化前生命值", "参与生命值状态管理计算的数值", "伤害结算配置"]],
        "status": "reviewed", "revision": 1,
    }]

    generated = auto_generate_tables(source, 3)

    assert generated["tables"][0]["status"] == "deleted"


def test_need_to_combine_with_configuration_is_not_evidence_for_a_table():
    source = model()
    source["chapters"][0]["parameterSchema"] = [{
        "name": "当前攻击属性", "plannerMeaning": "本次攻击用于计算伤害的攻击值",
        "type": "整数", "unit": "点", "configurationSource": "需要结合实现配置",
        "evidenceLevel": "根据素材推断",
    }]

    generated = auto_generate_tables(source, 3)

    assert generated["tables"] == []


def test_table_cannot_be_approved_until_every_review_row_is_confirmed():
    source = model()
    source["tables"] = [{
        "id": "GTB-001", "kind": "chapter_parameters", "status": "open",
        "columns": ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"],
        "rows": [["生命", "整数", "100", "100", "已确认", "确认"], ["恢复", "整数", "5", "5", "待确认", "确认"]],
        "rowReviews": [{"rowIndex": 0, "value": "100", "confirmed": True}],
    }]

    with pytest.raises(ValueError, match="all table rows must be confirmed"):
        table_action(source, "GTB-001", "approve", source["revision"])
