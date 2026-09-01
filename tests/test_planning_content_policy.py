from backend.planning_content_policy import carrier_policy_report, normalize_delivery_carriers


def test_same_rule_has_one_primary_published_carrier():
    sentence = "敌人进入攻击距离后停止移动并开始攻击。"
    model = {
        "chapters": [
            {
                "id": "C1",
                "plannerSections": {
                    "normalFlow": [sentence],
                    "keyRules": [],
                    "specialCases": [],
                },
                "objectStates": [sentence],
                "runtimeResponsibilities": [sentence],
                "presentationRules": [sentence],
            }
        ]
    }

    normalized = normalize_delivery_carriers(model)
    chapter = normalized["chapters"][0]

    assert chapter["plannerSections"]["normalFlow"] == [sentence]
    assert chapter["objectStates"] == []
    assert chapter["runtimeResponsibilities"] == []
    assert chapter["presentationRules"] == []
    assert len(chapter["carrierRefs"]) == 3
    assert carrier_policy_report(normalized)["passed"] is True


def test_distinct_runtime_responsibility_is_preserved():
    model = {
        "chapters": [
            {
                "id": "C2",
                "plannerSections": {"normalFlow": ["波次开始时生成怪物。"]},
                "runtimeResponsibilities": ["服务端在波次开始时生成本波怪物列表。"],
            }
        ]
    }

    chapter = normalize_delivery_carriers(model)["chapters"][0]

    assert chapter["runtimeResponsibilities"] == ["服务端在波次开始时生成本波怪物列表。"]


def test_nested_planner_facts_are_compared_as_text_not_dict_repr():
    sentence = "攻击力用于换算武器伤害，不直接等于最终伤害。"
    model = {
        "chapters": [
            {
                "id": "C3",
                "plannerSections": {
                    "attributeSections": [
                        {"heading": "伤害换算", "items": [sentence]},
                    ]
                },
                "objectStates": [sentence],
            }
        ]
    }

    chapter = normalize_delivery_carriers(model)["chapters"][0]

    assert chapter["objectStates"] == []
    assert chapter["carrierRefs"][0]["field"] == "objectStates"


def test_policy_report_rejects_unresolved_primary_fact_duplication():
    sentence = "确认强化后立即应用效果并恢复战斗。"
    report = carrier_policy_report(
        {
            "chapters": [
                {
                    "id": "C4",
                    "plannerSections": {"normalFlow": [sentence]},
                    "presentationRules": [sentence],
                }
            ]
        }
    )

    assert report["passed"] is False
    assert report["findings"] == [
        {
            "chapterId": "C4",
            "field": "presentationRules",
            "code": "CARRIER_DUPLICATE_PRIMARY_FACT",
            "action": "保留一个正文主载体，其他字段改为 factId 引用。",
        }
    ]
