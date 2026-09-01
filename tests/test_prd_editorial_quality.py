from backend import feishu_language_quality as quality


def model_with_rules(*rules):
    return {
        "chapters": [
            {
                "id": "C1",
                "scope": "载具",
                "plannerSections": {"normalFlow": list(rules)},
            }
        ]
    }


def finding_codes(model):
    return {item["code"] for item in quality.language_quality_report(model)["findings"]}


def test_logic_and_presentation_in_one_rule_is_rejected():
    codes = finding_codes(model_with_rules("载具沿道路自动前进，同时在载具上方显示生命条。"))

    assert "LANGUAGE_LOGIC_PRESENTATION_MIXED" in codes


def test_pure_visual_layout_rule_is_routed_out_of_gameplay_prose():
    codes = finding_codes(model_with_rules("载具上方常驻显示红色生命条。"))

    assert "LANGUAGE_PRESENTATION_IN_PROSE" in codes


def test_semantic_feedback_remains_valid_gameplay_copy():
    codes = finding_codes(model_with_rules("敌人命中载具后扣除生命值，并刷新当前生命值反馈。"))

    assert "LANGUAGE_PRESENTATION_IN_PROSE" not in codes
    assert "LANGUAGE_LOGIC_PRESENTATION_MIXED" not in codes


def test_empty_common_knowledge_is_rejected_but_state_transition_is_kept():
    empty_codes = finding_codes(model_with_rules("玩家可以通过操作控制载具。"))
    specific_codes = finding_codes(
        model_with_rules("怪物进入攻击距离后停止移动并开始攻击；目标离开攻击范围后恢复追击。")
    )

    assert "LANGUAGE_COMMON_KNOWLEDGE" in empty_codes
    assert "LANGUAGE_COMMON_KNOWLEDGE" not in specific_codes


def test_three_reader_report_requires_design_intent_implementation_and_test_boundary():
    assert hasattr(quality, "three_reader_report")
    report = quality.three_reader_report(
        model_with_rules("达到升级条件后生成三个强化候选；玩家确认一项后立即写入本局状态。")
    )

    assert report["planner"] is True
    assert report["programmer"] is True
    assert report["tester"] is False
    assert report["missing"] == ["test_boundary"]


def test_handwritten_comparison_reports_supported_missing_roles_and_excess_copy():
    assert hasattr(quality, "handwritten_gap_report")
    report = quality.handwritten_gap_report(
        handwritten_roles={"execution_sequence", "boundary", "lifecycle", "attribute_prose"},
        generated_roles={"execution_sequence", "attribute_prose", "visual_description"},
        supported_roles={"execution_sequence", "boundary", "lifecycle", "attribute_prose"},
    )

    assert report["missing"] == ["boundary", "lifecycle"]
    assert report["excess"] == ["visual_description"]
    assert report["passed"] is False


def test_handwritten_delta_matrix_requires_all_dimensions_sources_and_remediation():
    assert hasattr(quality, "handwritten_delta_matrix")
    complete = {
        dimension: {
            "handwritten": [f"人工参考中的{dimension}"],
            "current": [f"当前输出中的{dimension}"],
            "missing": [],
            "excess": [],
            "remediation": [],
            "handwritten_refs": ["H2:10-20"],
            "current_refs": ["gameplayReviewModel.chapters[0]"],
        }
        for dimension in quality.HANDWRITTEN_DELTA_DIMENSIONS
    }
    complete["配置映射"]["missing"] = ["项目字段读取时点"]
    complete["配置映射"]["remediation"] = ["写入载具章就近配置映射"]

    report = quality.handwritten_delta_matrix(complete)

    assert len(report["rows"]) == 9
    assert report["passed"] is False
    assert report["blockingDimensions"] == ["配置映射"]
    assert report["rows"][3]["手写文档有"]
    assert report["rows"][3]["当前输出有"]
    assert report["rows"][3]["改善方式"] == ["写入载具章就近配置映射"]


def test_handwritten_delta_matrix_rejects_untraced_or_unremediated_findings():
    report = quality.handwritten_delta_matrix({
        "机制拆分": {
            "handwritten": ["人工有独立关卡章"],
            "current": ["当前把阶段写进怪物章"],
            "missing": ["关卡章"],
            "excess": ["怪物章中的阶段切换"],
            "remediation": [],
            "handwritten_refs": [],
            "current_refs": [],
        }
    })

    assert report["passed"] is False
    assert "机制拆分" in report["untracedDimensions"]
    assert "机制拆分" in report["unremediatedDimensions"]
    assert set(report["missingDimensions"]) == set(quality.HANDWRITTEN_DELTA_DIMENSIONS) - {"机制拆分"}
