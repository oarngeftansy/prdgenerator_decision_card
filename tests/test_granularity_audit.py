import pytest

from backend.granularity_audit import granularity_audit_report


def test_provenance_scope_must_use_a_known_cross_project_scope():
    report = granularity_audit_report(
        {
            "chapters": [
                {
                    "id": "C-SCOPE",
                    "scope": "建造位置",
                    "provenanceClaims": [
                        {
                            "text": "建筑只能放在空闲格子。",
                            "sourceType": "reference_document",
                            "sourceScope": "legacy_template",
                        }
                    ],
                }
            ]
        }
    )

    assert any(
        item["code"] == "GRANULARITY_CLAIM_SCOPE_INVALID"
        for item in report["findings"]
    )


def test_context_inference_requires_a_replayable_reasoning_chain():
    model = {"chapters": [{
        "id": "GCH-009", "scope": "奖励刷新",
        "provenanceClaims": [{"text": "刷新次数在下一局重置", "sourceType": "context_inference"}],
    }]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    assert report["findings"][0]["code"] == "GRANULARITY_INFERENCE_CHAIN_INCOMPLETE"
    assert "前提" in report["findings"][0]["message"]


def test_complete_inference_and_all_evidence_applicable_axes_pass():
    model = {"chapters": [{
        "id": "GCH-009", "scope": "奖励刷新",
        "granularityEvidence": {
            "executionSequence": {"sourceIds": ["VIDEO-01"]},
            "boundary": {"sourceIds": ["DOC-02"]},
            "lifecycle": {"sourceIds": ["DOC-03"]},
        },
        "executionSequence": ["清空暂存结果", "重新抽取", "展示新结果"],
        "boundaryRules": ["候选池为空时不触发"],
        "lifecycle": ["本局累计次数，关卡结束后重置"],
        "provenanceClaims": [{
            "text": "刷新从第一步重新执行", "sourceType": "context_inference",
            "inference": {"premises": ["刷新前后结果不同"], "steps": ["比较连续画面"],
                          "alternatives": [{"explanation": "只替换一个栏位", "excludedBy": "三个栏位均发生变化"}],
                          "confidence": "medium", "publicationAllowed": True,
                          "publicationReason": "连续画面能够重放完整状态变化"},
        }],
    }]}

    assert granularity_audit_report(model)["passed"]


def test_supported_interaction_feedback_and_runtime_responsibility_cannot_be_omitted():
    model = {"chapters": [{
        "id": "GCH-010", "scope": "关卡掉落",
        "granularityEvidence": {
            "interactionFeedback": {"sourceIds": ["DOC-10"], "sourceType": "reference_document"},
            "runtimeResponsibility": {"sourceIds": ["DOC-11"], "sourceType": "reference_document"},
        },
    }]}

    report = granularity_audit_report(model)

    assert {item["axis"] for item in report["findings"]} == {"interactionFeedback", "runtimeResponsibility"}


def test_screenshot_alone_cannot_authorize_formula_configuration_or_lifecycle_claims():
    model = {"chapters": [{
        "id": "GCH-011", "scope": "刷新按钮",
        "granularityEvidence": {
            "formula": {"sourceIds": ["F0001"], "sourceType": "screenshot_fact"},
            "configuration": {"sourceIds": ["F0001"], "sourceType": "screenshot_fact"},
            "lifecycle": {"sourceIds": ["F0001"], "sourceType": "screenshot_fact"},
        },
        "formulae": [{"expression": "刷新次数=1"}],
        "parameterSchema": [{"name": "刷新次数"}],
        "lifecycle": ["下一关重置"],
    }]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    assert sum(item["code"] == "GRANULARITY_EVIDENCE_SOURCE_UNSUPPORTED" for item in report["findings"]) == 3


def test_non_empty_axis_does_not_pass_when_evidence_backed_facts_are_missing():
    model = {"chapters": [{
        "id": "GCH-012", "scope": "奖励候选生成",
        "granularityEvidence": {
            "executionSequence": {
                "sourceIds": ["DOC-12"],
                "sourceType": "reference_document",
                "requiredFacts": ["排除本局已经出现的奖励", "按来源表优先级排序", "候选不足时只展示已有结果"],
            }
        },
        "executionSequence": ["系统筛选奖励并展示两个候选位"],
    }]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    chapter = report["chapters"][0]
    assert chapter["axes"]["executionSequence"]["status"] == "missing"
    assert chapter["axes"]["executionSequence"]["missingFacts"] == [
        "排除本局已经出现的奖励", "按来源表优先级排序", "候选不足时只展示已有结果"
    ]
    assert "候选不足时只展示已有结果" in report["findings"][0]["message"]


def test_axis_passes_only_when_all_evidence_backed_facts_are_present():
    model = {"chapters": [{
        "id": "GCH-013", "scope": "奖励候选生成",
        "granularityEvidence": {
            "executionSequence": {
                "sourceIds": ["DOC-13"],
                "sourceType": "reference_document",
                "requiredFacts": ["排除本局已经出现的奖励", "按来源表优先级排序"],
            }
        },
        "executionSequence": ["排除本局已经出现的奖励", "按来源表优先级排序并填充候选位"],
    }]}

    report = granularity_audit_report(model)

    assert report["passed"]
    axis = report["chapters"][0]["axes"]["executionSequence"]
    assert axis["status"] == "satisfied"
    assert axis["coveredFacts"] == ["排除本局已经出现的奖励", "按来源表优先级排序"]


def test_unsupported_source_never_counts_as_axis_coverage():
    model = {"chapters": [{
        "id": "GCH-014", "scope": "刷新按钮",
        "granularityEvidence": {
            "lifecycle": {"sourceIds": ["F0001"], "sourceType": "screenshot_fact", "requiredFacts": ["下一关重置"]}
        },
        "lifecycle": ["下一关重置"],
    }]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    assert report["chapters"][0]["axes"]["lifecycle"]["status"] == "unsupported"


def test_v2_audit_checks_published_carrier_instead_of_source_structure():
    model = {"granularityAuditVersion": 2, "chapters": [{
        "id": "GCH-015", "scope": "奖励候选",
        "granularityEvidence": {
            "executionSequence": {
                "sourceIds": ["DOC-15"],
                "requiredFacts": ["排除未解锁奖励", "按优先级填充候选位"],
            }
        },
        "executionSequence": ["排除未解锁奖励", "按优先级填充候选位"],
        "plannerSections": {"summary": "系统生成奖励候选。", "normalFlow": []},
    }]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    assert report["chapters"][0]["axes"]["executionSequence"]["missingFacts"] == [
        "排除未解锁奖励", "按优先级填充候选位"
    ]


def test_v2_audit_passes_after_facts_are_written_to_the_published_carrier():
    model = {"granularityAuditVersion": 2, "chapters": [{
        "id": "GCH-016", "scope": "奖励候选",
        "granularityEvidence": {
            "executionSequence": {
                "sourceIds": ["DOC-16"],
                "requiredFacts": ["排除未解锁奖励", "按优先级填充候选位"],
            }
        },
        "executionSequence": ["排除未解锁奖励", "按优先级填充候选位"],
        "plannerSections": {"normalFlow": ["排除未解锁奖励", "按优先级填充候选位"]},
    }]}

    assert granularity_audit_report(model)["passed"]


def test_configuration_axis_requires_the_declared_reviewed_table_columns_not_only_prose():
    model = {"granularityAuditVersion": 2, "chapters": [{
        "id": "CFG-1", "scope": "挑战券消耗",
        "granularityEvidence": {"configuration": {
            "sourceIds": ["TABLE-1"], "sourceType": "configuration_table",
            "requiredFacts": ["确认进入时扣除", "挑战失败时返还"],
            "requiredColumns": ["字段", "单位", "默认值", "扣除时机", "失败处理", "配置来源"],
        }},
        "plannerSections": {"summary": "确认进入时扣除挑战券，挑战失败时返还。"},
    }], "tables": [{"id": "TABLE-1", "chapterIds": ["CFG-1"], "status": "reviewed", "rows": [
        ["字段", "单位"], ["挑战券消耗", "张"],
    ]}]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    finding = next(item for item in report["findings"] if item["code"] == "GRANULARITY_CONFIGURATION_COLUMNS_MISSING")
    assert "默认值" in finding["message"]
    assert finding["remediation"]["carrier"] == "配置表"
    assert "重新检查配置字段" in finding["remediation"]["retest"]


def test_every_granularity_failure_has_an_actionable_remediation_path():
    model = {"chapters": [{
        "id": "GAP-1", "scope": "奖励筛选",
        "granularityEvidence": {"executionSequence": {
            "sourceIds": ["DOC-X"], "requiredFacts": ["排除未解锁奖励"],
        }},
    }]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    for finding in report["findings"]:
        assert set(finding["remediation"]) == {"basis", "action", "carrier", "impact", "retest"}
        assert all(finding["remediation"].values())


@pytest.mark.parametrize("columns", [
    ["属性", "说明", "类型与单位", "配置或计算", "限制条件"],
    ["字段", "策划含义", "当前值与范围", "类型与单位", "配置来源"],
    ["名称", "填写格式", "单位", "默认值"],
])
def test_generic_field_audit_table_is_rejected_for_execution_prd(columns):
    model = {
        "granularityAuditVersion": 4,
        "tables": [{
            "id": "VEHICLE", "title": "载具属性", "status": "reviewed", "chapterIds": ["VEH-1"],
            "columns": columns,
            "rows": [["攻击力", "基础攻击", "数值·点", "配置", ">=0"]],
        }],
    }

    report = granularity_audit_report(model)

    assert not report["passed"]
    finding = next(item for item in report["findings"] if item["code"] == "GRANULARITY_GENERIC_CONFIGURATION_TABLE")
    assert "不能直接用于策划查配" in finding["message"]
    assert "按机制拆成" in finding["remediation"]["action"]


def test_parameter_table_cannot_replace_required_attribute_prose():
    model = {"granularityAuditVersion": 4, "chapters": [{
        "id": "MON-1", "scope": "怪物作战",
        "granularityEvidence": {"attributeNarrative": {
            "sourceIds": ["DOC-M"], "sourceType": "reference_document",
            "requiredFacts": ["生命值", "闪避"],
        }},
        "parameterSchema": [
            {"name": "生命值", "plannerMeaning": "当前生命值"},
            {"name": "闪避", "plannerMeaning": "万分比"},
        ],
        "plannerSections": {"summary": "怪物按波次刷新。"},
    }]}

    report = granularity_audit_report(model)

    assert not report["passed"]
    finding = next(item for item in report["findings"] if item["axis"] == "attributeNarrative")
    assert finding["code"] == "GRANULARITY_ATTRIBUTENARRATIVE_MISSING"
    assert "正文" in finding["message"]


def test_v5_detail_audit_never_marks_every_axis_not_applicable_when_chapter_has_evidence():
    model = {
        "granularityAuditVersion": 5,
        "reviewState": {"structurePhase": "detailed"},
        "chapters": [{
            "id": "GCH-EVIDENCE", "scope": "店铺升级", "sourceFrameIds": ["F0001"],
            "claims": [{"text": "升级按钮显示消耗100金币", "sourceType": "material", "sourceFrameIds": ["F0001"]}],
            "plannerSections": {"summary": "当前素材确认了升级入口与可见消耗。"},
        }],
    }

    report = granularity_audit_report(model)

    assert report["chapters"][0]["applicable"]
    assert "overviewTraceability" in report["chapters"][0]["applicable"]
    assert not all(
        axis["status"] == "not_applicable"
        for axis in report["chapters"][0]["axes"].values()
    )
