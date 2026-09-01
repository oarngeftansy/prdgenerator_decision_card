from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_upload_workspace_prioritizes_materials_and_hides_generated_source_text():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")

    assert 'class="setup-intro"' not in html
    assert 'class="analysis-panel panel"' in html
    assert 'id="output"' in html and 'class="output-state"' in html
    assert 'class="output"' not in html
    assert ".output-state { display: none; }" in css
    assert "grid-template-columns: repeat(4, minmax(0, 1fr));" in css
    assert '.classList.toggle("setup-mode"' in (ROOT / "js" / "app.js").read_text(encoding="utf-8")


def test_stage_navigation_stays_visible_in_every_review_section():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert html.count('class="review-step-nav"') == 1
    assert '.review-workspace[data-active-view="gameplay"]>.review-workspace-header' not in css
    assert '.review-workspace[data-active-view="gameplay"] { height:' not in css


def test_review_workspace_accessibility_and_responsive_contract():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert 'aria-label="审核步骤"' in html
    assert 'aria-live="polite"' in html
    assert "min-height: 44px" in css
    assert ":focus-visible" in css
    assert "overflow-x: auto" in css
    assert "max-width: 700px" in css
    assert "stage-mobile-tabs" in css
    assert "prefers-reduced-motion" in css


def test_review_workspace_reserves_screenshot_space_and_keeps_page_non_scrolling():
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert ".stage-shot {" in css and "aspect-ratio: 9 / 16;" in css
    assert ".stage-shot img {" in css and "object-fit: contain;" in css
    assert ".ue-flow-screen-image{width:100%;height:100%;object-fit:contain}" in css
    assert "body.has-review { overflow-x: hidden; }" in css
    assert ".flow-stage-lane" in css and "overflow-x: auto" in css
    assert ".planner-stage-name" in css and "-webkit-line-clamp: 2" in css


def test_review_workspace_actions_are_44px_and_export_preview_does_not_create_a_second_scroller():
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert ".review-workspace .btn, .review-workspace .flow-candidate-select { min-height: 44px;" in css
    assert ".export-preview-board { min-width: 0; overflow: auto;" in css
    # Keep the authored desktop board width and scroll only its container.
    assert ".export-preview-board svg { display:block; width:auto; min-width:1380px; max-width:none; height:auto;" in css


def test_review_workspace_header_matches_the_target_single_desktop_toolbar():
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert ".review-workspace-header {\n  display: flex;\n  align-items: center;" in css
    assert ".review-workspace-title { display: none; }" in css
    assert ".review-workspace-actions { display: contents; }" in css


def test_review_workspace_exposes_contextual_accessible_confirmation_controls():
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    assert 'id="reviewConfirmFlowBtn"' in html
    assert 'id="reviewConfirmStageBtn"' in html
    assert 'aria-describedby="reviewValidationError"' in html
    assert 'id="reviewValidationError"' in html and 'aria-live="assertive"' in html


def test_review_workspace_exposes_interaction_then_gameplay_phase_navigation():
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    assert 'data-review-view="rules"' not in html
    assert 'id="rulesReviewView"' not in html
    assert "rule-domain-review.js" not in html
    assert html.count("data-review-view=") == 7
    for view in ("gameplay_directory", "flow", "interaction_preview", "gameplay", "diagrams", "tables", "final_preview"):
        assert f'data-review-view="{view}"' in html
    assert 'data-review-view="stage"' not in html  # flow and page review share one planner-facing step
    assert "onclick=" not in html


def test_review_workspace_navigation_uses_the_approved_p1_to_p7_numbering():
    html = (ROOT / "index.html").read_text(encoding="utf-8")

    # P1-P7 follow the preceding AI-understanding step in the visible toolbar,
    # so their target-facing numbers are 2-8 rather than their phase ids.
    for phase, label in enumerate(("玩法目录", "交互审核", "交付物预览", "规则审核", "图解审核", "参数审核", "文档导出"), 1):
        assert f'data-workbench-step="p{phase}"' in html
        assert f'<span class="review-step-number">{phase}</span>{label}' in html


def test_interaction_review_uses_one_shared_content_baseline():
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert ".planner-stage-content { display:grid; grid-template-columns:minmax(260px,.8fr) minmax(360px,1.15fr) minmax(300px,.75fr);" in css
    assert ".planner-stage-heading,.planner-stage-flow { grid-column:1/-1; }" in css
    assert ".planner-evidence-drawer:not(.planner-page-editor) { grid-column:1; grid-row:3;" in css
    assert ".planner-page-editor { grid-column:3; grid-row:3;" in css


def test_desktop_interaction_review_does_not_stretch_empty_grid_rows():
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert "grid-template-rows: auto auto minmax(0, 1fr);" in css
    assert ".planner-stage-heading {\n  grid-column: 1 / -1;" in css
    assert ".planner-stage-flow { grid-column: 1 / -1;" in css


