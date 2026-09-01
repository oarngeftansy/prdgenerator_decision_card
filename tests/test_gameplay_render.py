from copy import deepcopy
from pathlib import Path

import pytest

from backend.feishu_render import render_feishu_document
from backend.gameplay_render import render_gameplay_document_sections, render_gameplay_sections
from backend.gameplay_directory import ensure_directory
from backend.review_preview import build_final_review_preview
from tests.review_fixtures import make_confirmed_job


def test_renderer_normalizes_delivery_carriers_at_boundary(monkeypatch):
    import backend.gameplay_render as gameplay_render

    called = []

    def normalize(model):
        called.append(model)
        return model

    monkeypatch.setattr(gameplay_render, "normalize_delivery_carriers", normalize)

    gameplay_render.render_gameplay_document_sections(complete_job())

    assert len(called) == 1


def test_structured_publication_projection_is_final_authority_over_planner_sections():
    job = complete_job()
    job["gameplayReviewModel"]["chapters"][0]["plannerSections"]["normalFlow"] = ["不应进入最终文档的缓存文本。"]
    job["gameplayReviewModel"]["ruleIntelligenceProjection"] = {
        "authorityMode": "structured_rules",
        "publication": {"chapters": [{
            "chapterId": "PC1", "title": "攻击规则", "system": "战斗", "object": "武器",
            "publicationEligibility": "eligible", "closureStatus": "complete", "gaps": [],
            "ruleDefinitions": [{"ruleId": "R1", "behavior": "武器每1秒执行一次攻击。", "intent": "AttackInterval"}],
            "references": [],
        }]},
        "guard": {"passed": True, "blockedRuleIds": []},
    }

    xml = render_gameplay_document_sections(job).xml

    assert "武器每1秒执行一次攻击" in xml
    assert "不应进入最终文档的缓存文本" not in xml


def test_inline_figure_is_placed_with_the_rule_it_explains():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSections"]["normalFlow"] = [
        {"id": "R1", "text": "玩家确认强化。"},
        {"id": "R2", "text": "系统恢复战斗。"},
    ]
    chapter["inlineFigures"] = [
        {
            "frameId": "F0001",
            "afterRuleId": "R1",
            "caption": "强化选择界面",
        }
    ]

    xml = render_gameplay_document_sections(job).xml

    assert xml.index("玩家确认强化") < xml.index('name="inline-figure-F0001"') < xml.index("系统恢复战斗")


def test_single_short_attribute_group_does_not_create_a_decorative_heading():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSections"]["attributeSections"] = [
        {"heading": "基础属性", "items": ["生命值归零时挑战失败。"]}
    ]

    xml = render_gameplay_document_sections(job).xml

    assert "生命值归零时挑战失败" in xml
    assert "<h4>基础属性</h4>" not in xml


def _parameter(value: str) -> dict:
    return {"value": value, "type": "text", "unit": "n/a", "range": "defined", "source": "planner"}


