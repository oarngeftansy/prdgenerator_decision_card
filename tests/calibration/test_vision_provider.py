from backend.calibration.vision_provider import resolve_provider


def test_qwen_profile_needs_only_key():
    config = resolve_provider({"VISION_API_KEY": "secret"})
    assert config["provider"] == "qwen"
    assert config["baseUrl"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert config["model"] == "qwen-vl-plus"
    assert config["apiKey"] == "secret"


def test_custom_provider_requires_base_and_model():
    try:
        resolve_provider({"VISION_API_KEY": "secret", "VISION_PROVIDER": "custom"})
    except ValueError as exc:
        assert "VISION_API_BASE" in str(exc)
    else:
        raise AssertionError("custom provider should require explicit configuration")

