from pathlib import Path
import re

import pytest

from backend.feishu_cli import LarkCommandError, LarkResult
from backend.feishu_publish import (
    FeishuPublisher,
    PublicationConflict,
    _board_checkpoint,
    _document_whiteboard_identity,
    _preview_svg_fast_path_allowed,
    _raw_board_has_content,
    _raw_board_has_expected_images,
    _structure_without_pending_images,
    _token_backed_image_node,
    _whiteboard_tokens,
)
from backend.feishu_render import render_feishu_document


def test_document_whiteboard_identity_accepts_renderer_figure_heading_prefix():
    content = (
        '<h4>图示：UE 流转图</h4><whiteboard token="board-ue"></whiteboard>'
        '<h4>图示：策划草图</h4><whiteboard token="board-planning"></whiteboard>'
        '<h4>图示：竞品参考</h4><whiteboard token="board-competitor"></whiteboard>'
    )

    tokens, mapping = _document_whiteboard_identity(
        {"content": content}, ("UE 流转图", "策划草图", "竞品参考")
    )

    assert tokens == ["board-ue", "board-planning", "board-competitor"]
    assert mapping == {
        "UE 流转图": ["board-ue"],
        "策划草图": ["board-planning"],
        "竞品参考": ["board-competitor"],
    }


def test_token_backed_image_is_forced_above_section_backgrounds():
    image = {
        "id": "planning-image-choice-1",
        "type": "image",
        "x": 32,
        "y": 248,
        "width": 210,
        "height": 374,
    }

    rendered = _token_backed_image_node(image, "media-token")

    assert rendered["z_index"] >= 1000


def test_preview_svg_fast_path_rejects_screenshot_rich_boards():
    board_with_image = type("Board", (), {"images": [object()]})()
    image_free_board = type("Board", (), {"images": []})()
    small_svg = '<svg width="1200" height="800"></svg>'

    assert _preview_svg_fast_path_allowed(small_svg, image_free_board) is True
    assert _preview_svg_fast_path_allowed(small_svg, board_with_image) is False


def test_remote_media_verification_rejects_zero_size_svg_image_shells():
    stripped_svg_shell = {
        "nodes": [{
            "type": "image", "width": 0, "height": 0,
            "image": {"token": "<svg><image href='data:image/jpeg;base64,...'/></svg>"},
        }]
    }
    native_image = {
        "nodes": [{
            "type": "image", "width": 170, "height": 320,
            "image": {"token": "feishu-media-token"},
        }]
    }

    assert _raw_board_has_expected_images(stripped_svg_shell, 1) is False
    assert _raw_board_has_expected_images(native_image, 1) is True


def test_raw_board_rejects_image_hidden_below_overlapping_section():
    raw = {
        "nodes": [
            {
                "id": "image-1",
                "type": "image",
                "x": 32,
                "y": 248,
                "width": 210,
                "height": 374,
                "z_index": 0,
                "image": {"token": "media-token"},
            },
            {
                "id": "section-1",
                "type": "section",
                "x": 0,
                "y": 100,
                "width": 900,
                "height": 760,
                "z_index": 2,
            },
        ]
    }

    assert _raw_board_has_content(raw) is False


def test_structure_write_removes_pending_images_from_section_children():
    structure = {
        "nodes": [
            {
                "id": "section-1",
                "type": "section",
                "children": ["copy-1", "image-1"],
            },
            {"id": "copy-1", "type": "text_shape", "text": {"text": "说明"}},
            {"id": "image-1", "type": "image", "x": 32, "y": 248, "width": 210, "height": 374},
        ]
    }

    rendered = _structure_without_pending_images(structure)
    section = next(node for node in rendered["nodes"] if node["type"] == "section")

    assert len(section["children"]) == 1


def test_unverified_board_with_all_media_claimed_complete_requires_clean_rebuild():
    publisher = FeishuPublisher(FakeCli(), Path("data/jobs/job-publish"))
    board = type("Board", (), {
        "images": [type("Image", (), {"node": {"id": "page-image-1"}})()]
    })()
    checkpoint = {
        "boardVerified": {"planning": False},
        "boardMediaNodesDone": {"planning": {"page-image-1": "media-token"}},
    }

    assert publisher._requires_clean_board_rebuild(checkpoint, "planning", board) is True