def complete_job() -> dict:
    job = make_confirmed_job()
    job["status"] = "completed"
    job["plan"] = "ready"
    job["planningModel"] = {
        "standard": "GVE16", "mode": "interaction",
        "project": {"name": "Demo", "scope": "按截图还原交互与玩法"},
        "scenes": [], "events": [], "designHandoff": {"flowEdges": []},
    }
    revision = job["reviewModel"]["revision"]
    job["gameplayReviewModel"] = {
        "schemaVersion": "1.0", "standard": "GVE16", "revision": 3,
        "jobId": job["id"], "interactionRevision": revision,
        "evidenceAnchors": [{"id": "GEV-001", "frameId": "F0001"}],
        "chapters": [{
            "id": "GCH-001", "scope": "局内循环", "claims": [{
                "id": "GCL-001", "text": "玩家完成选择后进入战斗",
                "sourceType": "material", "sourceFrameIds": ["F0001"],
            }],
            "plannerSummary": "玩家完成一次选择后进入战斗，战斗结果推动下一轮循环。",
            "plannerSections": {
                "summary": "玩家通过连续战斗推进关卡并完成本次挑战。",
                "normalFlow": ["玩家完成一次选择后进入战斗。", "战斗结束后进入下一轮或结算。"],
                "keyRules": ["每轮选择会改变后续战斗结果。"],
                "specialCases": ["挑战失败时进入失败结算。"],
                "acceptanceExamples": [{"scene": "完成战斗", "action": "结束当前轮次", "expected": "进入下一轮或结算"}],
            },
            "mechanism": {"type": "core_loop"},
            "parameters": {key: _parameter(key) for key in (
                "playerGoal", "trigger", "phaseOrder", "completion", "failure", "reset"
            )},
            "dependencies": [],
            "acceptanceCases": [{"id": "GAC-001", "title": "正常完成", "expected": "进入结算"}],
            "decisionCards": [],
            "unknowns": [{"text": "失败后的保留规则", "blocking": False}],
            "sourceFrameIds": ["F0001"], "status": "approved",
            "confirmation": {"confirmed": True, "revision": 3, "decision": "approved"},
        }],
        "contextWindows": [],
        "diagrams": [{
            "id": "GDI-001", "type": "state_flow", "chapterIds": ["GCH-001"],
            "revision": 1, "status": "reviewed", "freshness": "current", "optional": True,
            "interactionRevision": revision, "svg": "<svg><text>循环图示</text></svg>",
        }],
        "reviewState": {"status": "chapter_review", "findings": [{
            "id": "GFN-001", "severity": "warning", "status": "open", "text": "数值待配置"
        }]},
        "editHistory": [],
    }
    ensure_directory(job["gameplayReviewModel"])["entries"][0]["sectionTitle"] = "战斗与关卡"
    return job


def test_gameplay_sections_render_confirmed_content_without_evidence_images_or_internal_ids():
    xml = render_gameplay_sections(complete_job())

    assert "局内循环" in xml
    assert "玩家完成一次选择后进入战斗" in xml
    assert all(title not in xml for title in ("一句话玩法", "正常怎么玩", "关键规则", "特殊情况", "检查示例"))
    assert "玩家通过连续战斗推进关卡并完成本次挑战" in xml
    assert "素材依据" not in xml and "规则说明" not in xml
    rendered = render_gameplay_document_sections(complete_job())
    assert any("循环图示" in svg for _, svg in rendered.embedded_whiteboards)
    assert "玩法概述" in xml
    assert xml.index("战斗与关卡") < xml.index("局内循环")
    assert "配置与参数" not in xml
    assert "填写格式" not in xml and "数值单位" not in xml and "配置位置" not in xml
    assert all(term not in xml for term in (">text<", ">number<", ">n/a<", ">defined<", ">planner<"))
    assert "待确认事项" in xml
    assert "F0001" not in xml
    assert "GEV-" not in xml and "SCN-" not in xml and "EVT-" not in xml
    assert "<img" not in xml
    assert "前置状态" not in xml and "重置方式" not in xml


def test_sparse_chapter_uses_natural_copy_instead_of_repeating_template_headings():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSections"] = {
        "summary": "玩家横向移动载具规避敌人并持续推进。",
        "normalFlow": ["玩家拖动摇杆调整载具位置。"],
        "keyRules": [], "specialCases": [], "acceptanceExamples": [],
    }
    chapter["ruleHeading"] = "索敌与伤害结算"
    chapter["claims"] = []
    chapter["parameters"] = {}

    xml = render_gameplay_sections(job)

    assert "玩家横向移动载具规避敌人并持续推进" in xml
    assert "玩家拖动摇杆调整载具位置" in xml
    assert "一句话玩法" not in xml
    assert "正常怎么玩" not in xml
    assert "关键规则" not in xml


def test_deep_chapter_keeps_only_supported_structure_for_scanning():
    xml = render_gameplay_sections(complete_job())

    assert all(title not in xml for title in ("一句话玩法", "正常怎么玩", "关键规则", "特殊情况", "检查示例"))
    assert "玩家通过连续战斗推进关卡并完成本次挑战" in xml
    assert "挑战失败时进入失败结算" in xml


def test_feishu_places_approved_inline_screenshot_with_its_mechanism():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["inlineFigures"] = [{
        "frameId": "F0001",
        "caption": "首领来袭警告用于说明普通战斗切换到首领阶段。",
    }]
    job["reviewModel"]["sources"] = {
        "F0001": {"frameId": "F0001", "imageUrl": "/artifacts/job/frames/F0001.jpg"},
    }

    xml = render_gameplay_sections(job)

    assert '<img name="inline-figure-F0001" caption="首领来袭警告用于说明普通战斗切换到首领阶段。"/>' in xml
    assert "<p><b>对应截图：</b>" not in xml
    assert "首领来袭警告用于说明普通战斗切换到首领阶段" in xml
    assert "证据帧" not in xml and "参考画面" not in xml


