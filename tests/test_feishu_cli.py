import json
import subprocess

import pytest

from backend.feishu_cli import LarkCli, LarkCommandError


class FakeProcess:
    def __init__(self, *, returncode=0, stdout=None, stderr=""):
        self.returncode = returncode
        self.stdout = json.dumps({"ok": True, "data": {"identity": "user"}}) if stdout is None else stdout
        self.stderr = stderr
        self.calls = []

    def __call__(self, argv, **kwargs):
        self.calls.append({"argv": argv, **kwargs})
        return subprocess.CompletedProcess(argv, self.returncode, self.stdout, self.stderr)


def test_cli_uses_argv_without_shell_and_parses_success():
    process = FakeProcess()
    result = LarkCli(run_process=process).run(["auth", "status", "--json", "--verify"])

    assert result.data["identity"] == "user"
    assert process.calls[0]["shell"] is False
    assert process.calls[0]["encoding"] == "utf-8"
    assert process.calls[0]["argv"][0].endswith("lark-cli.cmd")


def test_cli_uses_configured_executable(monkeypatch):
    process = FakeProcess()
    monkeypatch.setenv("LARK_CLI_EXECUTABLE", r"C:\tools\lark-cli.exe")

    LarkCli(run_process=process).run(["auth", "status", "--json", "--verify"])

    assert process.calls[0]["argv"][0] == r"C:\tools\lark-cli.exe"


def test_cli_accepts_auth_status_object_without_ok_envelope():
    process = FakeProcess(stdout=json.dumps({"identity": "user", "verified": True, "identities": {}}))

    result = LarkCli(run_process=process).run(["auth", "status", "--json", "--verify"])

    assert result.data["verified"] is True


def test_cli_ignores_progress_text_after_json_payload():
    stdout = json.dumps({"ok": True, "data": {"files": [{"name": "example"}]}})
    process = FakeProcess(stdout=f"{stdout}\n[page 1] fetching...\n")

    result = LarkCli(run_process=process).run(["drive", "files", "list", "--page-all", "--as", "user", "--json"])

    assert result.data["files"][0]["name"] == "example"


def test_cli_rejects_failed_document_result_inside_success_envelope():
    process = FakeProcess(stdout=json.dumps({
        "ok": True,
        "data": {"result": "failed", "warnings": ["Document operation failed"]},
    }))

    with pytest.raises(LarkCommandError, match="Document operation failed"):
        LarkCli(run_process=process).run(["docs", "+update", "--doc", "doc-1"])


def test_cli_rejects_partial_document_result_inside_success_envelope():
    process = FakeProcess(stdout=json.dumps({
        "ok": True,
        "data": {"result": "partial_success", "warnings": ["unsupported block"]},
    }))

    with pytest.raises(LarkCommandError, match="unsupported block"):
        LarkCli(run_process=process).run(["docs", "+update", "--doc", "doc-1"])


def test_cli_finds_error_json_after_human_readable_prefix():
    payload = {"ok": False, "error": {"subtype": "invalid_param", "message": "invalid param"}}
    process = FakeProcess(returncode=1, stdout=f"Inserting: frame.jpg -> document redacted\n{json.dumps(payload)}\n")

    with pytest.raises(LarkCommandError) as caught:
        LarkCli(run_process=process).run(["docs", "+media-insert", "--doc", "doc-1", "--file", "frame.jpg"])

    assert caught.value.kind == "invalid_param"


def test_cli_rejects_unapproved_command():
    with pytest.raises(ValueError, match="command not allowed"):
        LarkCli().run(["drive", "+delete", "abc"])


def test_cli_rejects_confirmation_bypass():
    with pytest.raises(ValueError, match="confirmation bypass"):
        LarkCli().run(["docs", "+update", "--yes"])


def test_cli_turns_missing_scope_into_structured_error():
    payload = {"ok": False, "error": {"subtype": "missing_scope", "missing_scopes": ["drive:drive"]}}
    process = FakeProcess(returncode=1, stdout="", stderr=json.dumps(payload))

    with pytest.raises(LarkCommandError) as caught:
        LarkCli(run_process=process).run(["drive", "files", "list", "--as", "user"])

    assert caught.value.kind == "missing_scope"
    assert caught.value.missing_scopes == ("drive:drive",)


def test_cli_scrubs_token_values_from_command_errors():
    payload = {"ok": False, "error": {"subtype": "command_failed", "message": "access_token=secret-value"}}
    process = FakeProcess(returncode=1, stdout="", stderr=json.dumps(payload))

    with pytest.raises(LarkCommandError) as caught:
        LarkCli(run_process=process).run(["auth", "status", "--json"])

    assert "secret-value" not in str(caught.value)
    assert "[redacted]" in str(caught.value)


def test_cli_supports_split_feishu_authorization_commands():
    process = FakeProcess(stdout=json.dumps({
        "ok": True,
        "data": {"verification_url": "https://passport.feishu.cn/auth", "device_code": "dev_123"},
    }))
    cli = LarkCli(run_process=process)

    assert cli.auth_start()["device_code"] == "dev_123"
    cli.auth_complete("dev_123")

    assert process.calls[0]["argv"][1:] == ["auth", "login", "--domain", "all", "--no-wait", "--json"]
    assert process.calls[1]["argv"][1:] == ["auth", "login", "--device-code", "dev_123", "--json"]
