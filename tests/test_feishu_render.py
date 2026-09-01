from pathlib import Path
import re

from backend.feishu_render import _svg_text_block, render_competitor_board_svg, render_feishu_document
from tests.review_fixtures import make_confirmed_job


def _job(mode: str) -> dict:
    flow_key = "gameplay" if mode == "gameplay" else "interaction"
    flow_name = "coreLoop" if mode == "gameplay" else "taskFlow"
    return {
        "id": "job-render",
        "metadata": {"mode": mode, "projectName": "Demo", "scope": "还原演示流程"},
        "frames": [{"id": "F0001", "timestamp": 1.25, "imagePath": "frames/F0001.jpg"}],
        "planningModel": {
            "standard": "GVE16",
            "mode": mode,
            "project": {"name": "Demo", "scope": "还原演示流程"},
            "scenes": [{
                "id": "SCN-001", "title": "开始界面", "objective": "进入关卡",
                "entryCondition": "视频开始", "exitCondition": "点击开始",
                "visibleRules": ["点击后进入下一状态"], "stateChanges": ["菜单到关卡"],
                "evidence": [{"sourceId": "F0001", "locator": "00:01.250", "evidenceLevel": "observed"}],
            }],
            "events": [{
                "id": "EVT-001", "trigger": "点击", "action": "点击开始按钮",
                "beforeState": "菜单", "response": "进入关卡", "afterState": "关卡",
                "evidence": [{"sourceId": "F0001", "locator": "00:01.250", "evidenceLevel": "observed"}],
                "unknowns": [],
            }],
            flow_key: {flow_name: [{"id": "FLOW-001", "eventId": "EVT-001", "from": "菜单", "to": "关卡", "trigger": "点击开始按钮"}]},
            "designHandoff": {"flowEdges": [{"id": "FLOW-001", "eventId": "EVT-001", "from": "菜单", "to": "关卡", "trigger": "点击开始按钮"}]},
            "quality": {"score": 90},
        },
    }


def test_svg_text_block_wraps_and_limits_long_planner_copy():
    svg = _svg_text_block("玩家操控车辆持续攻击敌人并触发大量伤害数字反馈随后进入升级选择并继续战斗", 80, 120, 16, 12, 2, fill="#111")

    assert svg.count("<tspan") == 2
    assert "玩家操控车辆持续攻击敌人并触发大量伤害数字反馈随后进入升级选择并继续战斗" not in svg
    assert "…" in svg


def test_gameplay_document_uses_native_sections_and_embedded_flow():
    rendered = render_feishu_document(_job("gameplay"), Path("D:/jobs/job-render"))

    assert rendered.title.startswith("Demo｜玩法策划案｜")
    assert "<h1>玩法目标与核心机制</h1>" in rendered.xml
    assert [board.key for board in rendered.native_boards] == ["planning"]
    assert rendered.xml.count('<whiteboard type="blank">') == 1
    for legacy_gameplay_section in ("9. 叙事", "11. 引导", "12. 红点提示"):
        assert legacy_gameplay_section in rendered.xml
    assert "玩家操作" in rendered.mermaid
    assert "default-loading" not in rendered.xml
    assert rendered.evidence_images == ()
    assert rendered.native_board.images[0].image_path == "frames/F0001.jpg"


def test_interaction_document_uses_interaction_sections():
    rendered = render_feishu_document(_job("interaction"), Path("D:/jobs/job-render"))

    assert "<h1>页面与组件说明</h1>" in rendered.xml
    assert "显示条件" in rendered.xml
    assert "系统响应" in rendered.mermaid


def test_interaction_document_contains_only_planning_board_and_ignores_legacy_rules():
    job = _job("interaction")
    job["reviewModel"] = {"ruleDomains": {"narrative": [{"title": "legacy"}]}, "referenceBoards": {"ux": ["damaged"]}}

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))

    assert [board.key for board in rendered.native_boards] == ["planning"]
    assert [board.title for board in rendered.native_boards] == ["策划草图"]
    assert rendered.native_board is rendered.native_boards[0].board
    assert rendered.xml.count('<whiteboard type="blank"></whiteboard>') == 1
    for legacy in ("UE 流转图", "竞品参考", "UX设计", "9. 叙事", "11. 引导", "12. 红点提示", "legacy"):
        assert legacy not in rendered.xml