def test_long_rule_deduplication_keeps_the_later_reviewed_wording():
    from backend.gameplay_render import _dedupe_similar_rules

    early = "首领来袭是自动阶段反馈，不要求玩家点击确认。"
    reviewed = "达到首领阶段条件后自动播放“首领来袭”警告，不要求玩家点击确认。"

    assert _dedupe_similar_rules([early, reviewed]) == [reviewed]


def test_preview_and_feishu_follow_confirmed_dynamic_heading_order(tmp_path: Path):
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter.update(scope="伤害计算", systemName="战斗与关卡", subsystemName="战斗规则")
    chapter["formulae"] = [{
        "expression": "最终伤害 = 攻击属性 × 武器倍率",
        "variables": [{"name": "攻击属性"}, {"name": "武器倍率"}],
    }]
    chapter["workedExamples"] = [{"title": "计算示例", "steps": "100 × 1.5 = 150"}]
    chapter["configurationSources"] = [{"title": "武器基础属性表", "field": "damageRatio"}]
    job["gameplayReviewModel"]["systems"] = [{
        "id": "GSY-001", "name": "战斗与关卡", "subsystems": [{
            "id": "GSS-001", "name": "战斗规则", "chapterIds": [chapter["id"]],
        }],
    }]
    job["gameplayReviewModel"]["directory"]["entries"][0]["sectionTitle"] = "不应采用的旧分组"

    preview = render_gameplay_sections(job)
    feishu = render_feishu_document(job, tmp_path).xml

    expected = ["战斗与关卡", "战斗规则", "伤害计算"]
    assert all(preview.index(title) < preview.index(expected[index + 1]) for index, title in enumerate(expected[:-1]))
    assert all(feishu.index(title) < feishu.index(expected[index + 1]) for index, title in enumerate(expected[:-1]))
    assert "不应采用的旧分组" not in preview
    assert "不应采用的旧分组" not in feishu
    assert "武器系统" not in preview and "武器系统" not in feishu
    for value in ("最终伤害 = 攻击属性 × 武器倍率", "100 × 1.5 = 150", "武器基础属性表"):
        assert value in preview and value in feishu
    for fixed_heading in ("计算方法", "计算示例", "数值从哪里配置"):
        assert fixed_heading not in preview and fixed_heading not in feishu


def test_feishu_prefers_confirmed_planner_summary_over_stale_legacy_copy():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSummary"] = "旧模板摘要不应继续显示。"
    chapter["plannerSections"]["summary"] = "玩家消耗已确认的刷新资源后替换本轮候选内容。"

    xml = render_gameplay_sections(job)

    assert "玩家消耗已确认的刷新资源后替换本轮候选内容" in xml
    assert "旧模板摘要不应继续显示" not in xml


def test_feishu_merges_sparse_mechanisms_under_one_business_section():
    job = complete_job()
    first = job["gameplayReviewModel"]["chapters"][0]
    first.update(id="GCH-001", scope="载具移动机制", claims=[], parameters={}, formulae=[], workedExamples=[], configurationSources=[], acceptanceCases=[], unknowns=[])
    first["plannerSections"] = {"summary": "载具自动前进，玩家负责横向调整位置。", "normalFlow": ["拖动后，载具在可移动范围内横向移动。"], "keyRules": [], "specialCases": [], "acceptanceExamples": []}
    second = deepcopy(first)
    second.update(id="GCH-002", scope="生命值状态管理")
    second["plannerSections"] = {"summary": "载具受到伤害时扣减生命值，生命归零后本局失败。", "normalFlow": [], "keyRules": ["无效攻击不会扣减生命值。"], "specialCases": [], "acceptanceExamples": []}
    job["gameplayReviewModel"]["chapters"] = [first, second]
    job["gameplayReviewModel"]["diagrams"] = []
    job["gameplayReviewModel"]["systems"] = [{"id": "GSY-001", "name": "核心战斗", "subsystems": [
        {"id": "GSS-001", "name": "载具控制", "chapterIds": ["GCH-001"]},
        {"id": "GSS-002", "name": "生存规则", "chapterIds": ["GCH-002"]},
    ]}]
    job["gameplayReviewModel"]["directory"]["understanding"] = {"summary": "玩家控制载具推进关卡并在战斗中保持生存。"}
    job["gameplayReviewModel"]["reviewState"]["findings"] = []

    xml = render_gameplay_sections(job)

    assert xml.count("<h1>") == 1
    assert "<h1>核心战斗</h1>" in xml
    assert "<h2>" not in xml and "<h3>" not in xml
    assert "<b>载具移动：</b>载具自动前进" in xml
    assert "<b>生命值：</b>载具受到伤害" in xml
    assert "<ul>" not in xml


