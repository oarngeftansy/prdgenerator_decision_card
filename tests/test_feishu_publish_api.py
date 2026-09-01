from pathlib import Path

import pytest
from fastapi import HTTPException

from backend import server, storage
from backend.feishu_publish import PublicationConflict
from tests.review_fixtures import make_confirmed_job
from tests.test_gameplay_render import complete_job


def _make_job(tmp_path: Path, monkeypatch, *, completed=True):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    job = storage.new_job({"mode": "gameplay", "projectName": "Demo", "scope": ""})
    job["status"] = "completed" if completed else "processing"
    job["plan"] = "# Demo" if completed else ""
    if completed:
        job["planningModel"] = {"standard": "GVE16", "mode": "gameplay"}
    storage.save_job(job)
    return job


class ImmediateExecutor:
    def submit(self, function, *args):
        function(*args)


class DeferredExecutor:
    def __init__(self):
        self.tasks = []

    def submit(self, function, *args):
        self.tasks.append((function, args))


class FakePublisher:
    def __init__(self, cli, job_dir, save=None, approval_guard=None):
        self.save = save

    def publish(self, job, request_id, mode):
        publication = {
            "status": "published", "requestId": request_id, "documentToken": "doc-1",
            "documentUrl": "https://feishu.cn/docx/doc-1", "access_token": "secret",
        }
        self.save(publication, job.get("feishuPublicationHistory"))


class FailingPublisher:
    def __init__(self, cli, job_dir, save=None, approval_guard=None):
        pass

    def publish(self, job, request_id, mode):
        raise OSError("cli unavailable")


class RecordingPublisher:
    request_id = ""

    def __init__(self, cli, job_dir, save=None, approval_guard=None):
        pass

    def publish(self, job, request_id, mode):
        RecordingPublisher.request_id = request_id


class FakeAuthCli:
    def auth_start(self):
        return {"verification_url": "https://passport.feishu.cn/auth", "device_code": "dev_123456"}

    def auth_complete(self, device_code):
        self.device_code = device_code
        return {"ok": True, "access_token": "secret"}


class StaleSavingPublisher:
    def __init__(self, cli, job_dir, save=None, approval_guard=None):
        self.save = save

    def publish(self, job, request_id, mode):
        record = dict(job["feishuPublication"])
        record.update(status="published", requestId=request_id, documentToken="old-doc")
        self.save(record, job.get("feishuPublicationHistory"))


class EditAfterGuardPublisher:
    job_id = ""
    writes_after_persist = 0

    def __init__(self, cli, job_dir, save=None, approval_guard=None):
        self.save = save
        self.approval_guard = approval_guard

    def publish(self, job, request_id, mode):
        self.approval_guard()

        def edit(current):
            current["reviewModel"]["revision"] += 1
            current["reviewModel"]["reviewState"]["previewRevision"] = None
            current["reviewModel"]["stages"][0]["name"] = "human edit"

        storage.mutate_job(self.job_id, edit)
        record = dict(job["feishuPublication"])
        record["status"] = "uploading_board_media"
        self.save(record, job.get("feishuPublicationHistory"))
        EditAfterGuardPublisher.writes_after_persist += 1


class RemoteRevisionConflictPublisher:
    def __init__(self, cli, job_dir, save=None, approval_guard=None):
        self.save = save

    def publish(self, job, request_id, mode):
        message = "The Feishu document has remote edits; publish a new version to preserve them."
        record = dict(job["feishuPublication"])
        record.update(status="conflict", requestId=request_id, message=message)
        self.save(record, job.get("feishuPublicationHistory"))
        raise PublicationConflict(message)


class NewVersionSavingPublisher:
    retained_old_document = None

    def __init__(self, cli, job_dir, save=None, approval_guard=None):
        self.save = save

    def publish(self, job, request_id, mode):
        history = [dict(job["feishuPublication"])]
        persisted = self.save({"version": 2, "requestId": request_id, "status": "creating_document"}, history)
        NewVersionSavingPublisher.retained_old_document = "documentToken" in persisted


def _attach_ready_review(job):
    confirmed = make_confirmed_job()
    job["metadata"] = confirmed["metadata"]
    job["frames"] = confirmed["frames"]
    job["reviewModel"] = confirmed["reviewModel"]
    storage.save_job(job)
    return job


