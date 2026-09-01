from backend.calibration.document_parser import parse_document


def test_parse_document_keeps_heading_and_table_provenance():
    source = "# 玩法说明\n规则正文\n|字段|内容|\n|-|-|\n|触发|升级后|"
    result = parse_document(source)
    assert result["chapters"][0]["title"] == "玩法说明"
    assert result["tables"][0]["rows"][0] == {"字段": "触发", "内容": "升级后"}
    assert result["rules"][0]["sourceRef"]["sourceType"] == "document"


def test_parse_document_extracts_whiteboard_tokens():
    result = parse_document('# UE\n<whiteboard token="abc"></whiteboard>')
    assert result["media"] == [{"type": "whiteboard", "token": "abc", "locator": "UE"}]