class FakeCli:
    def __init__(self, fail_media_once=False, create_without_token=False, board_not_ready_once=False, transient_media_read_once=False, board_unknown_id_once=False):
        self.calls = []
        self.current_revision = 7
        self.fail_media_once = fail_media_once
        self.create_without_token = create_without_token
        self.document_created = False
        self.board_not_ready_once = board_not_ready_once
        self.board_unknown_id_once = board_unknown_id_once
        self.transient_media_read_once = transient_media_read_once
        self.created_title = "Demo"
        self.board_tokens = ["board-planning"]
        self.fail_board_key_once = ""
        self.structure_update_counts = {}
        self.image_update_counts = {}
        self.empty_board_key = ""
        self.fetched_content = ""
        self.fetched_payload = None
        self.rotate_board_tokens_on_update = False

    def board_key(self, args):
        token = args[args.index("--whiteboard-token") + 1]
        keys = ("ux", "planning", "competitor") if len(self.board_tokens) == 3 else (("planning", "competitor") if len(self.board_tokens) == 2 else ("planning",))
        return {value: key for key, value in zip(keys, self.board_tokens)}.get(token, token)

    def auth_status(self):
        return {"identity": "user", "verified": True, "identities": {"user": {"status": "valid"}}}

    def run(self, args, stdin=None):
        self.calls.append((args, stdin))
        command = " ".join(args[:3])
        if args[:3] == ["drive", "files", "list"] and "--folder-token" in args and self.document_created:
            return LarkResult({"files": [{"name": self.created_title, "token": "doc-1", "url": "https://feishu.cn/docx/doc-1", "type": "docx"}]}, {"ok": True})
        if args[:3] == ["drive", "files", "list"]:
            if "--folder-token" in args and self.document_created:
                return LarkResult({"files": [{"name": "Demo｜玩法策划案｜2026-07-22", "token": "doc-1", "url": "https://feishu.cn/docx/doc-1", "type": "docx"}]}, {"ok": True})
            return LarkResult({"files": []}, {"ok": True})
        if args[:2] == ["drive", "+create-folder"]:
            return LarkResult({"token": "folder-1"}, {"ok": True})
        if args[:2] == ["docs", "+create"]:
            self.document_created = True
            match = re.search(r"<title>(.*?)</title>", stdin or "")
            if match:
                self.created_title = match.group(1)
            if self.create_without_token:
                return LarkResult({"revision_id": 7}, {"ok": True})
            return LarkResult({"document_id": "doc-1", "url": "https://feishu.cn/docx/doc-1", "revision_id": 7, "whiteboard_tokens": self.board_tokens}, {"ok": True})
        if args[:2] == ["docs", "+fetch"]:
            if self.fetched_payload is not None:
                return LarkResult(self.fetched_payload, {"ok": True})
            titles = ["UX设计", "策划草图", "竞品参考"] if len(self.board_tokens) == 3 else (["策划草图", "竞品参考"] if len(self.board_tokens) == 2 else ["策划草图"])
            default_content = "".join(
                f'<h2>{title}</h2><whiteboard token="{token}"></whiteboard>'
                for title, token in zip(titles, self.board_tokens)
            )
            return LarkResult({"revision_id": self.current_revision, "content": self.fetched_content or default_content, "whiteboard_tokens": self.board_tokens}, {"ok": True})
        if args[:2] == ["docs", "+update"]:
            self.current_revision += 1
            if self.rotate_board_tokens_on_update and "overwrite" in args:
                self.board_tokens = [f"{token}-v2" for token in self.board_tokens]
            return LarkResult({"revision_id": self.current_revision}, {"ok": True})
        if args[:2] == ["docs", "+media-upload"]:
            if self.transient_media_read_once:
                self.transient_media_read_once = False
                raise LarkCommandError("command_failed", 'API call failed: Get "https://open.feishu.cn/open-apis/docx/v1/documents/doc-1/blocks/doc-1": EOF')
            if self.fail_media_once:
                self.fail_media_once = False
                raise LarkCommandError("command_failed", "media failed")
            return LarkResult({"file_token": "board-image-1"}, {"ok": True})
        if args[:2] == ["whiteboard", "+query"]:
            if self.board_key(args) == self.empty_board_key:
                return LarkResult({"nodes": []}, {"ok": True})
            if self.board_not_ready_once:
                self.board_not_ready_once = False
                raise LarkCommandError("command_failed", "doc data is not ready")
            if self.board_unknown_id_once:
                self.board_unknown_id_once = False
                raise LarkCommandError("unknown", "unknown idType [@from@] arg error [@from@] whiteboard")
            image_count = self.image_update_counts.get(self.board_key(args), 0)
            return LarkResult({
                "code": "flowchart LR\nA-->B",
                "nodes": [{"type": "text_shape", "text": {"text": "board"}}] + [{
                    "type": "image", "width": 170, "height": 320, "z_index": 1000,
                    "image": {"token": "board-image-1"},
                } for _ in range(image_count)],
            }, {"ok": True})
        if args[:2] == ["whiteboard", "+update"]:
            key = self.board_key(args)
            if "--overwrite" in args:
                self.structure_update_counts[key] = self.structure_update_counts.get(key, 0) + 1
                if key == self.fail_board_key_once:
                    self.fail_board_key_once = ""
                    raise LarkCommandError("command_failed", "board structure failed")
            elif stdin and '"type": "image"' in stdin:
                self.image_update_counts[key] = self.image_update_counts.get(key, 0) + 1
            return LarkResult({"updated": True}, {"ok": True})
        raise AssertionError(args)

    def count(self, prefix):
        expected = prefix.split()
        return sum(args[: len(expected)] == expected for args, _ in self.calls)


