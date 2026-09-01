from scripts.publish_yilu_v3_preserving_assets import build_v3_feishu_payload, plan_block_reorganization


def test_v3_payload_keeps_gameplay_figures_and_tables_but_removes_retired_boards():
    old = """<fragment><h2 id="ue">UE流转图</h2><h3 id="ux">UX设计</h3><whiteboard id="old-board" token="B0"/>
    <h2 id="weapon">武器</h2><p id="old-rule">旧规则</p><h4 id="figure-title">图示：武器流程</h4>
    <whiteboard id="figure" token="B1"/><h4 id="table-title">配置表：武器配置</h4><table id="table"><tr><td><p id="cell">参数</p></td></tr></table></fragment>"""
    payload = build_v3_feishu_payload(old, "# 新版执行案\n\n## 武器\n\n新版规则。", {
        "excludedSections": ["UE流转图", "UX设计", "策划草图", "竞品参考"],
        "appendixTitle": "附录：既有玩法图表",
    })

    assert "新版执行案" in payload["markdown"]
    assert payload["retainedAssetCaptions"] == ["图示：武器流程", "配置表：武器配置"]
    assert payload["retainedBlockIds"] == ["figure-title", "figure", "table-title", "table"]
    assert {"ue", "ux", "old-board", "old-rule", "weapon"}.issubset(set(payload["deleteBlockIds"]))
    assert "UE流转图" not in payload["markdown"]
    assert "竞品参考" not in payload["markdown"]


def test_table_cell_blocks_are_not_deleted_individually_when_table_is_retained():
    xml = "<fragment><h2 id='h'>系统</h2><h4 id='c'>配置表：参数</h4><table id='t'><tr><td><p id='cell'>值</p></td></tr></table></fragment>"
    plan = plan_block_reorganization(xml, {"excludedSections": [], "appendixTitle": "附录"})

    assert plan["retainedBlockIds"] == ["c", "t"]
    assert "cell" not in plan["deleteBlockIds"]

