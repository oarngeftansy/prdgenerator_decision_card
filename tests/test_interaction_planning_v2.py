from __future__ import annotations

from backend.interaction_planning import (
    audit_planning_sketch,
    build_planning_sketch,
    planning_sketch_to_markdown,
    project_and_review_interactions,
)


def _publication() -> dict:
    return {
        "chapters": [
            {"chapterId": "MOVE", "title": "场景移动"},
            {"chapterId": "SHOP", "title": "商店交易"},
            {"chapterId": "SIM", "title": "离线生产"},
        ],
        "rules": [
            {
                "ruleId": "R-MOVE",
                "canonicalOwner": "MOVE",
                "publicationEligibility": "eligible",
                "publicationState": "confirmed",
                "behavior": "角色持续接收方向输入并更新合法位置",
                "trigger": "方向输入变化",
                "conditions": ["目标位置可通行"],
                "result": "角色位置更新",
                "stateChange": "当前位置 -> 新位置",
                "acceptanceCases": ["不可通行位置不会被写入"],
            },
            {
                "ruleId": "R-SHOP",
                "canonicalOwner": "SHOP",
                "publicationEligibility": "eligible",
                "publicationState": "inferred",
                "behavior": "玩家点击购买后校验货币和库存并提交交易",
                "trigger": "点击购买",
                "conditions": ["货币足够", "库存可用"],
                "result": "货币减少并获得商品",
                "exception": "校验失败时保持原状态并显示失败反馈",
            },
            {
                "ruleId": "R-SIM",
                "canonicalOwner": "SIM",
                "publicationEligibility": "eligible",
                "publicationState": "proposed",
                "behavior": "系统按已记录的生产速率累计离线产出",
                "trigger": "重新进入项目",
                "result": "结算可领取产出",
                "persistence": "保存最后结算时间",
                "reset": "完成结算后更新时间锚点",
            },
        ],
    }


def test_planning_sketch_supports_ui_gameplay_and_system_contexts() -> None:
    sketch, review = project_and_review_interactions(_publication())
    context_types = {context["contextType"] for context in sketch["contexts"]}
    assert context_types == {"ui_surface", "gameplay_context", "system_context"}
    assert review["ready"] is True
    assert review["uncoveredRuleIds"] == []
    assert review["orphanInteractionIds"] == []
    assert review["publicationStateCounts"] == {"confirmed": 1, "inferred": 1, "proposed": 1}


def test_planning_sketch_does_not_invent_fake_screen_for_non_ui_mechanic() -> None:
    sketch = build_planning_sketch({
        "chapters": [{"chapterId": "SIM", "title": "自动生产"}],
        "rules": [{
            "ruleId": "R-1",
            "canonicalOwner": "SIM",
            "publicationState": "proposed",
            "behavior": "系统每个结算周期累计产出并写入资源状态",
            "trigger": "结算周期结束",
            "result": "资源状态更新",
        }],
    })
    assert len(sketch["contexts"]) == 1
    assert sketch["contexts"][0]["contextType"] == "system_context"
    assert sketch["contexts"][0]["title"] == "自动生产"


def test_interaction_review_blocks_only_structural_traceability_defects() -> None:
    publication = _publication()
    sketch = build_planning_sketch(publication)
    sketch["contexts"][0]["interactions"] = []
    review = audit_planning_sketch(sketch, publication)
    assert review["ready"] is False
    assert "planning_sketch_rule_coverage_incomplete" in review["criticalIssues"]
    assert "inferred" not in review["criticalIssues"]
    assert "proposed" not in review["criticalIssues"]


def test_planning_sketch_markdown_publishes_decisions_without_provenance_labels() -> None:
    sketch = build_planning_sketch(_publication())
    markdown = planning_sketch_to_markdown(sketch)
    assert "玩家点击购买后校验货币和库存并提交交易" in markdown
    assert "系统按已记录的生产速率累计离线产出" in markdown
    assert "【黄色：推断】" not in markdown
    assert "【推断】" not in markdown
    assert "【建议】" not in markdown
    assert "根据素材推测" not in markdown
    assert "待确认" not in markdown