def _job(mode: str = "interaction") -> dict:
    flow_key = "gameplay" if mode == "gameplay" else "interaction"
    flow_name = "coreLoop" if mode == "gameplay" else "taskFlow"
    return {
        "id": "job-publish",
        "status": "completed",
        "metadata": {"mode": mode, "projectName": "Demo"},
        "frames": [{"id": "F0001", "timestamp": 1.0, "imagePath": "frames/F0001.jpg"}],
        "planningModel": {
            "standard": "GVE16", "mode": mode, "project": {"name": "Demo", "scope": "完整还原"},
            "scenes": [],
            "events": [{"id": "EVT-001", "action": "点击", "response": "开始", "evidence": [{"sourceId": "F0001"}]}],
            flow_key: {flow_name: []},
            "designHandoff": {"flowEdges": [{"id": "FLOW-001", "from": "菜单", "to": "关卡", "trigger": "点击"}]},
            "quality": {"score": 90},
        },
    }


def test_first_publish_creates_one_folder_and_one_document():
    cli = FakeCli()
    job = _job()

    record = FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-00000001", "update")

    assert cli.count("drive +create-folder") == 1
    assert cli.count("docs +create") == 1
    assert record.status == "published"
    assert job["feishuPublication"]["documentToken"] == "doc-1"


def test_approval_guard_stops_before_the_next_external_write():
    cli = FakeCli()
    calls = []

    def guard():
        calls.append("checked")
        if len(calls) == 3:
            raise PublicationConflict("review approval changed")

    with pytest.raises(PublicationConflict, match="approval changed"):
        FeishuPublisher(cli, Path("data/jobs/job-publish"), approval_guard=guard).publish(_job(), "req-guard-0001", "update")

    assert cli.count("drive +create-folder") == 1
    assert cli.count("docs +create") == 1
    assert cli.count("whiteboard +update") == 0
    assert cli.count("docs +media-upload") == 0


def test_approval_guard_is_checked_before_each_media_upload_attempt():
    cli = FakeCli()
    checks = 0

    def guard():
        nonlocal checks
        checks += 1
        if checks == 4:
            raise PublicationConflict("review approval changed before upload")

    with pytest.raises(PublicationConflict, match="before upload"):
        FeishuPublisher(cli, Path("data/jobs/job-publish"), approval_guard=guard).publish(
            _job(), "req-guard-0002", "update"
        )

    assert cli.count("whiteboard +update") == 1
    assert cli.count("docs +media-upload") == 0


def test_create_recovers_document_from_folder_when_cli_response_omits_token():
    cli = FakeCli(create_without_token=True)
    job = _job()

    record = FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-00000009", "update")

    assert record.document_token == "doc-1"
    assert job["feishuPublication"]["documentUrl"] == "https://feishu.cn/docx/doc-1"


def test_retry_with_same_request_reuses_resources():
    cli = FakeCli()
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))

    first = publisher.publish(job, "req-00000002", "update")
    second = publisher.publish(job, "req-00000002", "update")

    assert second.document_token == first.document_token
    assert cli.count("docs +create") == 1


