"""Production adapter from reviewed gameplay model to canonical Master Planner Final."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ai_provider import ProviderConfig, Transport
from .document_assembler import build_final_document, document_to_markdown
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
    """Run the production planning kernel and materialize every Final representation."""
    projection = build_current_projection(gameplay_model)
    understanding = ((gameplay_model.get("directory") or {}).get("understanding") or {})
    completed = complete_execution_plan(
        projection,
        config,
        understanding=understanding if isinstance(understanding, dict) else {},
        transport=transport,
    )
    publication = completed.get("publication") if isinstance(completed.get("publication"), dict) else completed
    document = build_final_document(publication)
    quality = publication.get("qualityJudge") or {}
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
    }
