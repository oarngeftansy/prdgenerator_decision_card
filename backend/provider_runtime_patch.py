from __future__ import annotations

from typing import Any

from fastapi import Body, HTTPException

from . import server
from .provider_adapter import (
    DEFAULT_API_BASE,
    DEFAULT_MODEL,
    ProviderConfig,
    ProviderError,
    validate_connection,
)


_installed = False


def install_provider_runtime_patch(app) -> None:
    """Register provider defaults/validation without mutating generation modules.

    Earlier versions replaced gameplay_analysis functions at import time. That leaked
    Master Planner behavior into every test/importer and broke legacy generation
    contracts. Runtime registration is intentionally limited to configuration here;
    planner semantics live in their owning modules instead of global monkey patches.
    """
    global _installed
    if _installed:
        return
    _installed = True

    server.BUILT_IN_VISION_API_BASE = DEFAULT_API_BASE
    server.BUILT_IN_VISION_MODEL = DEFAULT_MODEL

    @app.post("/api/config/validate")
    def validate_ai_config(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return validate_connection(ProviderConfig.from_mapping(payload))
        except ProviderError as exc:
            status = exc.status_code if exc.status_code in {400, 401, 403, 429, 502, 503, 504} else 400
            if exc.kind in {"provider", "network"}:
                status = exc.status_code or 503
            elif exc.kind == "timeout":
                status = 504
            raise HTTPException(status_code=status, detail=exc.to_dict()) from exc
