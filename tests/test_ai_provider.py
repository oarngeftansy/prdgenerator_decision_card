import json

import pytest

from backend.ai_provider import ProviderConfig, ProviderError, chat_json_object, validate_connectivity


def _transport(status, payload):
    def run(url, headers, body, timeout):
        assert url.endswith("/chat/completions")
        assert headers["Authorization"].startswith("Bearer ")
        assert "secret" not in url
        json.loads(body.decode("utf-8"))
        return status, json.dumps(payload).encode("utf-8")
    return run


def test_connectivity_validation_is_key_safe_and_uses_required_defaults():
    config = ProviderConfig(api_key="secret")
    result = validate_connectivity(config, transport=_transport(200, {"choices": []}))
    assert result == {
        "ok": True,
        "apiBase": "https://ws-pht7pri9ebffuga3.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        "model": "qwen3.6plus",
        "configured": True,
    }
    assert "secret" not in repr(result)


def test_authentication_failure_is_not_retryable_or_key_leaking():
    config = ProviderConfig(api_key="secret")
    result = validate_connectivity(config, transport=_transport(401, {"error": "invalid key"}))
    assert result["ok"] is False
    assert result["kind"] == "authentication"
    assert result["statusCode"] == 401
    assert result["retryable"] is False
    assert "secret" not in repr(result)


def test_json_object_request_retries_429_then_succeeds():
    calls = []

    def transport(url, headers, body, timeout):
        calls.append(1)
        if len(calls) == 1:
            return 429, b"{}"
        return 200, json.dumps({
            "choices": [{"message": {"content": '{"systems": []}'}}]
        }).encode("utf-8")

    result = chat_json_object(
        ProviderConfig(api_key="secret"),
        [{"role": "user", "content": "test"}],
        transport=transport,
        max_attempts=2,
        sleep=lambda _: None,
    )
    assert result == {"systems": []}
    assert len(calls) == 2


def test_missing_key_fails_before_transport():
    called = False

    def transport(*args):
        nonlocal called
        called = True
        return 200, b"{}"

    with pytest.raises(ProviderError) as exc:
        chat_json_object(ProviderConfig(api_key=""), [], transport=transport)
    assert exc.value.kind == "configuration"
    assert called is False


def test_invalid_json_is_classified():
    with pytest.raises(ProviderError) as exc:
        chat_json_object(
            ProviderConfig(api_key="secret"),
            [{"role": "user", "content": "test"}],
            transport=_transport(200, {"choices": [{"message": {"content": "not-json"}}]}),
            max_attempts=1,
        )
    assert exc.value.kind == "invalid_json"