def test_feishu_keeps_deep_mechanism_as_an_independent_section():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter.update(scope="伤害结算", claims=[], parameters={}, unknowns=[])
    chapter["plannerSections"] = {"summary": "命中后结算伤害。", "normalFlow": ["确认目标。", "读取攻击属性。", "应用武器倍率。", "扣减目标生命值。"], "keyRules": [], "specialCases": [], "acceptanceExamples": []}
    chapter["formulae"] = [{"name": "最终伤害", "expression": "攻击属性 × 武器倍率"}]
    job["gameplayReviewModel"]["diagrams"] = []
    job["gameplayReviewModel"]["systems"] = [{"id": "GSY-001", "name": "核心战斗", "subsystems": [{"id": "GSS-001", "name": "战斗结算", "chapterIds": [chapter["id"]]}]}]

    xml = render_gameplay_sections(job)

    assert "<h1>玩法概述</h1>" in xml
    assert "<h1>核心战斗</h1>" in xml
    assert "<h2>战斗结算</h2>" in xml
    assert "<h3>伤害结算</h3>" in xml


def test_feishu_renders_labeled_gameplay_overview_as_separate_lines():
    job = complete_job()
    job["gameplayReviewModel"]["directory"]["understanding"]["summary"] = (
        "核心目标：击败首领。\n\n"
        "基础操作：横向移动。\n\n"
        "核心循环：战斗、强化、推进。\n\n"
        "胜败条件：击败首领获胜，生命归零失败。"
    )

    xml = render_gameplay_sections(job)

    assert "<p>核心目标：击败首领。</p>" in xml
    assert "<p>基础操作：横向移动。</p>" in xml
    assert "核心目标：击败首领。 基础操作：横向移动。" not in xml


def test_feishu_gives_deep_mechanism_semantic_subheadings():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["scope"] = "武器攻击"
    job["gameplayReviewModel"]["directory"]["entries"][0]["title"] = "武器攻击"
    chapter["ruleHeading"] = "索敌与伤害结算"
    chapter["plannerSections"] = {
        "summary": "武器自动攻击范围内敌人。",
        "normalFlow": ["搜索目标。", "确认目标在射程内。", "执行攻击并结算伤害。"],
        "keyRules": ["目标离开射程时不造成伤害。"],
        "specialCases": [], "acceptanceExamples": [],
    }

    xml = render_gameplay_sections(job)

    assert "<h4>武器攻击流程</h4>" in xml
    assert "<h4>索敌与伤害结算</h4>" in xml
    assert "<h4>规则与边界</h4>" not in xml


def test_feishu_collapses_reviewed_audit_table_into_delivery_columns():
    job = complete_job()
    chapter_id = job["gameplayReviewModel"]["chapters"][0]["id"]
    job["gameplayReviewModel"]["tables"] = [{
        "id": "T1", "title": "强化参数", "status": "reviewed", "chapterIds": [chapter_id],
        "columns": ["字段", "类型", "AI 建议值", "修改值", "状态", "操作"],
        "rows": [["火焰射击范围", "百分比（%）", "30", "30", "已确认", "确认"], ["雷暴枪伤害", "百分比（%）", "80", "100", "已确认", "确认"]],
    }]

    xml = render_gameplay_sections(job)

    assert "<th>参数</th><th>确认值</th>" in xml
    assert "<td>火焰射击范围</td><td>30%</td>" in xml
    assert "<td>雷暴枪伤害</td><td>100%</td>" in xml
    assert "AI 建议值" not in xml and "<th>操作</th>" not in xml


