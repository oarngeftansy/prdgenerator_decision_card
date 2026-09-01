from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_browser_qa_covers_the_two_board_confirmation_and_preview_journey():
    script = (ROOT / "tools" / "review-workspace-browser-qa.js").read_text(encoding="utf-8")

    assert 'workflowCalls, ["flow", "STG-001", "STG-002", "preview"]' in script
    assert 'data-review-view="rules"' not in script
    assert "rulesReviewView" not in script
    assert "ReferenceBoardAssets.render" in script
    assert "待补充" in script
    assert "uploadBoardAssets" in script
    assert "reorderBoardAssets" in script
    assert "deleteBoardAsset" in script
    assert "retry competitor asset" in script
    assert "current preview revision" in script
    assert "componentChecks" in script
    assert "exactly two active board cards" in script
    assert "no UX upload control" in script
    assert "stale preview revision" in script


def test_browser_qa_captures_the_final_mobile_workspace_and_checks_layout_safety():
    script = (ROOT / "tools" / "review-workspace-browser-qa.js").read_text(encoding="utf-8")

    assert "--screenshot" in script
    assert "page.screenshot" in script
    assert "scrollWidth <= window.innerWidth" in script
    assert "writingMode" in script
    assert "44px" in script
    assert "visible loading state" in script
    assert "visible error state" in script
    assert "visible disabled state" in script
    assert "focusVisible" in script
    assert "getBoundingClientRect" in script


def test_seeded_live_backend_edge_path_uses_real_review_and_asset_apis_only_mocking_feishu():
    seeder = (ROOT / "tools" / "seed-review-workspace-live-qa.py").read_text(encoding="utf-8")
    script = (ROOT / "tools" / "review-workspace-live-browser-qa.js").read_text(encoding="utf-8")

    assert "make_confirmed_job" in seeder
    assert "save_job" in seeder
    assert "confirm-flow" in script
    assert "confirm-stage" in script
    assert "/preview" in script
    assert "reference-boards/ux/assets" in script
    assert "legacy UX mutation is rejected" in script
    assert "stale competitor mutation exposes retry" in script
    assert "successful retry persists competitor assets" in script
    assert "feishu/publish" in script
    assert script.count("page.route(") == 1


def test_new_gameplay_classic_scripts_isolate_helpers_from_window_globals():
    for filename in (
        "gameplay-workspace.js", "gameplay-review.js", "gameplay-mechanism-forms.js", "gameplay-review-client.js",
    ):
        script = (ROOT / "js" / filename).read_text(encoding="utf-8")
        assert "(function" in script
        assert "window.Gameplay" in script or "root.Gameplay" in script


def test_gameplay_browser_qa_covers_restoration_full_journey_and_safe_publish_mock():
    script = (ROOT / "tools" / "run_gameplay_review_browser_qa.js").read_text(encoding="utf-8")

    for marker in (
        "interaction preview", "gameplay generation", "chapter edit",
        "mechanism field switching", "evidence drawer closed",
        "targeted context success", "targeted context needs-location",
        "chapter confirmation", "diagram regeneration", "diagram approval",
        "final preview", "matching revisions", "restored selected chapter",
    ):
        assert marker in script
    assert "1440" in script and "900" in script
    assert "390" in script and "844" in script
    assert "scrollWidth <= window.innerWidth" in script
    assert "writingMode" in script
    assert "44px" in script
    assert "focusVisible" in script
    assert "consoleErrors" in script
    assert "feishu/publish" in script
    assert script.count("page.route(") == 1
    assert '.context("GCH-' not in script
    assert '.confirmChapter("GCH-' not in script
    for screenshot in (
        "desktop-gameplay-1440x900.png", "desktop-diagrams-1440x900.png", "desktop-final-1440x900.png",
        "mobile-gameplay-390x844.png", "mobile-diagrams-390x844.png", "mobile-final-390x844.png",
    ):
        assert screenshot in script
    assert "gameplay-context-button" in script
    assert "data-gameplay-decision" in script