def test_renderer_ignores_corrupt_legacy_rules_and_ux_data():
    job = _job("interaction")
    job["reviewModel"] = {"ruleDomains": ["bad"], "referenceBoards": "bad", "components": [None]}

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))

    assert [item.key for item in rendered.native_boards] == ["planning"]
    assert "AttributeError" not in rendered.xml


def test_renderer_skips_invalid_competitor_assets_without_reading_legacy_rules():
    job = _job("interaction")
    job["reviewModel"] = {
        "components": [None], "ruleDomains": ["damaged"],
        "referenceBoards": {"ux": {"assets": [None]}, "competitor": {"assets": "bad"}},
    }

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))

    assert "首次引导" not in rendered.xml
    assert [item.key for item in rendered.native_boards] == ["planning"]
    assert "AttributeError" not in rendered.xml


def test_competitor_board_wraps_every_copy_block_inside_the_card(tmp_path):
    job = _job("interaction")
    frame_path = tmp_path / "frames" / "F0001.jpg"
    frame_path.parent.mkdir(parents=True)
    frame_path.write_bytes(b"image")
    job["reviewModel"] = {
        "stages": [{"name": "获取终极强化并再次选择武器", "sourceFrameIds": ["F0001"]}],
        "referenceBoards": {"competitor": {"insights": {"F0001": {
            "observed": "强化结果与后续武器选择连续出现，并展示当前可以选择的多项内容。",
            "adopted": "用于说明强化确认后继续选择武器的页面关系与操作反馈。",
            "excluded": "截图只能证明页面展示内容，不能据此推断隐藏概率、正式公式、默认数值或者后台配置字段。",
        }}}},
    }

    svg = render_competitor_board_svg(job, tmp_path)

    for copy_kind in ("observed", "adopted", "excluded"):
        match = re.search(rf'<text[^>]+data-copy-kind="{copy_kind}"[^>]*>(.*?)</text>', svg)
        assert match, f"missing wrapped {copy_kind} block"
        lines = re.findall(r"<tspan[^>]*>(.*?)</tspan>", match.group(1))
        assert len(lines) >= 2
        assert max(map(len, lines)) <= 24


def test_interaction_document_renders_region_cards_at_gve16_granularity():
    job = _job("interaction")
    job["frames"][0]["regionCards"] = [{
        "name": "刷新区",
        "visibleContent": "当前剩余观看次数 1/1 与刷新按钮",
        "condition": "选择层显示时可见",
        "feedback": "点击后整组替换候选项，视频未展示结果",
        "resultState": "仍停留在选择层",
        "unknowns": "刷新次数恢复规则待确认",
    }]

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))

    assert "<h2>区域显示与交互规则</h2>" in rendered.xml
    for term in ["区域", "可见内容", "交互规则", "刷新区", "当前剩余观看次数 1/1", "刷新次数恢复规则待确认"]:
        assert term in rendered.xml


def test_renderer_escapes_user_text_without_escaping_tags():
    job = _job("gameplay")
    job["planningModel"]["project"]["scope"] = "A < B & C"

    xml = render_feishu_document(job, Path("D:/jobs/job-render")).xml

    assert "A &lt; B &amp; C" in xml
    assert "&lt;h1&gt;" not in xml


def test_renderer_is_stable_and_fingerprint_changes_with_content():
    job = _job("gameplay")
    first = render_feishu_document(job, Path("D:/jobs/job-render"))
    second = render_feishu_document(job, Path("D:/jobs/job-render"))
    assert first.content_fingerprint == second.content_fingerprint

    job["planningModel"]["events"][0]["response"] = "进入第二关"
    changed = render_feishu_document(job, Path("D:/jobs/job-render"))
    assert changed.content_fingerprint != first.content_fingerprint


def test_renderer_resolves_the_existing_artifact_image_url():
    job = _job("gameplay")
    job["frames"][0].pop("imagePath")
    job["frames"][0]["imageUrl"] = "/artifacts/job-render/frames/F0001_0000001250.jpg"

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))

    assert rendered.evidence_images == ()
    assert rendered.native_board.images[0].image_path == "frames/F0001_0000001250.jpg"


