from pathlib import Path

from backend.server import accepted_planning_preview_data, accepted_planning_preview_page


def test_accepted_planning_preview_exposes_final_document_sketch_and_line_crosswalk():
    response = accepted_planning_preview_page()
    assert str(response.path).endswith("accepted-planning-preview.html")
    payload = accepted_planning_preview_data()
    assert payload["publicationState"] == "published"
    assert "# 一路狂飙·执行策划案" in payload["planningMarkdown"]
    assert "Human Planning Preview" not in payload["planningMarkdown"]
    assert "首领以载具为唯一攻击目标" in payload["planningMarkdown"]
    assert "首领生命值归零与载具生命值归零在同一结算步成立时，失败判定优先" in payload["planningMarkdown"]
    assert "# 一路狂飙·策划草图" in payload["planningSketchMarkdown"]
    assert payload["bodyCrosswalk"]["lines"]
    assert all(item["renderedFinalText"] for item in payload["bodyCrosswalk"]["lines"])
    assert payload["integrity"]["reviewLanguageTerms"] == []
    assert len(payload["p5Diagrams"]) == 5
    assert len(payload["p6Tables"]) == 6
    assert [item["key"] for item in payload["nativeBoards"]] == ["planning"]
    assert all(item["svg"].startswith("<svg") for item in payload["nativeBoards"])
    assert payload["nativeBoardAcceptance"]["uePages"] == list(range(1, 10))
    assert all(numbers == [1, 2, 3, 4] for numbers in payload["nativeBoardAcceptance"]["ueComponentMarkers"].values())


def test_accepted_preview_frontend_renders_both_delivery_carriers():
    script = Path("js/accepted-planning-preview.js").read_text(encoding="utf-8")
    assert "planningMarkdown" in script
    assert "planningSketchMarkdown" in script
    assert "bodyCrosswalk" in script
    assert "GVE16 逐行职责核对" in script
    assert "renderTable" in script
    assert "p5Diagrams" in script
    assert "p6Tables" in script
    assert "nativeBoards" in script
    assert 'nativeBoard(boards.planning, "策划草图")' in script
    assert 'nativeBoard(boards.ue, "UE 流转图")' not in script
    assert 'nativeBoard(boards.competitor, "竞品参考")' not in script
    assert 'embed[1] === "BOARD" && ["ue", "competitor"].includes(embed[2])' in script
    assert 'new URLSearchParams(location.search).get("tab")' in script
    assert 'classList.toggle("flow-wide"' in script
    assert 'document.getElementById("score")' not in script
