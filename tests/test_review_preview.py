from pathlib import Path

from fastapi.testclient import TestClient

from backend import server
from backend.review_preview import build_completion_snapshot, build_review_preview, repair_utf8_mojibake
from tests.review_fixtures import make_confirmed_job


def test_preview_uses_confirmed_review_model_and_reports_warning_without_blocking(tmp_path):
    job = make_confirmed_job()
    (tmp_path / "frames").mkdir()
    for frame in job["frames"]:
        frame["imagePath"] = f"frames/{frame['id']}.png"
        (tmp_path / frame["imagePath"]).write_bytes(b"\x89PNG\r\n\x1a\npreview")
    job["reviewModel"]["crossStateConstraints"] = [{
        "id": "CST-001", "text": "弱网反馈待确认", "severity": "non_core", "status": "unknown",
    }]

    preview = build_review_preview(job, tmp_path)

    assert preview["exportReady"] is True
    assert preview["warningIds"] == ["CST-001"]
    assert preview["representativeFrameIds"] == ["F0001", "F0002"]
    assert preview["referenceBoardSummary"] == [
        {"key": "planning", "assetCount": 2, "missingCount": 0, "status": "generated"},
    ]
    assert "ruleDomainSummary" not in preview
    assert preview["planningModel"]["standard"] == "GVE16"
    assert preview["planningModel"]["project"]["sourceType"] == "image_sequence"
    assert preview["boardPreviewSvg"].startswith("<svg")
    assert preview["boardPreviewSvg"].count('data-node-kind="page-screenshot"') == 2
    assert preview["boardPreviewSvg"].count("data:image/png;base64,") == 2


def test_preview_blocks_when_a_representative_media_file_is_missing(tmp_path):
    job = make_confirmed_job()
    preview = build_review_preview(job, tmp_path)

    assert preview["exportReady"] is False
    assert preview["blockerIds"] == ["MEDIA_F0001", "MEDIA_F0002"]
    assert job["reviewModel"]["reviewState"]["previewRevision"] is None


def test_preview_repairs_double_decoded_utf8_without_changing_valid_chinese():
    assert repair_utf8_mojibake("æ­¦å¨升级选择") == "武器升级选择"
    assert repair_utf8_mojibake("武器升级选择") == "武器升级选择"


def test_board_copy_drops_isolated_symbols_and_truncated_field_fragments():
    from backend.feishu_render import _page_copy_lines

    for fragment in ("/", "||", "级", "伤害-", "次数:/", "见上方说明", "本页未单独展示"):
        assert _page_copy_lines(fragment, 30) == []


def test_board_svg_omits_redundant_information_card_for_single_screenshot_pages(tmp_path):
    job = make_confirmed_job()
    (tmp_path / "frames").mkdir()
    for frame in job["frames"]:
        frame["imagePath"] = f"frames/{frame['id']}.png"
        (tmp_path / frame["imagePath"]).write_bytes(b"\x89PNG\r\n\x1a\npreview")

    svg = build_review_preview(job, tmp_path)["boardPreviewSvg"]

    assert 'data-node-kind="page-screenshot"' in svg
    assert 'data-node-kind="page-screenshot-detail"' not in svg


def test_board_svg_keeps_independent_information_cards_for_multi_screenshot_page(tmp_path):
    job = make_confirmed_job()
    first, second = job["reviewModel"]["stages"]
    first["name"] = second["name"] = "载具养成"
    first["objective"] = second["objective"] = "提升载具能力"
    (tmp_path / "frames").mkdir()
    for frame in job["frames"]:
        frame["imagePath"] = f"frames/{frame['id']}.png"
        (tmp_path / frame["imagePath"]).write_bytes(b"\x89PNG\r\n\x1a\npreview")

    svg = build_review_preview(job, tmp_path)["boardPreviewSvg"]

    assert svg.count('data-node-kind="page-screenshot-detail"') == 2


def test_stale_preview_blocks_publish(monkeypatch):
    job = make_confirmed_job()
    job["reviewModel"]["reviewState"]["previewRevision"] = job["reviewModel"]["revision"] - 1
    monkeypatch.setattr(server.storage, "mutate_job", lambda _job_id, mutation: mutation(job))

    client = TestClient(server.app)
    response = client.post(f"/api/jobs/{job['id']}/feishu/publish", json={"requestId": "req-00000001", "mode": "reuse"})

    assert response.status_code == 409
    assert "重新生成导出预览" in response.json()["detail"]


def test_preview_rejects_stale_compare_and_set_revision(monkeypatch):
    job = make_confirmed_job()
    monkeypatch.setattr(server, "load_job", lambda _job_id: job)
    monkeypatch.setattr(server.storage, "mutate_job", lambda _job_id, mutation: mutation(job))
    client = TestClient(server.app)

    response = client.post(f"/api/jobs/{job['id']}/review-model/preview", json={"expectedRevision": job["reviewModel"]["revision"] - 1})

    assert response.status_code == 409
    assert response.json()["detail"]["currentRevision"] == job["reviewModel"]["revision"]


def test_completion_snapshot_is_the_single_export_and_percentage_source():
    job = {
        "reviewModel": {"revision": 2, "reviewState": {"previewRevision": 2}, "stages": [{"confirmation": {"confirmed": True}}]},
        "gameplayReviewModel": {
            "revision": 3,
            "directory": {"understanding": {"summary": "玩法"}},
            "chapters": [{"id": "C1", "confirmation": {"confirmed": True}, "parameterSchema": [], "decisionCards": []}],
            "tables": [], "diagrams": [], "diagramReview": {"noDiagramChapterIds": ["C1"]},
        },
    }
    preview = {"blockerIds": [], "planningBoardPreviewSvg": "<svg/>", "languageAudit": {"passed": True}, "granularityAudit": {"passed": True}, "deliveryAlignment": {"passed": True}}

    ready = build_completion_snapshot(job, preview)
    assert ready["ready"] is True
    assert ready["percent"] == 100
    assert all(item["done"] for item in ready["checks"])
    assert ready["steps"][-1] == {"id": "export", "label": "文档导出", "done": True}
    assert [item["id"] for item in ready["steps"]] == ["understanding", "directory", "interaction", "rules", "diagrams", "tables", "export"]
    assert [item["id"] for item in ready["checks"]].index("diagrams") < [item["id"] for item in ready["checks"]].index("tables")

    job["gameplayReviewModel"]["chapters"][0]["decisionCards"] = [{"status": "pending"}]
    blocked = build_completion_snapshot(job, preview)
    assert blocked["ready"] is False
    assert blocked["percent"] < 100
    assert next(item for item in blocked["checks"] if item["id"] == "decisions")["done"] is False
    assert blocked["steps"][-1]["done"] is False
