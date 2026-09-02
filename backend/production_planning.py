"""Production adapter from reviewed gameplay model to canonical Master Planner Final."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ai_provider import ProviderConfig, Transport
from .document_assembler import build_final_document, document_to_markdown
from .interaction_planning import planning_sketch_to_markdown, project_and_review_interactions
from .master_planner import complete_execution_plan
from .publication_renderers import (
    final_document_to_annotated_markdown,
    final_document_to_feishu_xml,
    final_document_to_html,
)
from .rule_normalizer import build_rule_intelligence_v1


class ProductionPlanningError(ValueError):
    pass


def build_current_projection(gameplay_model: dict[str, Any]) -> dict[str, Any]:
    """Always rebuild from the current approved snapshot to avoid stale P7 data."""
    approved = gameplay_model.get("approvedData")
    if gameplay_model.get("contentModelVersion") != 2 or not isinstance(approved, dict):
        raise ProductionPlanningError("Master Planner requires content model v2 approvedData")
    return build_rule_intelligence_v1(gameplay_model, approved)


def build_master_planning_delivery(
    gameplay_model: dict[str, Any],
    config: ProviderConfig,
    *,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Run the production kernel and materialize Final plus interaction review."""
    projection = build_current_projection(gameplay_model)
    understanding = ((gameplay_model.get("directory") or {}).get("understanding") or {})
    completed = complete_execution_plan(
        projection,
        config,
        understanding=understanding if isinstance(understanding, dict) else {},
        transport=transport,
    )
    publication = completed.get("publication") if isinstance(completed.get("publication"), dict) else completed

    planning_sketch, interaction_review = project_and_review_interactions(publication)
    publication["planningSketch"] = deepcopy(planning_sketch)
    publication["interactionReview"] = deepcopy(interaction_review)

    quality = deepcopy(publication.get("qualityJudge") or {})
    if not interaction_review.get("ready"):
        issues = list(quality.get("criticalIssues") or [])
        for issue in interaction_review.get("criticalIssues") or []:
            if issue not in issues:
                issues.append(issue)
        quality["criticalIssues"] = issues
        quality["ready"] = False
    quality["interactionReviewReady"] = bool(interaction_review.get("ready"))
    quality["planningSketchVersion"] = planning_sketch.get("version")
    publication["qualityJudge"] = quality

    document = build_final_document(publication)
    return {
        "projection": completed,
        "publication": deepcopy(publication),
        "document": document,
        "markdown": document_to_markdown(document),
        "acceptedMarkdown": final_document_to_annotated_markdown(document),
        "previewHtml": final_document_to_html(document),
        "feishuXml": final_document_to_feishu_xml(document),
        "qualityJudge": deepcopy(quality),
        "masterPlanner": deepcopy(publication.get("masterPlanner") or {}),
        "planningSketch": deepcopy(planning_sketch),
        "planningSketchMarkdown": planning_sketch_to_markdown(planning_sketch),
        "interactionReview": deepcopy(interaction_review),
    }
