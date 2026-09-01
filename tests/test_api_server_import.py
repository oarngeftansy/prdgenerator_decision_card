import importlib


def test_gameplay_generation_timeout_has_a_specific_planner_facing_error():
    from openai import APITimeoutError
    from backend.gameplay_analysis import GameplayAnalysisQualityError
    from backend.server import _safe_gameplay_generation_error

    root = APITimeoutError(request=None)
    wrapped = GameplayAnalysisQualityError("gameplay model request failed")
    wrapped.__cause__ = root

    assert _safe_gameplay_generation_error(wrapped) == "视觉模型响应超时，请重试；如果持续发生，请改用响应更快的视觉模型"


def test_upstream_model_status_error_is_not_mislabeled_as_an_internal_system_failure():
    from backend.server import _gameplay_generation_failure_kind, _safe_gameplay_generation_error

    upstream_error = type("APIStatusError", (Exception,), {})("upstream returned 503")

    assert _safe_gameplay_generation_error(upstream_error) == "视觉模型请求失败"
    assert _gameplay_generation_failure_kind(upstream_error) == "network"


def test_api_server_uses_python_compatible_runtime_packages():
    module = importlib.import_module("api_server")
    assert module.app.title == "ai策划案工具 API"


def test_health_exposes_the_interrupted_screenshot_recovery_capability():
    from backend.server import health

    payload = health()
    assert "interrupted-screenshot-import-recovery-v1" in payload["capabilities"]
    assert "resumable-gameplay-detail-generation-v1" in payload["capabilities"]
    assert "pending-evidence-decision-cards-v1" in payload["capabilities"]
    assert "review-entry-pending-decision-boundary-v1" in payload["capabilities"]
    assert "actionable-gameplay-quality-diagnostics-v1" in payload["capabilities"]
    assert "generated-rule-carrier-routing-v1" in payload["capabilities"]
    assert "generated-rule-carrier-routing-v2" in payload["capabilities"]
    assert "review-entry-pending-gap-quality-v1" in payload["capabilities"]
    assert "incomplete-flow-decision-routing-v1" in payload["capabilities"]
    assert "evidence-grounded-gameplay-review-v1" in payload["capabilities"]
    assert payload["systemLessons"] is True