def test_same_request_republishes_when_the_delivery_fingerprint_changes():
    cli = FakeCli()
    cli.rotate_board_tokens_on_update = True
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))
    publisher.publish(job, "req-content-change", "update")
    job["planningModel"]["events"][0]["response"] = "进入已修订关卡"

    result = publisher.publish(job, "req-content-change", "update")

    assert result.status == "published"
    assert cli.count("docs +create") == 1
    assert cli.count("docs +update") == 1
    assert cli.structure_update_counts == {"planning": 2}
    planning_structure_tokens = [
        args[args.index("--idempotent-token") + 1]
        for args, _ in cli.calls
        if args[:2] == ["whiteboard", "+update"]
        and "--overwrite" in args
        and "planning" in args[args.index("--whiteboard-token") + 1]
    ]
    assert len(planning_structure_tokens) == 2
    assert len(set(planning_structure_tokens)) == 2


def test_content_change_invalidates_verified_boards_when_document_reuses_tokens():
    cli = FakeCli()
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))
    publisher.publish(job, "req-content-same-tokens", "update")
    first_uploads = cli.count("docs +media-upload")
    job["planningModel"]["events"][0]["response"] = "进入同一文档中的修订关卡"

    result = publisher.publish(job, "req-content-same-tokens", "update")

    assert result.status == "published"
    assert cli.structure_update_counts == {"planning": 2}
    assert cli.count("docs +media-upload") == first_uploads + 1
    assert job["feishuPublication"]["boardMediaNodesDone"]["planning"] == {
        "page-image-legacy-EVT-001-1": "board-image-1"
    }


def test_external_revision_change_blocks_overwrite():
    cli = FakeCli()
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))
    publisher.publish(job, "req-00000003", "update")
    cli.current_revision += 1
    job["planningModel"]["events"][0]["response"] = "进入第二关"

    with pytest.raises(PublicationConflict):
        publisher.publish(job, "req-00000004", "update")

    assert job["feishuPublication"]["status"] == "conflict"


def test_partial_board_media_failure_reuses_document_on_retry():
    cli = FakeCli(fail_media_once=True)
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))

    with pytest.raises(LarkCommandError):
        publisher.publish(job, "req-00000005", "update")
    assert job["feishuPublication"]["status"] == "partial"

    result = publisher.publish(job, "req-00000005", "update")

    assert result.status == "published"
    assert cli.count("docs +create") == 1
    assert cli.count("docs +media-insert") == 0
    assert cli.count("docs +media-upload") == 2


def test_transient_board_media_read_eof_recovers_without_partial_state():
    cli = FakeCli(transient_media_read_once=True)
    waits = []
    job = _job()

    result = FeishuPublisher(cli, Path("data/jobs/job-publish"), wait=waits.append).publish(
        job, "req-00000014", "update"
    )

    assert result.status == "published"
    assert cli.count("docs +media-insert") == 0
    assert cli.count("docs +media-upload") == 2
    assert waits == [1]


def test_partial_retry_recovers_created_document_when_saved_token_is_invalid():
    cli = FakeCli()
    cli.document_created = True
    job = _job()
    cli.created_title = render_feishu_document(job, Path("data/jobs/job-publish")).title
    job["feishuPublication"] = {
        "status": "partial", "requestId": "req-00000010", "folderToken": "folder-1",
        "documentToken": "None", "fingerprint": "stale", "mediaDone": [],
    }

    result = FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-00000010", "update")

    assert result.document_token == "doc-1"
    assert cli.count("docs +create") == 0


def test_new_version_creates_a_new_document():
    cli = FakeCli()
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))
    publisher.publish(job, "req-00000006", "update")

    publisher.publish(job, "req-00000007", "new_version")

    assert cli.count("docs +create") == 2
    assert len(job["feishuPublicationHistory"]) == 1
    assert cli.structure_update_counts == {"planning": 2}


def test_document_overwrite_resets_active_boards_but_keeps_legacy_ux_checkpoint():
    cli = FakeCli()
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))
    publisher.publish(job, "req-overwrite-0001", "update")
    job["feishuPublication"]["boardVerified"]["ux"] = "legacy-verified"
    job["planningModel"]["events"][0]["action"] = "changed action"

    publisher.publish(job, "req-overwrite-0002", "update")

    assert cli.structure_update_counts == {"planning": 2}
    assert job["feishuPublication"]["boardVerified"]["ux"] == "legacy-verified"


def test_document_overwrite_clears_legacy_flat_board_media_checkpoint():
    snapshots = []
    cli = FakeCli()
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"), save=lambda publication, history: snapshots.append(publication))
    publisher.publish(job, "req-flat-media-0001", "update")
    job["feishuPublication"]["boardMediaDone"] = {"F0001": "legacy-media-token"}
    job["planningModel"]["events"][0]["action"] = "changed action"
    changed_fingerprint = render_feishu_document(job, Path("data/jobs/job-publish")).content_fingerprint

    publisher.publish(job, "req-flat-media-0002", "update")

    reset = next(snapshot for snapshot in snapshots if snapshot.get("fingerprint") == changed_fingerprint)

    assert reset["boardMediaDone"] == {}


