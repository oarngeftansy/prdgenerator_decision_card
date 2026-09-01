from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError


DEFAULT_API_BASE = "https://ws-pht7pri9ebffuga3.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
DEFAULT_MODEL = "qwen3.6plus"


@dataclass(frozen=True)
class ProviderConfig:
    api_base: str = DEFAULT_API_BASE
    model: str = DEFAULT_MODEL
    api_key: str = ""
    timeout_seconds: float = 90.0
    max_retries: int = 2

    @classmethod
    def from_mapping(cls, value: dict[str, Any] | None) -> "ProviderConfig":
        value = value or {}
        return cls(
            api_base=str(value.get("apiBase") or value.get("api_base") or DEFAULT_API_BASE).strip().rstrip("/"),
            model=str(value.get("model") or DEFAULT_MODEL).strip(),
            api_key=str(value.get("apiKey") or value.get("api_key") or "").strip(),
            timeout_seconds=float(value.get("timeoutSeconds") or value.get("timeout_seconds") or 90.0),
            max_retries=int(value.get("maxRetries") or value.get("max_retries") or 2),
        )

    def public_dict(self) -> dict[str, Any]:
        return {"apiBase": self.api_base, "model": self.model, "hasApiKey": bool(self.api_key)}


class ProviderError(RuntimeError):
    def __init__(self, kind: str, message: str, *, status_code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.kind = kind
        self.status_code = status_code
        self.retryable = retryable

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": str(self),
            "statusCode": self.status_code,
            "retryable": self.retryable,
        }


def create_client(config: ProviderConfig) -> OpenAI:
    if not config.api_base:
        raise ProviderError("configuration", "AI API 地址未配置。")
    if not config.api_key:
        raise ProviderError("configuration", "AI API Key 未配置。")
    return OpenAI(
        api_key=config.api_key,
        base_url=config.api_base,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries,
    )


def classify_provider_exception(exc: Exception) -> ProviderError:
    if isinstance(exc, AuthenticationError):
        return ProviderError("authentication", "API Key 无效或没有模型访问权限。", status_code=401, retryable=False)
    if isinstance(exc, RateLimitError):
        return ProviderError("rate_limit", "模型服务当前限流，请稍后重试。", status_code=429, retryable=True)
    if isinstance(exc, APITimeoutError):
        return ProviderError("timeout", "模型响应超时。", retryable=True)
    if isinstance(exc, APIConnectionError):
        return ProviderError("network", "无法连接模型服务。", retryable=True)
    if isinstance(exc, APIStatusError):
        status = int(getattr(exc, "status_code", 0) or 0)
        if status in {401, 403}:
            return ProviderError("authentication", "API Key 无效或没有模型访问权限。", status_code=status, retryable=False)
        if status == 429:
            return ProviderError("rate_limit", "模型服务当前限流，请稍后重试。", status_code=status, retryable=True)
        if status >= 500:
            return ProviderError("provider", "模型服务暂时不可用。", status_code=status, retryable=True)
        return ProviderError("request", f"模型请求失败（HTTP {status}）。", status_code=status, retryable=False)
    return ProviderError("system", "模型请求发生未分类错误。", retryable=False)


def validate_connection(config: ProviderConfig) -> dict[str, Any]:
    """Perform a real authenticated model request. Never returns or persists the key."""
    client = create_client(config)
    try:
        response = client.chat.completions.create(
            model=config.model,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            temperature=0,
            max_tokens=8,
            extra_body={"enable_thinking": False} if config.model.casefold().startswith("qwen3.6") else None,
        )
    except Exception as exc:  # openai exposes multiple transport/status subclasses
        raise classify_provider_exception(exc) from exc
    text = str(response.choices[0].message.content or "").strip()
    return {"ok": True, **config.public_dict(), "responseReceived": bool(text)}
