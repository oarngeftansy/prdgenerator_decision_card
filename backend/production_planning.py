"""Compatibility adapter for the canonical production planning pipeline.

New production code should inspect `canonicalPipeline`. Historical callers may
continue reading the legacy top-level delivery keys returned here while migration
finishes.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ai_provider import ProviderConfig, Transport
from .canonical_pipeline import CanonicalPipelineError, run_canonical_pipeline
from .rule_normalizer import build_rule_intelligence_v1


class ProductionPlanningError(ValueError):
    pass


def build_current_projection(gameplay_model: dict[str, Any]) -> dict[str, Any]:
    """Legacy compatibility helper. It is no longer the production orchestrator."""
    approved = gameplay_model.get("approvedData")
    if gameplay_model.get("contentModelVersion") != 2 or not isinstance(approved, dict):
        raise ProductionPlanningError("Master Planner requires content model v2 approvedData")
    return build_rule_intelligence_v1(gameplay_model, approved)


def build_master_planning_delivery(
    gameplay_model: dict[str, Any],
    config: ProviderConfig,
    *,
    interaction_model: dict[str, Any] | None = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Run canonical stages and expose temporary legacy aliases for existing UI/API code."""
    try:
        pipeline = run_canonical_pipeline(
            gameplay_model,
            interaction_model,
            config,
            transport=transport,
        )
    except CanonicalPipelineError as exc:
        raise ProductionPlanningError(str(exc)) from exc

    p7 = pipeline["p7Delivery"]
    erm = pipeline["executionRuleModel"]
    p4 = pipeline["p4Review"]
    publication = {
        "chapters": deepcopy(erm.get("chapters") or []),
        "rules": deepcopy(erm.get("rules") or []),
        "ruleGroups": deepcopy(erm.get("ruleGroups") or []),
        "mechanicFlows": deepcopy(erm.get("mechanicFlows") or []),
        "gaps": deepcopy(erm.get("gaps") or []),
        "finalPlanningGaps": deepcopy(erm.get("finalPlanningGaps") or []),
        "masterPlanner": deepcopy(erm.get("masterPlanner") or {}),
        "planningSketch": deepcopy(p4.get("planningSketch") or {}),
        "interactionReview": deepcopy(p4.get("interactionReview") or {}),
        "qualityJudge": deepcopy(p4.get("qualityJudge") or {}),
    }
    return {
        # Canonical authority and observability.
        "canonicalPipeline": deepcopy(pipeline),
        "gameplayUnderstandingModel": deepcopy(pipeline["gameplayUnderstandingModel"]),
        "interactionModel": deepcopy(pipeline["interactionModel"]),
        "executionRuleModel": deepcopy(erm),
        "publicationInputSnapshot": deepcopy(pipeline["publicationInputSnapshot"]),
        "p4Review": deepcopy(p4),
        "p5DiagramProjection": deepcopy(pipeline["p5DiagramProjection"]),
        "p6ParameterProjection": deepcopy(pipeline["p6ParameterProjection"]),
        "p7Delivery": deepcopy(p7),
        # Compatibility aliases. These must be read-only projections of the
        # canonical stages; they are not independent authorities.
        "projection": deepcopy(erm),
        "publication": publication,
        "document": deepcopy(p7["document"]),
        "markdown": p7["markdown"],
        "acceptedMarkdown": p7["acceptedMarkdown"],
        "previewHtml": p7["previewHtml"],
        "feishuXml": p7["feishuXml"],
        "qualityJudge": deepcopy(p4.get("qualityJudge") or {}),
        "masterPlanner": deepcopy(erm.get("masterPlanner") or {}),
        "planningSketch": deepcopy(p4.get("planningSketch") or {}),
        "planningSketchMarkdown": p7["planningSketchMarkdown"],
        "interactionReview": deepcopy(p4.get("interactionReview") or {}),
    }
