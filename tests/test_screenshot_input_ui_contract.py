from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_screenshot_first_controls_and_accessibility_contract():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "css" / "style.css").read_text(encoding="utf-8") + (ROOT / "css" / "review-workspace.css").read_text(encoding="utf-8")
    assets = (ROOT / "js" / "assets.js").read_text(encoding="utf-8")
    app = (ROOT / "js" / "app.js").read_text(encoding="utf-8")

    assert 'id="screenshotFolderInput"' in html
    assert "webkitdirectory" in html and "directory" in html
    assert 'id="auxVideoInput"' in html
    assert 'id="screenshotPreviewList"' in html
    assert 'id="screenshotValidation"' in html and 'aria-live="polite"' in html
    assert "上移" in assets and 'data-action="up"' in assets
    assert "下移" in assets and 'data-action="down"' in assets
    assert ".screenshot-preview-item" in css
    assert ":focus-visible" in css
    assert "max-width: 700px" in css
    desktop_css = css.split("@media", 1)[0]
    assert "grid-template-columns: 32px 56px minmax(0, 1fr)" in desktop_css
    assert ".screenshot-order-actions { grid-column: 1 / -1;" in desktop_css
    assert "上传有序截图" in html
    assert "开始截图分析" in html
    assert 'js/backend.js?v=ux103' in html
    assert 'js/gameplay-review.js?v=gameplay27' in html
    assert 'js/flow-review.js?v=review19' in html
    assert 'js/stage-review.js?v=review22' in html
    assert "上传移动端演示视频" not in html
    assert "全片扫描与场景补帧" not in html
    assert 'rel="icon"' in html
    assert 'id="reviewWorkspace"' in html
    assert 'id="flowReviewView"' in html
    assert 'id="stageReviewView"' in html
    assert 'id="exportPreviewView"' in html
    assert 'id="analysisFailedView"' in html
    assert "review-workspace.css" in html
    assert "review-client.js" in html and "review-workspace.js" in html
    assert ".workspace.has-review" in css
    assert ".review-canvas { min-height: 0; overflow-y: auto; overflow-x: hidden;" in css
    assert "body.has-review { overflow-x: hidden; }" in css
    assert ".review-workspace-body { grid-template-columns: 1fr; grid-template-rows: auto minmax(0, 1fr); min-height: 0; overflow: hidden; }" in css
    assert ".review-workspace { grid-template-rows: auto minmax(0, 1fr); }" not in css
    assert "await extractFrames();" not in app
    assert "无法连接统一分析服务" in app
