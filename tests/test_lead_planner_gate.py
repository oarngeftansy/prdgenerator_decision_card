from pathlib import Path

from backend.lead_planner_gate import lead_planner_output_audit, lead_planner_preflight


def test_generation_preflight_requires_evidence_and_confirmed_detail_structure():
    assert "LEAD_PLANNER_INPUT_HAS_NO_EVIDENCE" in lead_planner_preflight({}, "structure")
    errors = lead_planner_preflight(
        {"frames": [{"id": "F0001"}]},
        "details",
        {"directory": {"status": "draft"}, "chapters": []},
    )
    assert "LEAD_PLANNER_DIRECTORY_NOT_CONFIRMED" in errors
    assert "LEAD_PLANNER_STRUCTURE_EMPTY" in errors


def test_lead_planner_audit_rejects_screen_captions_internal_language_and_shallow_rules():
    model = {
        "systems": [{"name": "战斗"}],
        "directory": {
            "understanding": {"summary": "画面显示载具前进。"},
            "entries": [{"id": "GDE-001", "summary": "载具移动机制的玩法规则。"}],
        },
        "chapters": [
            {
                "id": "GCH-001",
                "plannerSummary": "component pending",
                "plannerSections": {"summary": "画面显示绿色血条。"},
            }
        ],
    }
    errors = lead_planner_output_audit(model, "structure")
    assert any("SCREEN_CAPTION_AS_RULE" in item for item in errors)
    assert any("INTERNAL_LANGUAGE" in item for item in errors)
    assert any("RULE_TOO_SHALLOW" in item for item in errors)


def test_lead_planner_audit_accepts_gameplay_abstraction():
    movement_rule = "载具沿预设路线自动前进；玩家可控制载具横向移动，以规避敌人或对准攻击目标。"
    model = {
        "systems": [{"name": "核心战斗系统"}],
        "directory": {
            "understanding": {"summary": "载具沿路线自动前进，玩家调整位置并持续对抗敌人。"},
            "entries": [{"id": "GDE-001", "summary": movement_rule}],
        },
        "chapters": [
            {
                "id": "GCH-001",
                "plannerSummary": movement_rule,
                "plannerSections": {
                    "summary": movement_rule,
                    "normalFlow": ["玩家调整位置并持续推进。"],
                    "keyRules": ["载具只能在可移动范围内调整横向位置。"],
                    "acceptanceExamples": [{"scene": "正常推进", "expected": "载具继续前进"}],
                },
            }
        ],
    }
    assert lead_planner_output_audit(model, "details") == []


def test_lead_planner_audit_allows_ui_terms_when_they_define_player_and_system_behavior():
    model = {
        "systems": [{"name": "局内成长"}],
        "directory": {
            "understanding": {"summary": "玩家升级后选择一项强化并返回战斗。"},
            "entries": [{"id": "GDE-001", "summary": "升级后暂停战斗并打开强化选择界面。"}],
        },
        "chapters": [{
            "id": "GCH-001",
            "plannerSummary": "升级后暂停战斗并打开强化选择界面。",
            "plannerSections": {
                "summary": "玩家从三项强化中确认一项。",
                "normalFlow": ["玩家点击候选卡片后，系统应用该项效果并关闭弹窗。"],
                "keyRules": ["刷新按钮只替换候选，不会确认强化。"],
                "specialCases": ["刷新次数不足时按钮不可用。"],
            },
        }],
    }

    assert lead_planner_output_audit(model, "details") == []


def test_lead_planner_audit_rejects_a_confirmed_chapter_that_only_repeats_one_claim():
    sentence = "玩家选择一项强化，使本局能力发生变化。"
    model = {
        "systems": [{"name": "成长系统"}],
        "directory": {"understanding": {"summary": sentence}, "entries": [{"id": "GDE-001", "summary": sentence}]},
        "chapters": [{"id": "GCH-001", "plannerSummary": sentence, "plannerSections": {"summary": sentence, "normalFlow": [sentence], "keyRules": [], "specialCases": [], "acceptanceExamples": []}}],
    }
    assert any("RULE_DEPTH_INSUFFICIENT" in item for item in lead_planner_output_audit(model, "details"))


def test_review_entry_accepts_a_grounded_rule_with_pending_decision_but_delivery_stays_strict():
    sentence = "玩家确认升级后，系统扣除升级资源并提升店铺等级。"
    model = {
        "systems": [{"name": "店铺成长"}],
        "directory": {"understanding": {"summary": sentence}, "entries": []},
        "chapters": [{
            "id": "GCH-001",
            "scope": "店铺升级",
            "plannerSections": {
                "summary": sentence,
                "normalFlow": [sentence],
                "keyRules": [],
                "specialCases": [],
                "acceptanceExamples": [],
            },
            "decisionCards": [{
                "id": "GDC-001",
                "status": "pending",
                "question": "截图未提供升级消耗的可靠数值，该配置项如何处理？",
                "options": [
                    {"id": "configure", "label": "由策划补齐"},
                    {"id": "omit", "label": "不配置该数值"},
                ],
            }],
        }],
    }

    strict_errors = lead_planner_output_audit(model, "details")
    review_errors = lead_planner_output_audit(model, "details", allow_pending_decisions=True)

    assert any("RULE_DEPTH_INSUFFICIENT" in item for item in strict_errors)
    assert not any("RULE_DEPTH_INSUFFICIENT" in item for item in review_errors)


def test_lead_planner_audit_includes_language_and_carrier_quality_findings():
    model = {
        "systems": [{"name": "战斗"}],
        "directory": {"understanding": {"summary": "玩家控制载具前进。"}, "entries": []},
        "chapters": [{
            "id": "C1", "scope": "载具移动", "bodyText": "移动速度为每秒5米。",
            "plannerSections": {"summary": "本节主要介绍载具移动机制。", "normalFlow": ["玩家可以进行相关操作。"], "keyRules": ["通过状态隔离完成候选刷新。"], "specialCases": ["超出范围时停在边界。"]},
            "publishedHeadings": ["正常怎么玩"], "tables": [{"rows": [["移动速度", "每秒5米"]]}],
        }],
    }

    errors = lead_planner_output_audit(model, "details")

    assert any("LANGUAGE_FILLER" in item for item in errors)
    assert any("LANGUAGE_FIXED_HEADING" in item for item in errors)
    assert any("LANGUAGE_ABSTRACT_TERM" in item for item in errors)
    assert any("LANGUAGE_CARRIER_DUPLICATION" in item for item in errors)


def test_every_gameplay_generation_prompt_requires_a_lead_planner_self_check():
    source = (Path(__file__).resolve().parents[1] / "backend" / "gameplay_analysis.py").read_text(encoding="utf-8")
    assert "lead game designer" in source
    assert "主策视角静默自检" in source
    assert "不得让所有章节机械套用同一组模块" in source
    assert "简单机制使用连贯自然正文" in source


def test_detailed_generation_uses_review_entry_audit_for_pending_decisions():
    source = (Path(__file__).resolve().parents[1] / "backend" / "gameplay_analysis.py").read_text(encoding="utf-8")
    assert 'lead_planner_output_audit(result, "details", allow_pending_decisions=True)' in source