def test_absolute_job_directory_is_converted_to_safe_relative_media_argument():
    cli = FakeCli()
    job = _job()

    FeishuPublisher(cli, Path.cwd() / "data/jobs/job-publish").publish(job, "req-00000008", "update")

    media_args = next(args for args, _ in cli.calls if args[:2] == ["docs", "+media-upload"])
    value = media_args[media_args.index("--file") + 1]
    assert not Path(value).is_absolute()
    assert ".." not in Path(value).parts


def test_whiteboard_token_is_extracted_from_fetched_document_xml():
    fetched = {"document": {"content": '<h1>UE 流转图</h1><whiteboard token="board-real" type="mermaid">flowchart LR</whiteboard>'}}

    assert _whiteboard_tokens(fetched) == ["board-real"]


def test_whiteboard_token_is_extracted_from_new_document_blocks():
    imported = {
        "document": {
            "new_blocks": [
                {"block_type": "whiteboard", "block_token": "board-real"},
                {"block_type": "paragraph", "block_token": "paragraph-token"},
            ]
        }
    }

    assert _whiteboard_tokens(imported) == ["board-real"]


def test_only_event_representatives_are_uploaded_to_whiteboard():
    cli = FakeCli()
    job = _job()
    job["frames"].extend(
        {"id": f"F{index:04d}", "timestamp": float(index), "imagePath": f"frames/F{index:04d}.jpg"}
        for index in range(2, 138)
    )
    representative_ids = ["F0007", "F0021", "F0043", "F0064", "F0081", "F0111", "F0136"]
    job["planningModel"]["events"] = [
        {"id": f"EVT-{index:03d}", "action": "点击", "response": "切换", "evidence": [{"sourceId": frame_id}]}
        for index, frame_id in enumerate(representative_ids, 1)
    ]

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-00000011", "update")

    uploads = [args for args, _ in cli.calls if args[:2] == ["docs", "+media-upload"]]
    assert cli.count("docs +media-insert") == 0
    assert len(uploads) == 7
    assert [Path(args[args.index("--file") + 1]).stem for args in uploads] == representative_ids


def test_publisher_overwrites_structure_then_adds_token_backed_board_image():
    cli = FakeCli()
    job = _job()

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-00000012", "update")

    updates = [call for call in cli.calls if call[0][:2] == ["whiteboard", "+update"]]
    args, source = updates[0]
    assert args[args.index("--input_format") + 1] == "raw"
    assert "--overwrite" in args
    assert args[args.index("--source") + 1] == "-"
    nodes = __import__("json").loads(source)["nodes"]
    assert any(node["type"] == "section" for node in nodes)
    assert not any(node["type"] == "image" for node in nodes)
    assert all(__import__("re").fullmatch(r"[oac]001:\d+", node["id"]) for node in nodes)
    image_payload = next(
        __import__("json").loads(payload) for update_args, payload in updates
        if "--overwrite" not in update_args and '"type": "image"' in payload and '"x"' in payload
    )
    image_node = image_payload["nodes"][0]
    assert image_node["image"]["token"] == "board-image-1"
    assert __import__("re").fullmatch(r"o001:\d+", image_node["id"])
    assert image_node["style"] == {"border_style": "none"}
    assert "crop" not in image_node
    query_args = next(args for args, _ in cli.calls if args[:2] == ["whiteboard", "+query"])
    assert query_args[query_args.index("--output_as") + 1] == "raw"


def test_publisher_does_not_send_an_empty_native_board_overlay():
    cli = FakeCli()

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(
        _job(), "req-empty-overlay", "update"
    )

    raw_updates = [
        __import__("json").loads(payload)
        for args, payload in cli.calls
        if args[:2] == ["whiteboard", "+update"]
        and args[args.index("--input_format") + 1] == "raw"
        and "--overwrite" not in args
        and payload
    ]
    assert raw_updates
    assert all(update.get("nodes") for update in raw_updates)


