"""OpenAI-compatible provider adapter used by production planning generation.

The adapter centralizes endpoint normalization, connectivity validation, bounded
retry, public error classification and JSON-object parsing. API keys are accepted
only at runtime and are never included in public results or exception messages.
"""

from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib import error, request


DEFAULT_API_BASE = "https://ws-pht7pri9ebffuga3.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.6plus"


@dataclass(frozen=True)
class ProviderConfig:
    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    api_key: str = ""
    timeout_seconds: float = 45.0

    @property
    def chat_completions_url(self) -> str:
        return self.api_base.rstrip("/") + "/chat/completions"

    def public(self) -> dict[str, Any]:
        return {
            "apiBase": self.api_base.rstrip("/"),
            "model": self.model,
            "configured": bool(self.api_key.strip()),
        }


class ProviderError(RuntimeError):
    def __init__(self, kind: str, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.retryable = retryable

    def public(self) -> dict[str, Any]:
        return {
            "ok": False,
            "kind": self.kind,
            "statusCode": self.status_code,
            "retryable": self.retryable,
            "message": str(self),
        }


Transport = Callable[[str, dict[str, str], bytes, float], tuple[int, bytes]]


def _stdlib_transport(url: str, headers: dict[str, str], body: bytes, timeout: float) -> tuple[int, bytes]:
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return int(response.status), response.read()
    except error.HTTPError as exc:
        return int(exc.code), exc.read()
    except (error.URLError, socket.timeout, TimeoutError) as exc:
        reason = getattr(exc, "reason", exc)
        if isinstance(reason, (socket.timeout, TimeoutError)):
            raise ProviderError("timeout", "模型服务响应超时", retryable=True) from None
        raise ProviderError("network", "无法连接模型服务", retryable=True) from None


def _validate_config(config: ProviderConfig) -> None:
    if not config.api_base.strip().startswith(("https://", "http://")):
        raise ProviderError("configuration", "API 地址无效")
    if not config.model.strip():
        raise ProviderError("configuration", "模型名称不能为空")
    if not config.api_key.strip():
        raise ProviderError("configuration", "请先填写 API Key")


def _classify_status(status: int) -> ProviderError:
    if status in {401, 403}:
        return ProviderError("authentication", "API Key 无效或无权访问该模型", status_code=status, retryable=False)
    if status == 429:
        return ProviderError("rate_limit", "模型服务请求过于频繁", status_code=status, retryable=True)
    if 500 <= status <= 599:
        return ProviderError("provider", "模型服务暂时不可用", status_code=status, retryable=True)
    return ProviderError("request", f"模型服务请求失败（HTTP {status}）", status_code=status, retryable=False)


def _decode_json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProviderError("invalid_json", "模型服务返回了无法解析的 JSON", retryable=True) from None
    if not isinstance(value, dict):
        raise ProviderError("invalid_response", "模型服务返回结构无效", retryable=True)
    return value


def _request_json(
    config: ProviderConfig,
    payload: dict[str, Any],
    *,
    transport: Transport | None = None,
    max_attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    _validate_config(config)
    transport = transport or _stdlib_transport
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + config.api_key.strip(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    attempts = max(1, min(int(max_attempts), 5))
    last_error: ProviderError | None = None
    for attempt in range(attempts):
        try:
            status, raw = transport(config.chat_completions_url, headers, body, config.timeout_seconds)
            if not 200 <= status <= 299:
                raise _classify_status(status)
            return _decode_json(raw)
        except ProviderError as exc:
            last_error = exc
            if not exc.retryable or attempt + 1 >= attempts:
                raise
            sleep(min(2.0, 0.25 * (2 ** attempt)))
    assert last_error is not None
    raise last_error


def validate_connectivity(config: ProviderConfig, *, transport: Transport | None = None) -> dict[str, Any]:
    """Make a minimal authenticated completion request and return a key-safe result."""
    payload = {
        "model": config.model,
        "messages": [{"role": "user", "content": "Reply with OK."}],
        "temperature": 0,
        "max_tokens": 2,
    }
    try:
        response = _request_json(config, payload, transport=transport, max_attempts=1)
        choices = response.get("choices")
        if not isinstance(choices, list):
            raise ProviderError("invalid_response", "模型服务响应缺少 choices", retryable=False)
        return {"ok": True, **config.public()}
    except ProviderError as exc:
        return {**exc.public(), **config.public()}


def chat_json_object(
    config: ProviderConfig,
    messages: list[dict[str, str]],
    *,
    transport: Transport | None = None,
    max_attempts: int = 3,
    temperature: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    """Request a JSON object using the OpenAI-compatible JSON response contract."""
    payload = {
        "model": config.model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    response = _request_json(
        config,
        payload,
        transport=transport,
        max_attempts=max_attempts,
        sleep=sleep,
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ProviderError("invalid_response", "模型服务响应缺少正文", retryable=True) from None
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        raise ProviderError("invalid_response", "模型服务正文结构无效", retryable=True)
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        raise ProviderError("invalid_json", "模型未返回有效 JSON 对象", retryable=True) from None
    if not isinstance(result, dict):
        raise ProviderError("invalid_response", "模型未返回 JSON 对象", retryable=True)
    return result
