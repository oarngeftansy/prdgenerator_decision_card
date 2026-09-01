from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


_ALLOWED_PREFIXES = {
    ("auth", "login"),
    ("auth", "status"),
    ("drive", "files", "list"),
    ("drive", "+create-folder"),
    ("docs", "+create"),
    ("docs", "+fetch"),
    ("docs", "+update"),
    ("docs", "+media-insert"),
    ("docs", "+media-upload"),
    ("whiteboard", "+query"),
    ("whiteboard", "+update"),
}
_SECRET_RE = re.compile(r"(?i)(access_token|refresh_token|appsecret|api[_-]?key)(\s*[=:]\s*)([^\s,}\"]+)")


def _scrub(value: str) -> str:
    return _SECRET_RE.sub(r"\1\2[redacted]", value)


def _json_payload(raw_text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    stripped = raw_text.lstrip()
    try:
        payload, _ = decoder.raw_decode(stripped)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    for match in re.finditer(r"\{", raw_text):
        try:
            payload, _ = decoder.raw_decode(raw_text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and any(key in payload for key in ("ok", "error", "data")):
            return payload
    raise json.JSONDecodeError("No JSON object found", raw_text, 0)


@dataclass(frozen=True)
class LarkResult:
    data: dict[str, Any]
    raw: dict[str, Any]


class LarkCommandError(RuntimeError):
    def __init__(self, kind: str, message: str, missing_scopes: tuple[str, ...] = ()):
        super().__init__(_scrub(message))
        self.kind = kind
        self.missing_scopes = missing_scopes

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "LarkCommandError":
        error = payload.get("error") or {}
        kind = str(error.get("subtype") or error.get("type") or "command_failed")
        message = str(error.get("message") or error.get("hint") or kind)
        scopes = tuple(str(scope) for scope in error.get("missing_scopes") or ())
        return cls(kind, message, scopes)


class LarkCli:
    def __init__(
        self,
        executable: str | None = None,
        timeout: int = 120,
        run_process: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.executable = executable or os.environ.get("LARK_CLI_EXECUTABLE") or "lark-cli.cmd"
        self.timeout = timeout
        self._run_process = run_process

    def run(self, args: list[str], stdin: str | None = None) -> LarkResult:
        if not any(tuple(args[: len(prefix)]) == prefix for prefix in _ALLOWED_PREFIXES):
            raise ValueError("command not allowed")
        if "--yes" in args:
            raise ValueError("confirmation bypass is not allowed")
        try:
            completed = self._run_process(
                [self.executable, *args],
                input=stdin,
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                shell=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise LarkCommandError("timeout", "Feishu command timed out") from exc
        except OSError as exc:
            raise LarkCommandError("command_failed", str(exc)) from exc

        raw_text = completed.stdout or completed.stderr or "{}"
        try:
            payload = _json_payload(raw_text)
        except json.JSONDecodeError as exc:
            raise LarkCommandError("command_failed", raw_text) from exc
        if completed.returncode or payload.get("ok") is False:
            raise LarkCommandError.from_payload(payload)
        data = payload.get("data", payload)
        if isinstance(data, dict) and str(data.get("result") or "").lower() in {"failed", "partial_success"}:
            warnings = data.get("warnings") or []
            message = "; ".join(str(item) for item in warnings) or "Feishu document operation failed"
            raise LarkCommandError("command_failed", message)
        return LarkResult(data=data if isinstance(data, dict) else {"value": data}, raw=payload)

    def auth_status(self) -> dict[str, Any]:
        return self.run(["auth", "status", "--json", "--verify"]).data

    def auth_start(self) -> dict[str, Any]:
        return self.run(["auth", "login", "--domain", "all", "--no-wait", "--json"]).data

    def auth_complete(self, device_code: str) -> dict[str, Any]:
        return self.run(["auth", "login", "--device-code", device_code, "--json"]).data
