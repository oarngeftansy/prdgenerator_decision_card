from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def test_web_runtime_sources_do_not_expose_removed_brand_name():
    runtime_sources = (
        ROOT / "index.html",
        ROOT / "js" / "feishu-publish.js",
        ROOT / "js" / "app.js",
        ROOT / "js" / "ai.js",
        ROOT / "backend" / "server.py",
        ROOT / "backend" / "__init__.py",
    )

    leaks = [
        str(path.relative_to(ROOT)) for path in runtime_sources
        if re.search(r"言灵[·・•\s_-]*镜瞳", path.read_text(encoding="utf-8"))
    ]
    assert leaks == []


def test_header_removes_legacy_logo_and_uses_neutral_product_title():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    assert '<div class="logo">' not in html
    assert "瞳" not in html
    assert "<b>ai策划案工具</b>" in html
    assert "<title>ai策划案工具｜移动端交互与玩法策划案</title>" in html
