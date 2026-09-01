from backend.calibration.whiteboard_parser import parse_whiteboard


def test_connector_preserves_direction():
    raw = [
        {"id": "a", "type": "text_shape", "text": "玩法主界面"},
        {"id": "b", "type": "text_shape", "text": "挑战失败"},
        {"id": "e", "type": "connector", "start": {"id": "a"}, "end": {"id": "b"}},
    ]
    graph = parse_whiteboard(raw, "ux")
    assert graph["edges"][0]["from"] == "a"
    assert graph["edges"][0]["to"] == "b"


def test_unresolved_connector_is_diagnostic():
    graph = parse_whiteboard([{"id": "e", "type": "connector"}], "ux")
    assert graph["diagnostics"]["unresolvedEdges"] == ["e"]
