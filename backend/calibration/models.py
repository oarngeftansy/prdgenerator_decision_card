from __future__ import annotations

from typing import Any


EVIDENCE_LEVELS = {"observed", "inferred", "unknown"}


def make_source_ref(source_type: str, source_id: str, locator: str) -> dict[str, str]:
    return {
        "sourceType": source_type,
        "sourceId": source_id,
        "locator": locator,
    }


def validate_artifact(data: dict[str, Any], kind: str) -> list[str]:
    errors: list[str] = []
    if kind != "evidence":
        return errors
    if data.get("evidenceLevel") not in EVIDENCE_LEVELS:
        errors.append("evidenceLevel must be one of observed, inferred, unknown")
    elif not isinstance(data.get("sourceRefs"), list) or not data["sourceRefs"]:
        errors.append("evidence sourceRefs must be a non-empty list")
    return errors
