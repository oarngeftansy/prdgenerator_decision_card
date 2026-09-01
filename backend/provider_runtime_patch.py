from __future__ import annotations

from typing import Any

from fastapi import Body, HTTPException

from . import analysis_service, gameplay_analysis, server
from .provider_adapter import (
    DEFAULT_API_BASE,
    DEFAULT_MODEL,
    ProviderConfig,
    ProviderError,
    create_client,
    validate_connection,
)


_installed = False
_original_client = analysis_service._client


def _runtime_client(config: dict[str, Any]):
    """Drop-in replacement for the legacy client factory.

    Local development proxies retain their legacy health-check behavior. All external
    OpenAI-compatible providers use the centralized adapter and therefore share the same
    timeout/retry/auth semantics.
    """
    base = str(config.get("apiBase") or "").strip().rstrip("/")
    if "127.0.0.1" in base or "localhost" in base:
        return _original_client(config)
    try:
        return create_client(ProviderConfig.from_mapping(config))
    except ProviderError:
        return None


def install_provider_runtime_patch(app) -> None:
    global _installed
    if _installed:
        return
    _installed = True

    # These constants are read dynamically by _runtime_ai_config and /api/config/public.
    server.BUILT_IN_VISION_API_BASE = DEFAULT_API_BASE
    server.BUILT_IN_VISION_MODEL = DEFAULT_MODEL

    # Modules imported the legacy factory by value, so patch both owner and consumers.
    analysis_service._client = _runtime_client
    gameplay_analysis._client = _runtime_client

    @app.post("/api/config/validate")
    def validate_ai_config(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Perform a real authenticated provider request before long-running generation."""
        try:
            return validate_connection(ProviderConfig.from_mapping(payload))
        except ProviderError as exc:
            status = exc.status_code if exc.status_code in {400, 401, 403, 429, 502, 503, 504} else 400
            if exc.kind in {"provider", "network"}:
                status = exc.status_code or 503
            elif exc.kind == "timeout":
                status = 504
            raise HTTPException(status_code=status, detail=exc.to_dict()) from exc
