from __future__ import annotations

from typing import Any

from .feishu_language_quality import language_quality_report
from .granularity_audit import granularity_audit_report
from .sample_alignment import sample_alignment_report


def stage3_quality_gate_report(model: dict[str, Any]) -> dict[str, Any]:
    granularity = granularity_audit_report(model)
    language = language_quality_report(model)
    alignment = sample_alignment_report(model)
    return {
        "passed": granularity["passed"] and language["passed"] and alignment["passed"],
        "granularityAudit": granularity,
        "languageAudit": language,
        "sampleAlignment": alignment,
        "blockers": [
            *[item["code"] for item in granularity["findings"]],
            *[item["code"] for item in language["findings"]],
        ],
    }