def test_vehicle_level_rule_keeps_configuration_table_granularity():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["scope"] = "载具等级"
    chapter["plannerSections"] = {
        "summary": "载具初始为1级，消耗指定道具升级并提升基础属性。",
        "normalFlow": ["各等级消耗同一种道具，但消耗数量不同。"],
        "keyRules": ["升级行为不可逆。", "活动结束后载具等级重置。"],
        "specialCases": [], "acceptanceExamples": [],
    }
    chapter["configurationSources"] = [
        {"title": "GveMagicBookVehicle", "field": "_id"},
        {"title": "GveMagicBookVehicle", "field": "cost"},
        {"title": "GveMagicBookVehicle", "field": "atk"},
        {"title": "GveMagicBookVehicle", "field": "hp"},
        {"title": "GveMagicBookVehicle", "field": "dr"},
    ]

    rendered = render_gameplay_sections(job)

    for value in ("载具等级", "初始为1级", "同一种道具", "升级行为不可逆", "活动结束后载具等级重置", "GveMagicBookVehicle", "_id", "cost", "atk", "hp", "dr"):
        assert value in rendered


def test_gameplay_renderer_strips_internal_ids_when_optional_diagram_is_unreviewed():
    job = complete_job()
    job["gameplayReviewModel"]["chapters"][0]["claims"][0]["text"] = "EVT-001 后进入战斗"
    job["gameplayReviewModel"]["diagrams"][0]["status"] = "draft"
    job["gameplayReviewModel"]["diagrams"][0]["svg"] = '<svg onload="alert(1)"><script>x</script></svg>'

    xml = render_gameplay_sections(job)

    assert "EVT-001" not in xml
    assert "script" not in xml and "onload" not in xml


@pytest.mark.parametrize("payload", [
    '<svg></svg><h1>INJECTED</h1><whiteboard type="raw"></whiteboard>',
    '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><svg>&xxe;</svg>',
    '<svg><foreignObject><div>bad</div></foreignObject></svg>',
    '<svg OnLoad="alert(1)"><text>bad</text></svg>',
    '<svg><image HREF="https://evil.example/x.png"/></svg>',
])
def test_gameplay_renderer_blocks_malformed_or_active_reviewed_svg(payload):
    job = complete_job()
    job["gameplayReviewModel"]["diagrams"][0]["svg"] = payload

    with pytest.raises(ValueError, match="GDI-001:DIAGRAM_RENDER_INVALID"):
        render_gameplay_sections(job)


@pytest.mark.parametrize("status,freshness", [("draft", "current"), ("reviewed", "stale")])
def test_gameplay_renderer_ignores_invalid_diagram_that_is_not_current_and_reviewed(status, freshness):
    job = complete_job()
    diagram = job["gameplayReviewModel"]["diagrams"][0]
    diagram.update(status=status, freshness=freshness, svg='<svg onload="bad()"/>')

    xml = render_gameplay_sections(job)

    assert '<whiteboard type="svg">' not in xml


def test_single_document_orders_interaction_before_gameplay_without_evidence_wall(tmp_path: Path):
    job = complete_job()
    rendered = render_feishu_document(job, tmp_path)

    assert rendered.xml.index("文档概述") < rendered.xml.index("玩法概述") < rendered.xml.index("策划草图")
    assert "竞品参考" not in rendered.xml
    assert "UE 流转图" not in rendered.xml
    assert rendered.xml.count("<h1>策划草图</h1>") == 1
    assert "证据帧" not in rendered.xml
    assert "SCN-" not in rendered.xml and "EVT-" not in rendered.xml
    assert rendered.xml.count('<whiteboard type="blank"></whiteboard>') == 1 + rendered.embedded_whiteboard_count


def test_combined_legacy_gameplay_mode_outputs_planning_board_only(tmp_path: Path):
    job = complete_job()
    job["planningModel"]["mode"] = "gameplay"

    rendered = render_feishu_document(job, tmp_path)

    assert [board.key for board in rendered.native_boards] == ["planning"]
    assert rendered.xml.count('<whiteboard type="blank"></whiteboard>') == 1 + rendered.embedded_whiteboard_count
    assert "UX设计" not in rendered.xml