def test_publish_requires_completed_plan(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch, completed=False)

    with pytest.raises(HTTPException) as caught:
        server.publish_job_to_feishu(job["id"], {"requestId": "req-00000004", "mode": "update"})

    assert caught.value.status_code == 409


def test_publish_validates_request_id(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)

    with pytest.raises(HTTPException) as caught:
        server.publish_job_to_feishu(job["id"], {"requestId": "bad", "mode": "update"})

    assert caught.value.status_code == 400


def test_new_publication_pins_the_selected_folder(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)
    deferred = DeferredExecutor()
    monkeypatch.setattr(server, "executor", deferred)

    server.publish_job_to_feishu(job["id"], {
        "requestId": "req-folder-0001", "mode": "new_version",
        "folderToken": "fld_game", "folderName": "游戏项目",
    })

    record = storage.load_job(job["id"])["feishuPublication"]
    assert record["folderToken"] == "fld_game"
    assert record["folderName"] == "游戏项目"
    assert len(deferred.tasks) == 1


def test_publish_starts_worker_and_public_state_is_allowlisted(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)
    monkeypatch.setattr(server, "executor", ImmediateExecutor())
    monkeypatch.setattr(server, "FeishuPublisher", FakePublisher)

    response = server.publish_job_to_feishu(job["id"], {"requestId": "req-00000005", "mode": "update"})
    public = server.get_feishu_publication(job["id"])

    assert response["status"] == "checking_auth"
    assert public["status"] == "published"
    assert public["documentUrl"].endswith("doc-1")
    assert "access_token" not in public
    assert "documentToken" not in public


def test_public_job_never_returns_publication_credentials():
    public = server._public_job({
        "frames": [],
        "feishuPublication": {
            "status": "published", "documentUrl": "https://feishu.cn/docx/doc-1",
            "access_token": "secret", "refresh_token": "secret-2", "documentToken": "doc-1",
        },
    })

    assert public["feishuPublication"] == {
        "status": "published", "documentUrl": "https://feishu.cn/docx/doc-1"
    }


def test_public_job_allowlists_current_and_historical_publication_records_recursively():
    public = server._public_job({
        "frames": [],
        "feishuPublication": {
            "status": "published", "documentUrl": "https://feishu.cn/docx/current",
            "documentToken": "secret-current-doc", "boardTokens": {"planning": "secret-current-board"},
        },
        "feishuPublicationHistory": [
            {
                "status": "partial", "documentUrl": "https://feishu.cn/docx/old",
                "message": "飞书文档已创建，但导出尚未完成；可继续重试",
                "documentToken": "secret-old-doc", "boardMediaDone": {"planning": {"F0001": "secret-media"}},
            },
            {
                "status": "failed", "message": "access_token=secret D:/jobs/private.json",
                "nested": {"credential": "secret-history"},
            },
        ],
    })

    assert public["feishuPublication"] == {
        "status": "published", "documentUrl": "https://feishu.cn/docx/current",
    }
    assert public["feishuPublicationHistory"] == [
        {
            "status": "partial", "documentUrl": "https://feishu.cn/docx/old",
            "message": "飞书文档已创建，但导出尚未完成；可继续重试",
        },
        {"status": "failed"},
    ]
    assert all(
        marker not in f"{key} {value}".lower()
        for key, value in _walk(public)
        for marker in ("secret", "documenttoken", "boardtokens", "boardmediadone", "credential", "d:/")
    )