def test_reused_frame_uploads_once_and_tokens_every_distinct_whiteboard_node():
    cli = FakeCli()
    job = _job()
    job["planningModel"]["events"] = [
        {"id": "EVT-001", "action": "打开强化", "evidence": [{"sourceId": "F0001"}]},
        {"id": "EVT-002", "action": "返回强化", "evidence": [{"sourceId": "F0001"}]},
    ]

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-reused-frame", "update")

    assert cli.count("docs +media-upload") == 1
    image_payloads = [
        __import__("json").loads(payload)["nodes"][0]
        for args, payload in cli.calls
        if args[:2] == ["whiteboard", "+update"]
        and "--overwrite" not in args
        and payload
        and '"type": "image"' in payload
    ]
    assert len(image_payloads) == 2
    assert len({node["id"] for node in image_payloads}) == 2
    assert [node["image"]["token"] for node in image_payloads] == ["board-image-1"] * 2
    assert job["feishuPublication"]["boardMediaNodesDone"]["planning"] == {
        "page-image-legacy-EVT-001-1": "board-image-1",
        "page-image-legacy-EVT-002-1": "board-image-1",
    }


def test_whiteboard_verification_retries_only_when_board_is_not_ready():
    cli = FakeCli(board_not_ready_once=True)

    result = FeishuPublisher(cli, Path("data/jobs/job-publish"), wait=lambda _: None).publish(_job(), "req-00000013", "update")

    assert result.status == "published"
    assert cli.count("whiteboard +query") == 2


def test_whiteboard_verification_retries_transient_unknown_id_type():
    cli = FakeCli(board_unknown_id_once=True)
    waits = []

    result = FeishuPublisher(cli, Path("data/jobs/job-publish"), wait=waits.append)._query_ready_board("board-planning")

    assert result["code"].startswith("flowchart")
    assert cli.count("whiteboard +query") == 2
    assert waits == [1]


def test_publisher_publishes_only_the_planning_board():
    cli = FakeCli()
    job = _job()

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-three-boards", "update")

    saved = job["feishuPublication"]
    assert list(saved["boardTokens"]) == ["planning"]
    assert saved["boardVerified"] == {"planning": True}
    assert saved["boardMediaDone"] == {"planning": {"F0001": "board-image-1"}}
    assert cli.structure_update_counts == {"planning": 1}


def test_gameplay_publisher_does_not_restore_pre_migration_boards():
    cli = FakeCli()
    job = _job("gameplay")

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-gameplay-boards", "update")

    assert list(job["feishuPublication"]["boardTokens"]) == ["planning"]
    assert job["feishuPublication"]["boardVerified"] == {"planning": True}
    assert cli.structure_update_counts == {"planning": 1}


def test_planning_failure_resumes_without_restoring_legacy_boards():
    cli = FakeCli()
    cli.fail_board_key_once = "planning"
    job = _job()
    job["feishuPublication"] = {
        "boardTokens": {"ux": "legacy-ux-board"},
        "boardStructureRequestIds": {"ux": "legacy-ux-request"},
        "boardMediaDone": {"ux": {"legacy-frame": "legacy-media"}},
        "boardVerified": {"ux": False},
    }
    legacy_ux = {
        field: job["feishuPublication"][field]["ux"]
        for field in ("boardTokens", "boardStructureRequestIds", "boardMediaDone", "boardVerified")
    }
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"))

    with pytest.raises(LarkCommandError, match="board structure failed"):
        publisher.publish(job, "req-partial-board", "update")
    first_structure_counts = cli.structure_update_counts.copy()

    publisher.publish(job, "req-partial-board", "update")

    assert cli.count("docs +create") == 1
    assert cli.structure_update_counts["planning"] == first_structure_counts["planning"] + 1
    assert job["feishuPublication"]["boardVerified"]["planning"] is True
    assert {
        field: job["feishuPublication"][field]["ux"]
        for field in legacy_ux
    } == legacy_ux


def test_publisher_rejects_mismatched_document_whiteboard_tokens_before_writing():
    cli = FakeCli()
    cli.board_tokens = ["board-planning", "board-planning"]

    with pytest.raises(LarkCommandError, match="exactly 1"):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(_job(), "req-bad-tokens", "update")

    assert cli.count("whiteboard +update") == 0


def test_publisher_rejects_three_whiteboard_occurrences_even_with_two_unique_tokens():
    cli = FakeCli()
    cli.board_tokens = ["board-planning", "board-competitor", "board-planning"]

    with pytest.raises(LarkCommandError, match="exactly 1"):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(_job(), "req-extra-token", "update")

    assert cli.count("whiteboard +update") == 0