def test_final_preview_records_and_returns_both_current_revisions(tmp_path: Path):
    job = complete_job()

    preview = build_final_review_preview(job, tmp_path)

    assert preview["exportReady"] is True
    assert preview["interactionRevision"] == job["reviewModel"]["revision"]
    assert preview["gameplayRevision"] == job["gameplayReviewModel"]["revision"]
    assert preview["directoryRevision"] == 1
    assert job["gameplayReviewModel"]["reviewState"]["previewRevision"] == preview["gameplayRevision"]
    assert [item["type"] for item in preview["documentOrder"]] == [
        "title", "document_overview", "gameplay_overview", "ue_board", "gameplay_section", "gameplay_subsection", "gameplay_chapter", "gameplay_diagram", "pending_list"
    ]
    assert all("xml" not in item and "svg" not in item for item in preview["documentOrder"])
    rendered = render_feishu_document(job, tmp_path)
    shared_boards = dict(rendered.preview_board_svgs)
    assert preview["planningBoardPreviewSvg"] == shared_boards["planning"]
    assert "competitor" not in shared_boards


def test_gameplay_document_uses_four_heading_levels_instead_of_flat_chapters():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["scope"] = "伤害计算"
    job["gameplayReviewModel"]["systems"] = [{
        "id": "GSY-001", "name": "战斗与关卡", "subsystems": [{
            "id": "GSS-001", "name": "核心战斗", "chapterIds": [chapter["id"]],
        }],
    }]
    rendered = render_gameplay_document_sections(job)

    assert '<h1>战斗与关卡</h1>' in rendered.xml
    assert '<h2>核心战斗</h2>' in rendered.xml
    assert '<h3>伤害计算</h3>' in rendered.xml
    assert '<h4>一句话玩法</h4>' not in rendered.xml
    levels = {
        item["type"]: item.get("level")
        for item in rendered.order
        if item["type"] in {"gameplay_section", "gameplay_subsection", "gameplay_chapter", "gameplay_diagram"}
    }
    assert levels == {
        "gameplay_section": 1,
        "gameplay_subsection": 2,
        "gameplay_chapter": 3,
        "gameplay_diagram": 4,
    }


def test_final_preview_blocks_invalid_reviewed_diagram_without_pinning(tmp_path: Path):
    job = complete_job()
    job["gameplayReviewModel"]["diagrams"][0]["svg"] = '<svg></svg><whiteboard type="raw"></whiteboard>'

    preview = build_final_review_preview(job, tmp_path)

    assert preview["exportReady"] is False
    assert "GDI-001:DIAGRAM_RENDER_INVALID" in preview["blockerIds"]
    assert preview["documentOrder"] == []
    assert job["gameplayReviewModel"]["reviewState"].get("previewRevision") is None
    with pytest.raises(ValueError, match="GDI-001:DIAGRAM_RENDER_INVALID"):
        render_feishu_document(job, tmp_path)


def test_final_preview_rejects_stale_interaction_binding(tmp_path: Path):
    job = complete_job()
    job["gameplayReviewModel"]["interactionRevision"] -= 1

    preview = build_final_review_preview(job, tmp_path)

    assert preview["exportReady"] is False
    assert "INTERACTION_REVISION_STALE" in preview["blockerIds"]
    assert job["gameplayReviewModel"]["reviewState"].get("previewRevision") is None


def test_final_preview_blocks_failed_structured_rule_guard(tmp_path: Path):
    job = complete_job()
    job["gameplayReviewModel"]["ruleIntelligenceProjection"] = {
        "authorityMode": "structured_rules",
        "guard": {"passed": False, "blockedRuleIds": ["R-STALE"]},
        "publication": {"chapters": [{
            "chapterId": "GCH-001", "title": "攻击规则", "publicationEligibility": "eligible",
            "ruleDefinitions": [{"ruleId": "R-1", "behavior": "每 1 秒执行一次攻击。"}],
            "references": [], "gaps": [],
        }]},
    }

    preview = build_final_review_preview(job, tmp_path)

    assert preview["exportReady"] is False
    assert "STRUCTURED_RULE_GUARD_FAILED" in preview["blockerIds"]
def test_gameplay_document_keeps_attribute_prose_without_generating_a_generic_parameter_table():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSections"]["attributeSections"] = [{
        "heading": "生存与防御",
        "items": ["生命值：受到最终伤害后扣减，降至 0 时进入死亡流程。"],
    }]
    chapter["parameterSchema"] = [{
        "name": "生命值", "type": "整数", "unit": "点", "defaultValue": 100,
    }]

    xml = render_gameplay_document_sections(job).xml

    assert "<h4>生存与防御</h4>" in xml
    assert "生命值：受到最终伤害后扣减" in xml
    assert "<table>" not in xml
    assert "填写格式" not in xml