def test_visible_feishu_document_hides_internal_ids_and_evidence_sections():
    rendered = render_feishu_document(_job("interaction"), Path("D:/jobs/job-render"))

    assert "SCN-001" not in rendered.xml
    assert "EVT-001" not in rendered.xml
    assert "FLOW-001" not in rendered.xml
    assert "Evidence" not in rendered.xml
    assert "视频证据" not in rendered.xml
    assert rendered.evidence_images == ()
    assert "<h1>参考画面</h1>" not in rendered.xml
    assert [image.frame_id for image in rendered.native_board.images] == ["F0001"]


def test_event_only_model_uses_one_representative_frame_per_event_on_board_only():
    job = _job("interaction")
    job["frames"] = [
        {"id": f"F{index:04d}", "timestamp": float(index), "imagePath": f"frames/F{index:04d}.jpg"}
        for index in range(1, 138)
    ]
    representative_ids = ["F0007", "F0021", "F0043", "F0064", "F0081", "F0111", "F0136"]
    job["planningModel"]["events"] = [
        {
            "id": f"EVT-{index:03d}",
            "action": f"操作 {index}",
            "response": f"反馈 {index}",
            "evidence": [{"sourceId": frame_id}],
        }
        for index, frame_id in enumerate(representative_ids, 1)
    ]

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))

    assert rendered.evidence_images == ()
    assert "<h1>参考画面</h1>" not in rendered.xml
    assert [image.frame_id for image in rendered.native_board.images] == representative_ids


def test_confirmed_review_document_renders_complete_contract_without_duplicate_evidence():
    job = make_confirmed_job()
    job["planningModel"] = _job("interaction")["planningModel"]
    review = job["reviewModel"]
    first_stage, second_stage = review["stages"]
    review["transitions"] = [{
        "id": "TRN-001",
        "included": True,
        "confirmation": {"confirmed": True},
        "sourceStageId": first_stage["id"],
        "targetStageId": second_stage["id"],
        "triggerLabel": "点击已确认入口",
        "condition": "入口可操作",
        "response": "立即展示已确认反馈",
        "resultState": "进入已确认结果状态",
        "resultType": "navigate",
    }]
    review["components"] = [
        {"id": "CMP-0001", "stageId": first_stage["id"], "name": "确认按钮"},
        {"id": "CMP-0002", "stageId": first_stage["id"], "name": "未标注组件"},
    ]
    review["componentStates"] = [{
        "componentId": "CMP-0001",
        "states": {
            "default": "默认可见", "pressed": "按下反馈", "selected": "选中反馈",
            "disabled": "待确认", "loading": "加载中", "success": "成功反馈",
            "error": "错误反馈", "exhausted": "次数耗尽", "condition_unmet": "条件不满足",
        },
    }]
    review["crossStateConstraints"] = [{"id": "CST-001", "text": "返回后是否保留选择待确认", "status": "unknown"}]

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))
    xml = rendered.xml

    assert "阶段完整事件链" in xml
    for term in [
        "进入前状态", "操作/触发", "系统响应", "操作后状态", "条件", "结果",
        first_stage["entryCondition"], "已确认触发", "已确认反馈", first_stage["exitCondition"],
    ]:
        assert term in xml
    assert "已确认转换链" in xml
    for term in ["点击已确认入口", "入口可操作", "立即展示已确认反馈", "进入已确认结果状态"]:
        assert term in xml

    assert "组件状态矩阵" in xml
    for term in [
        "默认", "按下", "选中", "禁用", "加载", "成功", "错误", "次数耗尽", "条件不满足",
        "默认可见", "待确认", "次数耗尽",
    ]:
        assert term in xml
    assert "可执行验收项" in xml
    assert "确认按钮" in xml
    assert "未标注组件" in xml
    assert "返回后是否保留选择待确认" in xml
    assert xml.count("<whiteboard") == 1
    assert "<img" not in xml
    assert "<h1>参考画面</h1>" not in xml
    assert xml.index("项目说明") < xml.index("页面与组件说明") < xml.index("交互流程与状态") < xml.index("策划草图")