def test_publisher_maps_planning_board_before_an_approved_gameplay_diagram():
    cli = FakeCli()
    cli.board_tokens = ["board-planning", "board-gameplay-diagram"]
    cli.fetched_content = (
        '<h2>策划草图</h2><whiteboard token="board-planning"></whiteboard>'
        '<h3>state_flow</h3><whiteboard token="board-gameplay-diagram"></whiteboard>'
    )
    job = _job("interaction")
    job["gameplayReviewModel"] = {
        "chapters": [{
            "id": "GCH-001", "scope": "Core loop", "status": "approved",
            "confirmation": {"confirmed": True}, "claims": [], "parameters": {},
            "acceptanceCases": [], "unknowns": [],
        }],
        "diagrams": [{
            "id": "GDI-001", "type": "state_flow", "chapterIds": ["GCH-001"],
            "status": "reviewed", "freshness": "current", "svg": "<svg><text>diagram</text></svg>",
        }],
        "reviewState": {},
    }

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-board-count-0003", "update")

    assert job["feishuPublication"]["boardTokens"] == {"planning": "board-planning"}
    assert "board-gameplay-diagram" in job["feishuPublication"]["whiteboardTokens"]


def test_publisher_uses_semantic_board_identity_when_token_list_is_shuffled():
    cli = FakeCli()
    cli.board_tokens = ["board-gameplay-diagram", "board-planning"]
    cli.fetched_content = (
        '<section><h2>策划草图</h2><whiteboard token="board-planning"></whiteboard></section>'
        '<section><h3>state_flow</h3><whiteboard token="board-gameplay-diagram"></whiteboard></section>'
    )
    job = _job("interaction")
    job["gameplayReviewModel"] = {
        "chapters": [{
            "id": "GCH-001", "scope": "Core loop", "status": "approved",
            "confirmation": {"confirmed": True}, "claims": [], "parameters": {},
            "acceptanceCases": [], "unknowns": [],
        }],
        "diagrams": [{
            "id": "GDI-001", "type": "state_flow", "chapterIds": ["GCH-001"],
            "status": "reviewed", "freshness": "current", "svg": "<svg><text>diagram</text></svg>",
        }],
        "reviewState": {},
    }

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-board-order-001", "update")

    assert job["feishuPublication"]["boardTokens"] == {"planning": "board-planning"}


def test_publisher_rejects_duplicate_expected_heading_before_board_write():
    cli = FakeCli()
    cli.board_tokens = ["board-planning", "board-diagram"]
    cli.fetched_content = (
        '<h2>策划草图</h2><whiteboard token="board-planning"></whiteboard>'
        '<h3>策划草图</h3><whiteboard token="board-diagram"></whiteboard>'
    )
    job = _job("interaction")
    job["gameplayReviewModel"] = {
        "chapters": [{"id": "GCH-001", "scope": "Loop", "status": "approved", "confirmation": {"confirmed": True}}],
        "diagrams": [{"id": "GDI-001", "type": "策划草图", "chapterIds": ["GCH-001"], "status": "reviewed", "freshness": "current", "svg": "<svg/>"}],
        "reviewState": {},
    }

    with pytest.raises(LarkCommandError, match="semantic identity is ambiguous"):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-duplicate-heading", "update")

    assert cli.count("whiteboard +update") == 0


def test_publisher_rejects_nested_structured_duplicate_expected_heading():
    cli = FakeCli()
    cli.board_tokens = ["board-planning", "board-diagram"]
    cli.fetched_payload = {
        "revision_id": 7,
        "blocks": [{"type": "whiteboard", "title": "策划草图", "block_token": "board-planning"}],
        "nested": {"items": [
            {"type": "whiteboard", "title": "策划草图", "block_token": "board-diagram"},
        ]},
    }
    job = _job("interaction")
    job["gameplayReviewModel"] = {
        "chapters": [{"id": "GCH-001", "scope": "Loop", "status": "approved", "confirmation": {"confirmed": True}}],
        "diagrams": [{"id": "GDI-001", "type": "state_flow", "chapterIds": ["GCH-001"], "status": "reviewed", "freshness": "current", "svg": "<svg/>"}],
        "reviewState": {},
    }

    with pytest.raises(LarkCommandError, match="semantic identity is ambiguous"):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-structured-duplicate", "update")

    assert cli.count("whiteboard +update") == 0


