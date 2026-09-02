"""Runtime owner for Execution Planning Skill v2.

This module is the only generative stage after P3. It loads the checked-in Skill
contract at runtime and combines it with the current dynamic project graph/gaps.
"""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from .ai_provider import ProviderConfig, Transport, chat_json_object
from .master_planner import (
    MasterPlannerError,
    _compact_context,
    _gap_id,
    _open_gap,
    _validate_decisions,
    apply_planner_decisions,
)
from .planning_skill_contract import load_production_skill


def _runtime_prompt(context: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    contract = load_production_skill("execution_planning")
    gap_payload = [{
        "gapId": gap["gapId"],
        "chapterId": gap.get("chapterId"),
        "mechanicId": gap.get("mechanicId") or gap.get("ownerMechanicId"),
        "intent": gap.get("intent"),
        "schemaSlot": gap.get("schemaSlot"),
        "gapKind": gap.get("gapKind"),
        "question": gap.get("question"),
        "knownContext": gap.get("knownContext") or gap.get("evidenceSummary") or "",
    } for gap in gaps]
    return f"""{contract}

## Runtime task

You are executing the Skill above for the current project. Close every supplied gap exactly once. Do not copy mechanism nouns or structures from examples/Golden Samples. The current dynamic project context is authoritative.

Return JSON only:
{{"decisions":[{{"gapId":"...","publicationState":"inferred|proposed","decision":"确定性规则正文","ruleType":"logic|flow|numeric|config|presentation","trigger":"可为空","conditions":[],"result":"可为空","exception":"可为空","persistence":"可为空","reset":"可为空","dependencies":[],"acceptanceCases":[]}}]}}

Additional runtime constraints:
- Every gapId must appear exactly once.
- The visible decision must be decisive Chinese planning copy. Never write 待确认、可能、或许、根据素材推测、建议可以、【推断】 or provenance labels.
- Do not invent formal table names, field IDs, APIs or technical architecture.
- Preserve confirmed rules and use only the dimensions relevant to the current mechanism.

Current project context:
{json.dumps(context, ensure_ascii=False)}

Execution gaps:
{json.dumps(gap_payload, ensure_ascii=False)}"""


def execute_planning_skill(
    projection: dict[str, Any],
    config: ProviderConfig,
    *,
    understanding: dict[str, Any] | None = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Execute the checked-in Skill contract and return a closed rule projection."""
    source = deepcopy(projection)
    publication = source.get("publication") if isinstance(source.get("publication"), dict) else source
    gaps: list[dict[str, Any]] = []
    for index, raw_gap in enumerate(publication.get("gaps") or publication.get("finalPlanningGaps") or [], 1):
        if not isinstance(raw_gap, dict) or not _open_gap(raw_gap):
            continue
        gap = deepcopy(raw_gap)
        gap["gapId"] = _gap_id(gap, index)
        gaps.append(gap)

    if not gaps:
        publication["masterPlanner"] = {
            "status": "completed",
            "decisionCount": 0,
            "inferredCount": 0,
            "proposedCount": 0,
            "skillContract": "execution-planning-v2",
        }
        return source

    payload = chat_json_object(
        config,
        [{"role": "user", "content": _runtime_prompt(_compact_context(source, understanding), gaps)}],
        transport=transport,
        max_attempts=3,
        temperature=0.1,
    )
    decisions = _validate_decisions(payload, gaps)
    publication["gaps"] = gaps
    publication["finalPlanningGaps"] = deepcopy(gaps)
    output = apply_planner_decisions(source, decisions)
    target = output.get("publication") if isinstance(output.get("publication"), dict) else output
    target.setdefault("masterPlanner", {})["skillContract"] = "execution-planning-v2"
    return output
