"""P7 readiness policy for the Master Planner publication path.

Legacy gameplay review still owns source integrity, interaction revision, artifact
review and explicit conflicts. Once Master Planner has produced a closed canonical
rule model, legacy blockers that only mean “the old prose is not deep enough” are
superseded by the canonical Final instead of blocking publication forever.
"""

from __future__ import annotations

from typing import Any


# Suffix/prefix codes whose responsibility moved from legacy prose generation to
# Master Planner. Keep this list narrow: media, revision, table, diagram, model,
# source-integrity and explicit review blockers are deliberately NOT here.
_PLANNER_SUFFIXES = {
    "LEAD_PLANNER_RULE_DEPTH_INSUFFICIENT",
    "GAMEPLAY_DEPTH_INSUFFICIENT",
    "RULES_MISSING",
    "VERIFICATION_MISSING",
    "BOUNDARY_OR_CONFIGURATION_MISSING",
    "FORMULA_DEFINITION_MISSING",
    "DRAW_RULE_MISSING",
    "SPATIAL_RULE_MISSING",
}
_PLANNER_PREFIXES = (
    "GRANULARITY_",
)
_GLOBAL_PLANNER_CODES = {
    "DETAIL_QUALITY_FAILED",
    "STRUCTURED_RULE_GUARD_FAILED",
    "STRUCTURED_SCHEMA_CLOSURE_INCOMPLETE",
}


def is_planner_superseded_blocker(blocker: Any) -> bool:
    value = str(blocker or "").strip()
    if not value:
        return False
    if value in _GLOBAL_PLANNER_CODES:
        return True
    code = value.rsplit(":", 1)[-1]
    if code in _PLANNER_SUFFIXES:
        return True
    return any(code.startswith(prefix) for prefix in _PLANNER_PREFIXES)


def combine_master_p7_gate(
    legacy_preview: dict[str, Any],
    *,
    master_ready: bool,
    master_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    legacy = list(dict.fromkeys(str(item) for item in (legacy_preview.get("blockerIds") or []) if item))
    superseded = [item for item in legacy if is_planner_superseded_blocker(item)] if master_ready else []
    delivery_blockers = [item for item in legacy if item not in superseded]
    quality = master_quality or {}
    if not master_ready:
        delivery_blockers.append("MASTER_PLANNING_NOT_READY")
        for issue in quality.get("criticalIssues") or []:
            delivery_blockers.append(f"MASTER_PLANNING:{issue}")
    delivery_blockers = list(dict.fromkeys(delivery_blockers))
    ready = master_ready and not delivery_blockers
    return {
        "ready": ready,
        "blockerIds": delivery_blockers,
        "legacyBlockerIds": legacy,
        "plannerSupersededBlockerIds": superseded,
    }


def merge_completion_snapshot(
    legacy_snapshot: dict[str, Any] | None,
    gate: dict[str, Any],
    *,
    master_quality: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep legacy delivery checks visible while adding canonical planning readiness."""
    snapshot = dict(legacy_snapshot or {})
    checks = [dict(item) for item in (snapshot.get("checks") or []) if isinstance(item, dict)]
    planning_ids = {"language", "granularity", "rules", "decisions"}
    master_ready = gate.get("ready") or (
        "MASTER_PLANNING_NOT_READY" not in gate.get("blockerIds", [])
        and bool(master_quality)
        and bool((master_quality or {}).get("ready"))
    )
    if master_ready:
        for check in checks:
            if check.get("id") in planning_ids:
                check["done"] = True
                check["detail"] = "由 Master Planner 最终规则模型闭合"
    checks.append({
        "id": "master_planning",
        "label": "主策规则闭环",
        "detail": f"质量分 {(master_quality or {}).get('overall', 0)}" if master_quality else "未完成",
        "done": bool((master_quality or {}).get("ready")),
    })
    completed = sum(bool(item.get("done")) for item in checks)
    total = len(checks)
    percent = 100 if gate.get("ready") else min(99, round(completed * 100 / total) if total else 0)
    snapshot.update({
        "ready": bool(gate.get("ready")),
        "percent": percent,
        "completed": completed,
        "total": total,
        "checks": checks,
        "blockerIds": list(gate.get("blockerIds") or []),
        "plannerSupersededBlockerIds": list(gate.get("plannerSupersededBlockerIds") or []),
    })
    steps = [dict(item) for item in (snapshot.get("steps") or []) if isinstance(item, dict)]
    for step in steps:
        if step.get("id") == "rules" and (master_quality or {}).get("ready"):
            step["done"] = True
        if step.get("id") == "export":
            step["done"] = bool(gate.get("ready"))
    snapshot["steps"] = steps
    return snapshot
