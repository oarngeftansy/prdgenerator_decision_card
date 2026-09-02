"""Publication provenance and visual-state policy.

This module keeps epistemic/planning provenance structural. User-visible copy stays
clean: inferred/proposed rules are rendered as normal implementation-ready rules and
are distinguished by presentation metadata, not by hedging labels in the sentence.
"""

from __future__ import annotations

from typing import Any

PUBLICATION_STATES = {"confirmed", "inferred", "proposed", "conflict"}
YELLOW_STATES = {"inferred", "proposed"}

# Renderer-neutral semantic tokens. HTML/Feishu exporters may map these tokens to
# their native highlight implementations without changing the underlying sentence.
VISUAL_TOKENS = {
    "confirmed": {"tone": "normal", "highlight": None},
    "inferred": {"tone": "normal", "highlight": "yellow"},
    "proposed": {"tone": "normal", "highlight": "yellow"},
    "conflict": {"tone": "danger", "highlight": "red"},
}


def normalize_publication_state(item: dict[str, Any] | None, default: str = "confirmed") -> str:
    """Resolve provenance from current and legacy fields without mutating copy."""
    item = item or {}
    candidates = (
        item.get("publicationState"),
        item.get("provenanceState"),
        item.get("epistemicStatus"),
        item.get("decisionStatus"),
        item.get("evidenceLevel"),
    )
    aliases = {
        "observed": "confirmed",
        "approved": "confirmed",
        "explicit": "confirmed",
        "fact": "confirmed",
        "reasonable_inference": "inferred",
        "hypothesis": "inferred",
        "proposal": "proposed",
        "planner_decision": "proposed",
        "contradiction": "conflict",
        "conflicted": "conflict",
    }
    for value in candidates:
        normalized = str(value or "").strip().lower()
        normalized = aliases.get(normalized, normalized)
        if normalized in PUBLICATION_STATES:
            return normalized
    return default if default in PUBLICATION_STATES else "confirmed"


def publication_visual(state: str) -> dict[str, Any]:
    state = state if state in PUBLICATION_STATES else "confirmed"
    return dict(VISUAL_TOKENS[state])


def decorate_publication_item(item: dict[str, Any], default: str = "confirmed") -> dict[str, Any]:
    """Return a copy with canonical provenance + renderer-neutral visual metadata."""
    state = normalize_publication_state(item, default=default)
    return {**item, "publicationState": state, "visual": publication_visual(state)}
