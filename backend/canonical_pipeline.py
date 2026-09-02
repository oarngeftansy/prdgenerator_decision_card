"""Canonical production planning pipeline.

The ordering in this module is an architectural contract:

Evidence / Video (already materialized by upstream ingestion)
-> GameplayUnderstandingModel
-> InteractionModel
-> P1 / P2 / P3 projections
-> Execution Planning
-> ExecutionRuleModel
-> P4 Review
-> P5 Diagram / P6 Parameters
-> PublicationInputSnapshot
-> P7 Assemble / Validate / Render

Only Execution Planning may call a generative model. P4-P7 are deterministic
projections/reviews/renderers and must never invent gameplay rules.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any

from .ai_provider import ProviderConfig, Transport
from .document_assembler import build_final_document, document_to_markdown
from .interaction_planning import planning_sketch_to_markdown, project_and_review_interactions
from .master_planner import complete_execution_plan
from .planner_quality_judge import evaluate_execution_readiness
from .publication_renderers import (
    final_document_to_annotated_markdown,
    final_document_to_feishu_xml,
    final_document_to_html,
)
from .rule_normalizer import build_rule_intelligence_v1


PIPELINE_STAGE_ORDER = (
    "gameplay_understanding",
    "interaction_model",
    "p1_directory_projection",
    "p2_interaction_projection",
    "p3_planning_snapshot",
    "execution_planning",
    "execution_rule_model",
    "p4_review",
    "p5_diagram_projection",
    "p6_parameter_projection",
    "publication_input_snapshot",
    "p7_assemble_validate_render",
)


class CanonicalPipelineError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _record(trace: list[str], stage: str) -> None:
    trace.append(stage)


def build_gameplay_understanding_model(gameplay_model: dict[str, Any]) -> dict[str, Any]:
    """Freeze the current gameplay understanding as the sole semantic source for projections.

    `gameplayReviewModel` remains a compatibility container. Downstream stages
    consume this first-class model rather than reaching back into evidence/media.
    """
    directory = gameplay_model.get("directory") if isinstance(gameplay_model.get("directory"), dict) else {}
    understanding = directory.get("understanding") if isinstance(directory.get("understanding"), dict) else {}
    chapters = [deepcopy(item) for item in (gameplay_model.get("chapters") or []) if isinstance(item, dict)]
    systems = [deepcopy(item) for item in (gameplay_model.get("systems") or []) if isinstance(item, dict)]
    model = {
        "version": "gameplay_understanding_model_v1_2",
        "sourceRevision": gameplay_model.get("revision"),
        "directoryRevision": directory.get("revision"),
        "summary": deepcopy(understanding.get("Summary") or understanding.get("summary") or ""),
        "coreLoop": deepcopy(understanding.get("CoreLoop") or understanding.get("coreLoop") or []),
        "systems": deepcopy(understanding.get("Systems") or understanding.get("systems") or systems),
        "systemGraph": deepcopy(understanding.get("SystemGraph") or understanding.get("systemGraph") or {}),
        "mechanisms": deepcopy(understanding.get("Mechanisms") or understanding.get("mechanisms") or []),
        "ruleGroups": deepcopy(understanding.get("RuleGroups") or understanding.get("ruleGroups") or []),
        "chapters": chapters,
    }
    model["digest"] = _digest(model)
    return model


def build_interaction_model(
    gameplay_understanding: dict[str, Any],
    interaction_source: dict[str, Any] | None,
) -> dict[str, Any]:
    """Freeze reviewed interaction observations before any execution planning.

    This is the pre-planning interaction authority. It may contain screenshot/
    flow review data, but it cannot contain planner-generated execution rules.
    """
    source = interaction_source if isinstance(interaction_source, dict) else {}
    stages = [deepcopy(item) for item in (source.get("stages") or []) if isinstance(item, dict)]
    model = {
        "version": "interaction_model_v2",
        "sourceRevision": source.get("revision"),
        "understandingDigest": gameplay_understanding.get("digest"),
        "stages": stages,
        "transitions": deepcopy(source.get("transitions") or []),
        "states": deepcopy(source.get("states") or []),
        "reviewState": deepcopy(source.get("reviewState") or {}),
    }
    model["digest"] = _digest(model)
    return model


def build_p1_directory_projection(gameplay_understanding: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "p1_directory_projection_v2",
        "sourceDigest": gameplay_understanding.get("digest"),
        "systems": deepcopy(gameplay_understanding.get("systems") or []),
        "systemGraph": deepcopy(gameplay_understanding.get("systemGraph") or {}),
        "mechanisms": deepcopy(gameplay_understanding.get("mechanisms") or []),
        "ruleGroups": deepcopy(gameplay_understanding.get("ruleGroups") or []),
        "chapters": deepcopy(gameplay_understanding.get("chapters") or []),
    }


def build_p2_interaction_projection(interaction_model: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "p2_interaction_projection_v2",
        "sourceDigest": interaction_model.get("digest"),
        "stages": deepcopy(interaction_model.get("stages") or []),
        "transitions": deepcopy(interaction_model.get("transitions") or []),
        "states": deepcopy(interaction_model.get("states") or []),
    }


def build_p3_planning_snapshot(
    gameplay_model: dict[str, Any],
    understanding: dict[str, Any],
    interaction: dict[str, Any],
    p1: dict[str, Any],
    p2: dict[str, Any],
) -> dict[str, Any]:
    approved = gameplay_model.get("approvedData")
    if gameplay_model.get("contentModelVersion") != 2 or not isinstance(approved, dict):
        raise CanonicalPipelineError("canonical planning requires content model v2 approvedData")
    snapshot = {
        "version": "p3_planning_snapshot_v2",
        "gameplayRevision": gameplay_model.get("revision"),
        "interactionRevision": interaction.get("sourceRevision"),
        "understanding": deepcopy(understanding),
        "interactionModel": deepcopy(interaction),
        "p1DirectoryProjection": deepcopy(p1),
        "p2InteractionProjection": deepcopy(p2),
        # Transitional compatibility source. It is frozen here so execution
        # planning cannot reach back into mutable upstream job/evidence state.
        "approvedData": deepcopy(approved),
    }
    snapshot["digest"] = _digest(snapshot)
    return snapshot


def build_execution_rule_model(
    gameplay_model: dict[str, Any],
    p3_snapshot: dict[str, Any],
    config: ProviderConfig,
    *,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """The only generative planning stage in the post-understanding pipeline."""
    frozen_gameplay = {
        **deepcopy(gameplay_model),
        "approvedData": deepcopy(p3_snapshot["approvedData"]),
    }
    projection = build_rule_intelligence_v1(frozen_gameplay, frozen_gameplay["approvedData"])
    completed = complete_execution_plan(
        projection,
        config,
        understanding=deepcopy(p3_snapshot.get("understanding") or {}),
        transport=transport,
    )
    publication = completed.get("publication") if isinstance(completed.get("publication"), dict) else completed
    model = {
        "version": "execution_rule_model_v1",
        "sourceP3Digest": p3_snapshot.get("digest"),
        "chapters": deepcopy(publication.get("chapters") or []),
        "rules": deepcopy(publication.get("rules") or []),
        "ruleGroups": deepcopy(publication.get("ruleGroups") or []),
        "mechanicFlows": deepcopy(publication.get("mechanicFlows") or []),
        "gaps": deepcopy(publication.get("gaps") or []),
        "finalPlanningGaps": deepcopy(publication.get("finalPlanningGaps") or []),
        "masterPlanner": deepcopy(publication.get("masterPlanner") or {}),
    }
    model["digest"] = _digest(model)
    return model


def build_p4_review(execution_rule_model: dict[str, Any]) -> dict[str, Any]:
    """Review the ERM without rewriting it."""
    publication_view = {
        "chapters": deepcopy(execution_rule_model.get("chapters") or []),
        "rules": deepcopy(execution_rule_model.get("rules") or []),
        "ruleGroups": deepcopy(execution_rule_model.get("ruleGroups") or []),
        "mechanicFlows": deepcopy(execution_rule_model.get("mechanicFlows") or []),
        "gaps": deepcopy(execution_rule_model.get("gaps") or []),
        "finalPlanningGaps": deepcopy(execution_rule_model.get("finalPlanningGaps") or []),
    }
    quality = evaluate_execution_readiness(publication_view)
    sketch, interaction_review = project_and_review_interactions(publication_view)
    critical = list(quality.get("criticalIssues") or [])
    for issue in interaction_review.get("criticalIssues") or []:
        if issue not in critical:
            critical.append(issue)
    ready = bool(quality.get("ready")) and bool(interaction_review.get("ready")) and not critical
    review = {
        "version": "p4_execution_review_v1",
        "executionRuleDigest": execution_rule_model.get("digest"),
        "ready": ready,
        "qualityJudge": {**deepcopy(quality), "criticalIssues": critical, "ready": ready},
        "planningSketch": deepcopy(sketch),
        "interactionReview": deepcopy(interaction_review),
    }
    review["digest"] = _digest(review)
    return review


def build_p5_diagram_projection(gameplay_model: dict[str, Any], execution_rule_model: dict[str, Any]) -> dict[str, Any]:
    """Project reviewed diagrams. This stage cannot add or modify ERM rules."""
    projection = {
        "version": "p5_diagram_projection_v1",
        "executionRuleDigest": execution_rule_model.get("digest"),
        "diagrams": deepcopy(gameplay_model.get("diagrams") or []),
        "diagramReview": deepcopy(gameplay_model.get("diagramReview") or {}),
    }
    projection["digest"] = _digest(projection)
    return projection


def build_p6_parameter_projection(gameplay_model: dict[str, Any], execution_rule_model: dict[str, Any]) -> dict[str, Any]:
    """Project parameters/tables without changing gameplay semantics."""
    chapter_parameters = []
    for chapter in gameplay_model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        chapter_parameters.append({
            "chapterId": chapter.get("id") or chapter.get("chapterId"),
            "parameterSchema": deepcopy(chapter.get("parameterSchema") or []),
            "formulae": deepcopy(chapter.get("formulae") or []),
            "workedExamples": deepcopy(chapter.get("workedExamples") or []),
            "configurationSources": deepcopy(chapter.get("configurationSources") or []),
        })
    projection = {
        "version": "p6_parameter_projection_v1",
        "executionRuleDigest": execution_rule_model.get("digest"),
        "chapterParameters": chapter_parameters,
        "tables": deepcopy(gameplay_model.get("tables") or []),
    }
    projection["digest"] = _digest(projection)
    return projection


def build_publication_input_snapshot(
    understanding: dict[str, Any],
    interaction: dict[str, Any],
    execution_rule_model: dict[str, Any],
    p4_review: dict[str, Any],
    p5: dict[str, Any],
    p6: dict[str, Any],
) -> dict[str, Any]:
    """Freeze the sole P7 input. Nothing after this point may call a model."""
    if p4_review.get("executionRuleDigest") != execution_rule_model.get("digest"):
        raise CanonicalPipelineError("P4 review is stale relative to ExecutionRuleModel")
    if p5.get("executionRuleDigest") != execution_rule_model.get("digest"):
        raise CanonicalPipelineError("P5 diagram projection is stale relative to ExecutionRuleModel")
    if p6.get("executionRuleDigest") != execution_rule_model.get("digest"):
        raise CanonicalPipelineError("P6 parameter projection is stale relative to ExecutionRuleModel")
    snapshot = {
        "version": "publication_input_snapshot_v1",
        "gameplayUnderstandingDigest": understanding.get("digest"),
        "interactionModelDigest": interaction.get("digest"),
        "executionRuleModel": deepcopy(execution_rule_model),
        "p4Review": deepcopy(p4_review),
        "p5DiagramProjection": deepcopy(p5),
        "p6ParameterProjection": deepcopy(p6),
        "planningSketch": deepcopy(p4_review.get("planningSketch") or {}),
    }
    snapshot["digest"] = _digest(snapshot)
    return snapshot


def assemble_validate_render(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Pure P7. No ProviderConfig, transport, evidence, or mutable job input."""
    erm = deepcopy(snapshot.get("executionRuleModel") or {})
    if not erm or not snapshot.get("digest"):
        raise CanonicalPipelineError("PublicationInputSnapshot is required")
    if not (snapshot.get("p4Review") or {}).get("ready"):
        raise CanonicalPipelineError("P4 review must be ready before P7")
    publication = {
        "chapters": deepcopy(erm.get("chapters") or []),
        "rules": deepcopy(erm.get("rules") or []),
        "ruleGroups": deepcopy(erm.get("ruleGroups") or []),
        "mechanicFlows": deepcopy(erm.get("mechanicFlows") or []),
        "gaps": deepcopy(erm.get("gaps") or []),
        "finalPlanningGaps": deepcopy(erm.get("finalPlanningGaps") or []),
        "planningSketch": deepcopy(snapshot.get("planningSketch") or {}),
        "qualityJudge": deepcopy((snapshot.get("p4Review") or {}).get("qualityJudge") or {}),
        "masterPlanner": deepcopy(erm.get("masterPlanner") or {}),
    }
    document = build_final_document(publication)
    if document.get("unresolvedDiagnostics"):
        raise CanonicalPipelineError("P7 received unresolved publication diagnostics")
    delivery = {
        "version": "p7_delivery_v1",
        "publicationInputDigest": snapshot.get("digest"),
        "document": document,
        "markdown": document_to_markdown(document),
        "acceptedMarkdown": final_document_to_annotated_markdown(document),
        "previewHtml": final_document_to_html(document),
        "feishuXml": final_document_to_feishu_xml(document),
        "planningSketch": deepcopy(snapshot.get("planningSketch") or {}),
        "planningSketchMarkdown": planning_sketch_to_markdown(snapshot.get("planningSketch") or {}),
    }
    delivery["digest"] = _digest({key: value for key, value in delivery.items() if key != "digest"})
    return delivery