def test_gameplay_document_uses_object_heading_then_attribute_group_headings():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSections"]["attributeHeading"] = "载具"
    chapter["plannerSections"]["attributeSections"] = [{
        "heading": "承伤与武器换算",
        "items": ["生命值：受到最终伤害后扣减。"],
    }, {
        "heading": "等级与栏位状态",
        "items": ["武器栏：已选武器在本关卡内不可卸除。"],
    }]

    xml = render_gameplay_document_sections(job).xml

    assert "<h3>载具</h3>" in xml
    assert "<h4>承伤与武器换算</h4>" in xml
    assert "<h4>等级与栏位状态</h4>" in xml


def test_diagram_does_not_split_a_numbered_rule_group_or_publish_editor_followup():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["plannerSections"]["normalFlow"] = ["进入关卡。", "持续战斗。", "完成结算。"]
    diagram = job["gameplayReviewModel"]["diagrams"][0]
    diagram["chapterIds"] = [chapter["id"]]
    diagram["placement"] = {"chapterId": chapter["id"], "afterFlowIndex": 0,
                            "followUp": "图中的升级由后续章节展开；本节继续说明载具边界。"}

    xml = render_gameplay_document_sections(job).xml

    flow_start = xml.index("进入关卡。")
    flow_end = xml.index("完成结算。")
    diagram_start = xml.index("<whiteboard", flow_start)
    assert flow_start < flow_end < diagram_start
    assert "后续章节" not in xml
    assert "本节继续说明" not in xml


def test_delivery_preview_decorates_native_tables_without_flattening_cells():
    from types import SimpleNamespace
    from backend.review_preview import _delivery_preview_html

    rendered = SimpleNamespace(
        xml=("<h3>载具等级</h3><table><thead><tr><th>等级</th><th>升级道具ID</th>"
             "<th>消耗数量</th><th>攻击力</th></tr></thead><tbody>"
             "<tr><td>1</td><td>—</td><td>—</td><td>—</td></tr>"
             "<tr><td>2～上限</td><td></td><td></td><td></td></tr></tbody></table>"),
        preview_board_svgs=[], embedded_whiteboards=[],
    )
    html = _delivery_preview_html(rendered)

    assert '<div class="final-document-table-scroll"><table class="final-document-table final-document-delivery-table">' in html
    assert html.count("<th>") >= 4
    assert html.count("<td>") >= 8
    assert "等级升级道具ID消耗数量攻击力" not in html


def test_long_rule_list_uses_a_few_semantic_headings_and_removes_near_duplicates():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["scope"] = "关卡阶段与首领战"
    chapter["plannerSections"]["keyRules"] = [
        "首领来袭是自动阶段反馈，不要求玩家点击确认。",
        "达到首领阶段条件后自动播放首领来袭警告，不要求玩家点击确认。",
        "警告结束后切入首领战并显示首领名称和生命百分比。",
        "关卡时间和局内等级在首领战中继续累计。",
        "怪物生命值等于基础生命值乘当前波次生命倍率。",
        "受到攻击时优先判定闪避。",
        "怪物仍有格挡次数时优先消耗一次格挡。",
        "首领生命归零进入成功结算。",
    ]
    chapter["plannerSections"]["specialCases"] = ["载具生命归零进入失败结算，两条结果互斥。"]

    xml = render_gameplay_document_sections(job).xml

    for heading in ("触发与战斗状态", "属性与承伤判定", "胜负结算"):
        assert f"<h4>{heading}</h4>" in xml
    assert xml.count("不要求玩家点击确认") == 1
    assert "其他规则" not in xml


def test_long_unrelated_chapter_does_not_borrow_boss_rule_headings():
    job = complete_job()
    chapter = job["gameplayReviewModel"]["chapters"][0]
    chapter["scope"] = "挑战成功、奖励与伤害统计"
    chapter["plannerSections"]["keyRules"] = [f"结算规则 {index}。" for index in range(10)]

    xml = render_gameplay_document_sections(job).xml

    assert "触发与战斗状态" not in xml
    assert "属性与承伤判定" not in xml