def test_gameplay_review_contract_keeps_evidence_out_of_editor_and_loads_its_assets():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "css" / "gameplay-review.css").read_text(encoding="utf-8")

    assert 'id="gameplayReviewView"' in html
    assert "gameplay-mechanism-forms.js" in html
    assert "gameplay-review.js" in html
    assert "gameplay-review.css" in html
    assert ".gameplay-evidence-drawer" in css
    assert "@media (max-width: 700px)" in css
    assert "prefers-reduced-motion" in css
    assert 'data-active-tab="parameters"' in css
    assert 'data-active-tab="issues"' in css
    assert "overflow-x:hidden" in css or "overflow-x: hidden" in css
    assert "@media (max-width: 900px)" in css


def test_desktop_gameplay_review_keeps_sparse_columns_compact():
    css = (ROOT / "css" / "gameplay-review.css").read_text(encoding="utf-8")
    shared_css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")

    assert ".gameplay-directory-understanding-body { flex:0 1 auto; max-height:42%;" in css
    assert ".gameplay-directory-family-tags { flex:0 0 auto;" in css
    assert ".gameplay-evidence-thumbnails .gameplay-inline-evidence-image { width:auto; height:112px;" in css
    assert ".interaction-flow-node-image { display:block; width:100%; height:auto; aspect-ratio:9/16;" in shared_css
    assert ".gameplay-chapter-rail { grid-column:1; align-content:start;" in css
    assert ".gameplay-review:has(.gameplay-evidence-empty) { grid-template-columns:300px 260px minmax(620px,1fr); }" in css

    source = (ROOT / "js" / "gameplay-review.js").read_text(encoding="utf-8")
    assert 'data-gameplay-panel' in source
    assert 'class: "gameplay-save-status"' in source
    assert 'class: "gameplay-context-status"' in source


def test_gameplay_studio_uses_planner_reading_size_instead_of_twelve_pixel_body_copy():
    css = (ROOT / "css" / "gameplay-review.css").read_text(encoding="utf-8")

    assert ".gameplay-planning-table { font-size:14px;" in css
    assert ".gameplay-evidence-facts p { font-size:14px;" in css
    assert ".gameplay-summary>.gameplay-planner-summary { font-size:15px;" in css


def test_reference_board_replacement_input_has_a_mobile_touch_target():
    css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")

    assert ".reference-board-replace { min-height: 44px; }" in css


def test_reference_board_heading_names_the_exact_two_board_workflow():
    source = (ROOT / "js" / "reference-board-assets.js").read_text(encoding="utf-8")

    assert "UE 两画板准备" in source
    assert "UE 三图准备" not in source


def test_interaction_preview_does_not_render_internal_warning_identifiers():
    source = (ROOT / "js" / "export-preview.js").read_text(encoding="utf-8")

    assert 'issueList("可以稍后补充", view.warningIds' not in source
    assert 'issueList("非核心提醒", view.warningIds' not in source


def test_api_setup_can_return_to_the_last_workspace_without_clearing_it():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")

    assert 'id="returnToLastJobBtn"' in html
    assert 'localStorage.getItem("vpr_last_job")' in app


def test_interaction_preview_hides_internal_board_setup_and_representative_frame_copy():
    source = (ROOT / "js" / "export-preview.js").read_text(encoding="utf-8")

    assert "onRenderAssets" not in source
    assert "代表画面" not in source
    assert "UE 两画板准备" not in source
def test_review_workspace_uses_target_html_full_screen_shell():
    css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    assert "body.has-review > header .topbar { display: none; }" in css
    assert "body.has-review > header { display: block; position: static; }" in css
    assert "height: 100dvh" in css
    assert "height: 52px" in css
    assert ".review-workspace-title { display: none; }" in css
    assert "flex-wrap: nowrap" in css
    assert "grid-template-columns: 220px minmax(0, 1fr)" in css
    assert "grid-template-columns: 280px minmax(300px, 1fr) 300px" in css
    assert ".review-context-bar { display: none; }" in css


def test_refactor_maintenance_announcement_is_permanent_and_safe():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    style_css = (ROOT / "css" / "style.css").read_text(encoding="utf-8")
    review_css = (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")

    start = html.index('class="maintenance-announcement"')
    end = html.index('<div class="topbar">', start)
    announcement = html[start:end]

    assert "2026/8/26" in announcement
    assert "代码重构" in announcement
    assert "无法正常使用" in announcement
    assert "@岛岛" in announcement
    assert (
        "https://hjjxo8h8vu.feishu.cn/wiki/MQOWwHokkimZakkoa2ycUGwZnib"
        "?table=tblpdxq33mhp9eWW&amp;view=vewRNAggZL"
    ) in announcement
    assert 'target="_blank"' in announcement
    assert 'rel="noopener noreferrer"' in announcement
    assert "Bug 列表 - 0.5 期" in announcement
    assert "button" not in announcement
    assert ".maintenance-announcement" in style_css
    assert "body.has-review > header .topbar { display: none; }" in review_css