def run_canonical_pipeline(
    gameplay_model: dict[str, Any],
    interaction_source: dict[str, Any] | None,
    config: ProviderConfig,
    *,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Execute the canonical order and return every first-class stage for persistence."""
    trace: list[str] = []
    understanding = build_gameplay_understanding_model(gameplay_model); _record(trace, "gameplay_understanding")
    interaction = build_interaction_model(understanding, interaction_source); _record(trace, "interaction_model")
    p1 = build_p1_directory_projection(understanding); _record(trace, "p1_directory_projection")
    p2 = build_p2_interaction_projection(interaction); _record(trace, "p2_interaction_projection")
    p3 = build_p3_planning_snapshot(gameplay_model, understanding, interaction, p1, p2); _record(trace, "p3_planning_snapshot")
    _record(trace, "execution_planning")
    erm = build_execution_rule_model(gameplay_model, p3, config, transport=transport); _record(trace, "execution_rule_model")
    p4 = build_p4_review(erm); _record(trace, "p4_review")
    p5 = build_p5_diagram_projection(gameplay_model, erm); _record(trace, "p5_diagram_projection")
    p6 = build_p6_parameter_projection(gameplay_model, erm); _record(trace, "p6_parameter_projection")
    snapshot = build_publication_input_snapshot(understanding, interaction, erm, p4, p5, p6); _record(trace, "publication_input_snapshot")
    p7 = assemble_validate_render(snapshot); _record(trace, "p7_assemble_validate_render")
    if tuple(trace) != PIPELINE_STAGE_ORDER:
        raise CanonicalPipelineError("canonical pipeline stage order drifted")
    return {
        "pipelineVersion": "canonical_planning_pipeline_v1",
        "stageTrace": trace,
        "gameplayUnderstandingModel": understanding,
        "interactionModel": interaction,
        "p1DirectoryProjection": p1,
        "p2InteractionProjection": p2,
        "p3PlanningSnapshot": p3,
        "executionRuleModel": erm,
        "p4Review": p4,
        "p5DiagramProjection": p5,
        "p6ParameterProjection": p6,
        "publicationInputSnapshot": snapshot,
        "p7Delivery": p7,
    }