def test_native_numbered_chapter_body_numbers_the_real_sections_without_detached_index():
    from backend.feishu_render import _native_numbered_chapter_body

    rendered = _native_numbered_chapter_body(
        "<h1>一路狂飙</h1><h2>玩法概述</h2><p>核心循环。</p><h2>武器</h2><p>自动攻击。</p>"
    )

    assert rendered.count('seq="auto"') == 2
    assert '<li seq="auto"><h2>玩法概述</h2><p>核心循环。</p></li>' in rendered
    assert '<li seq="auto"><h2>武器</h2><p>自动攻击。</p></li>' in rendered
    assert "自动编号目录" not in rendered


def test_accepted_publication_bypasses_legacy_gameplay_and_uses_native_numbering():
    job = _job("gameplay")
    job["gameplayReviewModel"] = {"chapters": [{"scope": "旧章节", "plannerSections": {"summary": "旧正文"}}]}
    job["acceptedPublication"] = {
        "markdown": "# 一路狂飙\n\n## 玩法概述\n\n<!-- EMBED:BOARD:ue -->\n<!-- EMBED:BOARD:planning -->\n<!-- EMBED:BOARD:competitor -->\n\n## 武器\n\n1. 筛选合法目标。\n2. 目标失效后重新选择。\n\n| 参数 | 当前值 |\n|---|---|\n| 射程 | 8世界单位 |",
        "p5Diagrams": [{"id": "P5-W", "title": "武器流程", "status": "reviewed", "svg": "<svg><path d=\"M0 0L1 1\"/></svg>"}],
        "p6Tables": [{"id": "P6-W", "title": "武器配置", "status": "reviewed", "rows": [["射程", "攻击距离", "8", "8世界单位", "已确认", "已批准"]]}],
    }

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))

    assert "旧正文" not in rendered.xml
    assert "筛选合法目标" in rendered.xml
    assert rendered.xml.count('seq="auto"') >= 4
    assert "1. 筛选合法目标" not in rendered.xml
    assert "自动编号目录" not in rendered.xml
    assert '<li seq="auto"><h2>玩法概述</h2>' in rendered.xml
    assert "武器配置" in rendered.xml and "8世界单位" in rendered.xml
    assert rendered.embedded_whiteboard_count == 1
    assert rendered.xml.count('<whiteboard type="blank"></whiteboard>') == len(rendered.native_boards) + 1


def test_accepted_publication_interleaves_diagrams_and_tables_at_body_anchors():
    job = _job("gameplay")
    job["acceptedPublication"] = {
        "markdown": """# 一路狂飙

## 武器

<!-- EMBED:BOARD:ue -->

<!-- EMBED:BOARD:planning -->

<!-- EMBED:BOARD:competitor -->

### 选敌与伤害

- 筛选合法目标并结算伤害。

<!-- EMBED:P5:P5-W -->

<!-- EMBED:P6:P6-W -->

## 怪物

- 怪物接触载具后攻击。
""",
        "p5Diagrams": [{"id": "P5-W", "title": "武器流程", "status": "reviewed", "svg": "<svg><path d=\"M0 0L1 1\"/></svg>"}],
        "p6Tables": [{
            "id": "P6-W", "title": "武器配置", "status": "reviewed",
            "publicationColumns": ["参数", "含义", "当前值"],
            "publicationRows": [["射程", "攻击距离", "8世界单位"]],
        }],
    }

    rendered = render_feishu_document(job, Path("D:/jobs/job-render"))
    published_body = rendered.xml

    assert published_body.index("筛选合法目标") < published_body.index("图示：武器流程")
    assert published_body.index("图示：武器流程") < published_body.index("配置表：武器配置")
    assert published_body.index("配置表：武器配置") < published_body.index("怪物接触载具")
    assert "<h1>必要图解</h1>" not in rendered.xml
    assert "<h1>参数配置表</h1>" not in rendered.xml
    assert "EMBED:P5" not in rendered.xml and "EMBED:P6" not in rendered.xml
    assert rendered.embedded_whiteboards == (("武器流程", "<svg><path d=\"M0 0L1 1\"/></svg>"),)