def _walk(value):
    if isinstance(value, dict):
        yield from value.items()
        for nested in value.values():
            yield from _walk(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk(nested)


def test_public_publication_only_exposes_status_url_and_user_message():
    public = server._public_feishu_publication({
        "status": "partial", "documentUrl": "https://feishu.cn/docx/doc-1",
        "boardTokens": {"ux": "secret-board"}, "boardMediaDone": {"ux": {"asset": "secret-media"}},
        "boardVerified": {"ux": True}, "cliStdout": "secret", "sourcePath": "D:/secret.jpg",
        "message": "飞书文档已创建，但导出尚未完成；可继续重试", "nested": {"credential": "secret"},
    })

    assert public == {
        "status": "partial", "documentUrl": "https://feishu.cn/docx/doc-1",
        "message": "飞书文档已创建，但导出尚未完成；可继续重试",
    }
    assert all("token" not in str(key).lower() and "secret" not in str(value).lower() and "d:/" not in str(value).lower()
               for key, value in _walk(public))


def test_public_publication_redacts_arbitrary_persisted_error_message_recursively():
    public = server._public_feishu_publication({
        "status": "failed",
        "message": "lark-cli stdout: access_token=secret D:/jobs/private.json board-token-123",
    })

    assert public == {"status": "failed"}
    assert all(
        marker not in f"{key} {value}".lower()
        for key, value in _walk(public)
        for marker in ("token", "secret", "d:/", "stdout", "credential")
    )


def test_worker_turns_early_cli_failure_into_terminal_state(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)
    job["feishuPublication"] = {"status": "checking_auth", "requestId": "req-00000006"}
    storage.save_job(job)
    monkeypatch.setattr(server, "FeishuPublisher", FailingPublisher)

    server._publish_feishu(job["id"], "req-00000006", "update")

    publication = storage.load_job(job["id"])["feishuPublication"]
    assert publication["status"] == "failed"
    assert publication["message"] == "飞书连接失败，可以重试。"


def test_partial_retry_reuses_saved_request_id_after_page_reload(tmp_path, monkeypatch):
    job = _make_job(tmp_path, monkeypatch)
    job["feishuPublication"] = {
        "status": "partial", "requestId": "req-original-0001", "documentToken": "doc-1"
    }
    storage.save_job(job)
    monkeypatch.setattr(server, "executor", ImmediateExecutor())
    monkeypatch.setattr(server, "FeishuPublisher", RecordingPublisher)

    server.publish_job_to_feishu(job["id"], {"requestId": "req-new-page-0002", "mode": "update"})

    assert RecordingPublisher.request_id == "req-original-0001"


def test_newer_publish_pin_cannot_be_overwritten_by_an_older_worker(tmp_path, monkeypatch):
    job = _attach_ready_review(_make_job(tmp_path, monkeypatch))
    executor = DeferredExecutor()
    monkeypatch.setattr(server, "executor", executor)
    monkeypatch.setattr(server, "FeishuPublisher", StaleSavingPublisher)

    server.publish_job_to_feishu(job["id"], {"requestId": "req-concurrent-0001", "mode": "update"})
    server.publish_job_to_feishu(job["id"], {"requestId": "req-concurrent-0002", "mode": "update"})
    first_worker, first_args = executor.tasks[0]
    first_worker(*first_args)

    record = storage.load_job(job["id"])["feishuPublication"]
    assert record["requestId"] == "req-concurrent-0002"
    assert record["status"] == "checking_auth"


def test_duplicate_busy_request_does_not_start_a_second_worker(tmp_path, monkeypatch):
    job = _attach_ready_review(_make_job(tmp_path, monkeypatch))
    executor = DeferredExecutor()
    monkeypatch.setattr(server, "executor", executor)

    payload = {"requestId": "req-idempotent-0001", "mode": "update"}
    server.publish_job_to_feishu(job["id"], payload)
    server.publish_job_to_feishu(job["id"], payload)

    assert len(executor.tasks) == 1


def test_new_version_publication_merge_does_not_retain_the_old_document_token(tmp_path, monkeypatch):
    job = _attach_ready_review(_make_job(tmp_path, monkeypatch))
    job["feishuPublication"] = {"status": "published", "requestId": "req-old-version-001", "documentToken": "old-doc"}
    storage.save_job(job)
    NewVersionSavingPublisher.retained_old_document = None
    monkeypatch.setattr(server, "executor", ImmediateExecutor())
    monkeypatch.setattr(server, "FeishuPublisher", NewVersionSavingPublisher)

    server.publish_job_to_feishu(job["id"], {"requestId": "req-new-version-001", "mode": "new_version"})

    assert NewVersionSavingPublisher.retained_old_document is False


def test_edit_after_guard_is_preserved_and_stale_persist_stops_later_writes(tmp_path, monkeypatch):
    job = _attach_ready_review(_make_job(tmp_path, monkeypatch))
    EditAfterGuardPublisher.job_id = job["id"]
    EditAfterGuardPublisher.writes_after_persist = 0
    monkeypatch.setattr(server, "executor", ImmediateExecutor())
    monkeypatch.setattr(server, "FeishuPublisher", EditAfterGuardPublisher)

    server.publish_job_to_feishu(job["id"], {"requestId": "req-edit-race-0001", "mode": "update"})

    current = storage.load_job(job["id"])
    assert current["reviewModel"]["stages"][0]["name"] == "human edit"
    assert current["reviewModel"]["revision"] == job["reviewModel"]["revision"] + 1
    assert current["feishuPublication"]["status"] == "conflict"
    assert "preview" in current["feishuPublication"]["message"].lower() or "\u9884\u89c8" in current["feishuPublication"]["message"]
    assert EditAfterGuardPublisher.writes_after_persist == 0


def test_remote_revision_conflict_retains_remote_edit_recovery_message(tmp_path, monkeypatch):
    job = _attach_ready_review(_make_job(tmp_path, monkeypatch))
    monkeypatch.setattr(server, "executor", ImmediateExecutor())
    monkeypatch.setattr(server, "FeishuPublisher", RemoteRevisionConflictPublisher)

    server.publish_job_to_feishu(job["id"], {"requestId": "req-remote-race-0001", "mode": "update"})

    publication = server.get_feishu_publication(job["id"])
    assert publication["status"] == "conflict"
    assert publication["message"] == "The Feishu document has remote edits; publish a new version to preserve them."


def _save_complete_gameplay_job(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "DATA_ROOT", tmp_path)
    monkeypatch.setattr(server, "DATA_ROOT", tmp_path)
    job = complete_job()
    (tmp_path / job["id"]).mkdir(parents=True)
    storage.save_job(job)
    server.create_gameplay_final_preview(job["id"], {"expectedRevision": job["gameplayReviewModel"]["revision"]})
    return storage.load_job(job["id"])


def test_combined_publish_pins_both_review_revisions(tmp_path, monkeypatch):
    job = _save_complete_gameplay_job(tmp_path, monkeypatch)
    executor = DeferredExecutor()
    monkeypatch.setattr(server, "executor", executor)

    server.publish_job_to_feishu(job["id"], {"requestId": "req-combined-0001", "mode": "update"})

    record = storage.load_job(job["id"])["feishuPublication"]
    assert record["approvedReviewRevision"] == job["reviewModel"]["revision"]
    assert record["approvedGameplayRevision"] == job["gameplayReviewModel"]["revision"]
    assert len(executor.tasks) == 1


def test_combined_worker_rejects_gameplay_edit_after_publication_start(tmp_path, monkeypatch):
    job = _save_complete_gameplay_job(tmp_path, monkeypatch)
    executor = DeferredExecutor()
    monkeypatch.setattr(server, "executor", executor)
    monkeypatch.setattr(server, "FeishuPublisher", RecordingPublisher)
    server.publish_job_to_feishu(job["id"], {"requestId": "req-combined-0002", "mode": "update"})

    def edit(current):
        current["gameplayReviewModel"]["revision"] += 1
        current["gameplayReviewModel"]["reviewState"]["previewRevision"] = None

    storage.mutate_job(job["id"], edit)
    worker, args = executor.tasks[0]
    worker(*args)

    assert storage.load_job(job["id"])["feishuPublication"]["status"] == "conflict"


def test_combined_publish_ignores_legacy_competitor_mutation(tmp_path, monkeypatch):
    job = _save_complete_gameplay_job(tmp_path, monkeypatch)
    job["reviewModel"]["referenceBoards"]["competitor"]["status"] = "uploading"
    storage.save_job(job)
    executor = DeferredExecutor()
    monkeypatch.setattr(server, "executor", executor)

    response = server.publish_job_to_feishu(job["id"], {"requestId": "req-combined-0003", "mode": "update"})

    assert response["status"] == "checking_auth"
    assert len(executor.tasks) == 1


def test_combined_partial_retry_rejects_a_newer_gameplay_revision(tmp_path, monkeypatch):
    job = _save_complete_gameplay_job(tmp_path, monkeypatch)
    job["feishuPublication"] = {
        "status": "partial", "requestId": "req-combined-old1",
        "approvedReviewRevision": job["reviewModel"]["revision"],
        "approvedGameplayRevision": job["gameplayReviewModel"]["revision"] - 1,
        "documentToken": "doc-existing",
    }
    storage.save_job(job)

    with pytest.raises(HTTPException) as caught:
        server.publish_job_to_feishu(job["id"], {"requestId": "req-combined-new1", "mode": "update"})

    assert caught.value.status_code == 409
