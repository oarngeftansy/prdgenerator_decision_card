from backend.feishu_language_quality import language_quality_report


def test_rejects_ai_composite_title():
    model = {
        "chapters": [
            {
                "id": "C-TITLE",
                "scope": "命中、反馈与伤害归集",
                "plannerSections": {"summary": "武器命中后造成伤害。"},
            }
        ]
    }

    codes = {item["code"] for item in language_quality_report(model)["findings"]}

    assert "LANGUAGE_TEMPLATE_TITLE" in codes


def test_rejects_audit_voice_in_delivery_copy():
    model = {
        "chapters": [
            {
                "id": "C-AUDIT",
                "scope": "武器",
                "plannerSections": {
                    "keyRules": ["当前项目应逐项保留奖励，而不能概括处理。"]
                },
            }
        ]
    }

    codes = {item["code"] for item in language_quality_report(model)["findings"]}

    assert "LANGUAGE_AUDIT_VOICE" in codes


def test_accepts_business_object_titles():
    model = {
        "chapters": [
            {
                "id": "C-BUSINESS",
                "scope": "武器栏",
                "plannerSections": {
                    "summary": "玩家获得新武器后，将武器写入一个空栏位。"
                },
            }
        ]
    }

    assert language_quality_report(model)["passed"] is True


def test_rejects_repeated_ai_sentence_cadence():
    model = {
        "chapters": [
            {
                "id": "C-CADENCE",
                "scope": "商店刷新",
                "plannerSections": {
                    "normalFlow": [
                        "玩家点击刷新并消耗一次刷新次数。",
                        "玩家查看商品并选择一个商品。",
                        "玩家确认购买并获得对应道具。",
                    ]
                },
            }
        ]
    }

    codes = {item["code"] for item in language_quality_report(model)["findings"]}

    assert "LANGUAGE_REPEATED_CADENCE" in codes


def test_rejects_empty_editorial_abstraction():
    model = {
        "chapters": [
            {
                "id": "C-EMPTY",
                "scope": "关卡",
                "plannerSections": {"summary": "本部分用于承接后续玩法内容。"},
            }
        ]
    }

    codes = {item["code"] for item in language_quality_report(model)["findings"]}

    assert "LANGUAGE_EMPTY_ABSTRACTION" in codes


def test_language_audit_rejects_filler_fixed_headings_abstract_terms_and_repeated_carrier_copy():
    chapter = {
        "id": "C1", "scope": "载具移动",
        "plannerSections": {
            "summary": "本节主要介绍载具移动机制，该机制具有重要作用。",
            "normalFlow": ["玩家可以进行相关操作。"],
            "keyRules": ["通过状态隔离完成候选刷新。"],
        },
        "publishedHeadings": ["正常怎么玩", "关键规则", "特殊情况"],
        "tables": [{"rows": [["移动速度", "每秒5米"]]}],
        "bodyText": "移动速度为每秒5米。",
    }

    report = language_quality_report({"chapters": [chapter]})

    codes = {item["code"] for item in report["findings"]}
    assert {"LANGUAGE_FILLER", "LANGUAGE_FIXED_HEADING", "LANGUAGE_ABSTRACT_TERM", "LANGUAGE_CARRIER_DUPLICATION"} <= codes


def test_language_audit_accepts_concise_condition_action_result_copy_with_distinct_carriers():
    chapter = {
        "id": "C2", "scope": "载具移动",
        "plannerSections": {
            "summary": "进入战斗后，载具沿路线自动前进；玩家拖动载具时，只改变横向位置。",
            "specialCases": ["拖动超出可移动范围时，载具停在范围边界。"],
        },
        "tables": [{"rows": [["移动速度", "配置在载具表"]]}],
        "bodyText": "进入战斗后，载具沿路线自动前进；玩家拖动载具时，只改变横向位置。",
    }

    assert language_quality_report({"chapters": [chapter]})["passed"]


def test_internal_process_terms_are_reported_with_the_actual_term():
    model = {"chapters": [{
        "id": "C3", "scope": "奖励选择",
        "plannerSections": {"summary": "系统完成状态隔离后形成规则闭环，并在本节收口。"},
    }]}

    report = language_quality_report(model)

    assert not report["passed"]
    messages = "\n".join(item["message"] for item in report["findings"])
    assert "状态隔离" in messages
    assert "闭环" in messages
    assert "收口" in messages


def test_top_level_reviewed_table_is_compared_with_its_chapter_body():
    model = {
        "chapters": [{
            "id": "C4", "scope": "挑战消耗",
            "plannerSections": {"summary": "挑战失败返还挑战券。"},
        }],
        "tables": [{
            "id": "T4", "chapterIds": ["C4"], "status": "reviewed",
            "rows": [["失败处理", "挑战失败返还挑战券"]],
        }],
    }

    report = language_quality_report(model)

    assert not report["passed"]
    finding = next(item for item in report["findings"] if item["code"] == "LANGUAGE_CARRIER_DUPLICATION")
    assert "挑战失败返还挑战券" in finding["message"]


def test_short_ascii_enum_in_table_is_not_mistaken_for_duplicated_prose():
    model = {
        "chapters": [{
            "id": "C4B", "scope": "首领战",
            "plannerSections": {"summary": "进入 BOSS 波次后显示首领生命条。"},
        }],
        "tables": [{
            "id": "T4B", "chapterIds": ["C4B"], "status": "reviewed",
            "rows": [["刷怪点类型", "BOSS"]],
        }],
    }

    assert language_quality_report(model)["passed"]


def test_language_failure_includes_concrete_edit_and_retest_path():
    model = {"chapters": [{
        "id": "C5", "scope": "奖励规则",
        "plannerSections": {"summary": "本节主要介绍奖励机制，并通过状态隔离形成闭环。"},
    }]}

    report = language_quality_report(model)

    assert not report["passed"]
    for finding in report["findings"]:
        remediation = finding["remediation"]
        assert remediation["action"]
        assert remediation["carrier"] == "玩法正文"
        assert "重新运行语言检查" in remediation["retest"]


def test_unpublished_diagram_editor_note_does_not_block_formal_planner_copy():
    model = {
        "chapters": [{"id": "C6", "scope": "三选一强化", "plannerSections": {"summary": "升级后暂停战斗并展示三项候选。"}}],
        "diagrams": [{"chapterIds": ["C6"], "placement": {"followUp": "流程图只确定暂停、选择和恢复战斗；候选池仍由决策卡确认。"}}],
    }

    report = language_quality_report(model)

    assert report["passed"]


def test_unpublished_ai_navigation_note_does_not_block_formal_planner_copy():
    model = {
        "chapters": [{"id": "C6B", "scope": "载具", "plannerSections": {"summary": "载具沿道路推进。"}}],
        "diagrams": [{"chapterIds": ["C6B"], "placement": {
            "followUp": "图中的升级由后续章节展开；本节继续说明载具边界。",
        }}],
    }

    report = language_quality_report(model)

    assert report["passed"]


def test_attribute_copy_cannot_publish_planner_decision_state():
    model = {"chapters": [{
        "id": "C7", "scope": "载具",
        "plannerSections": {"attributeSections": [{
            "heading": "承伤与武器换算",
            "items": ["固定减伤参与承伤计算；具体计算位置需由策划决策后再固化。"],
        }]},
    }]}

    report = language_quality_report(model)

    assert not report["passed"]
    assert any(item["code"] == "LANGUAGE_REVIEW_META" for item in report["findings"])