def test_publisher_rejects_one_token_assigned_to_both_native_titles():
    cli = FakeCli()
    cli.board_tokens = ["board-shared", "board-diagram"]
    cli.fetched_content = (
        '<h2>策划草图</h2><whiteboard token="board-shared"></whiteboard>'
        '<h2>竞品参考</h2><whiteboard token="board-shared"></whiteboard>'
    )

    with pytest.raises(LarkCommandError):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(_job(), "req-cross-title-reuse", "update")

    assert cli.count("whiteboard +update") == 0


def test_publisher_rejects_tokens_without_expected_native_headings():
    cli = FakeCli()
    cli.fetched_content = '<h2>unrelated</h2><whiteboard token="board-planning"></whiteboard>'

    with pytest.raises(LarkCommandError, match="semantic identity is ambiguous"):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(_job(), "req-missing-headings", "update")

    assert cli.count("whiteboard +update") == 0


def test_publisher_rejects_invalid_reviewed_diagram_before_document_write():
    cli = FakeCli()
    job = _job("interaction")
    job["gameplayReviewModel"] = {
        "chapters": [{"id": "GCH-001", "scope": "Loop", "status": "approved", "confirmation": {"confirmed": True}}],
        "diagrams": [{"id": "GDI-001", "type": "state_flow", "chapterIds": ["GCH-001"], "status": "reviewed", "freshness": "current", "svg": '<svg></svg><whiteboard type="raw"></whiteboard>'}],
        "reviewState": {},
    }

    with pytest.raises(ValueError, match="GDI-001:DIAGRAM_RENDER_INVALID"):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-invalid-diagram", "update")

    assert cli.count("docs +create") == 0
    assert cli.count("whiteboard +update") == 0


def test_legacy_single_board_checkpoint_migrates_to_planning_key():
    cli = FakeCli()
    job = _job()
    fingerprint = render_feishu_document(job, Path("data/jobs/job-publish")).content_fingerprint
    job["feishuPublication"] = {
        "status": "partial", "requestId": "req-legacy-board", "folderToken": "folder-1",
        "documentToken": "doc-1", "fingerprint": fingerprint, "boardToken": "board-planning",
        "boardStructureRequestId": "req-legacy-board", "boardMediaDone": {"F0001": "legacy-media"},
    }

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(job, "req-legacy-board", "update")

    assert job["feishuPublication"]["boardTokens"]["planning"] == "board-planning"
    assert job["feishuPublication"]["boardStructureRequestIds"]["planning"] == "req-legacy-board"
    assert job["feishuPublication"]["boardMediaDone"]["planning"] == {"F0001": "legacy-media"}


def test_legacy_three_board_checkpoint_ignores_ux_for_new_completion():
    record = {
        "requestId": "req-old",
        "status": "partial",
        "boardVerified": {"ux": False, "planning": True, "competitor": False},
        "boardStructureRequestIds": {"ux": "old", "planning": "req-old"},
        "boardMediaDone": {"ux": {"legacy": "token"}, "planning": {}},
    }

    checkpoint = _board_checkpoint(record)

    assert checkpoint["boardVerified"] == {"planning": True, "competitor": False}
    assert "ux" not in checkpoint["boardTokens"]
    assert record["boardVerified"]["ux"] is False


def test_empty_board_raw_verification_is_not_accepted():
    cli = FakeCli()
    cli.empty_board_key = "planning"

    with pytest.raises(LarkCommandError, match="empty"):
        FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(_job(), "req-empty-board", "update")


def test_empty_board_retry_rewrites_the_failed_board_structure():
    cli = FakeCli()
    cli.empty_board_key = "planning"
    job = _job()
    publisher = FeishuPublisher(cli, Path("data/jobs/job-publish"), wait=lambda _: None)

    with pytest.raises(LarkCommandError, match="empty"):
        publisher.publish(job, "req-empty-board-retry", "update")
    first_counts = cli.structure_update_counts.copy()
    cli.empty_board_key = ""

    result = publisher.publish(job, "req-empty-board-retry", "update")

    assert result.status == "published"
    assert cli.structure_update_counts["planning"] == first_counts["planning"] + 1


def test_board_idempotency_tokens_are_unique_and_within_feishu_limit():
    cli = FakeCli()

    FeishuPublisher(cli, Path("data/jobs/job-publish")).publish(_job(), "req-board-keys", "update")

    tokens = [args[args.index("--idempotent-token") + 1] for args, _ in cli.calls if "--idempotent-token" in args]
    assert len(tokens) == len(set(tokens))
    assert all(10 <= len(token) <= 64 for token in tokens)
    assert any(token.startswith("prd-planning-boa-") for token in tokens)
    assert not any("competitor" in token for token in tokens)
