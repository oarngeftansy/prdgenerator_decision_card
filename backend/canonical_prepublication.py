"""Canonical prepublication orchestration.

This module executes the production chain only through PublicationInputSnapshot:

GameplayUnderstandingModel
-> InteractionModel
-> P1/P2/P3
-> Execution Planning Skill
-> ExecutionRuleModel
-> P4 Review
-> P5 Diagram / P6 Parameters
-> PublicationInputSnapshot

P7 is deliberately excluded. Final preview/render must consume the frozen snapshot
through `canonical_pipeline.assemble_validate_render` and must never call an AI
provider or reconstruct execution rules.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .ai_provider import ProviderConfig, Transport
from .canonical_pipeline import (
    CanonicalPipelineError,
    build_execution_rule_model,
    build_gameplay_understanding_model,
    build_interaction_model,
    build_p1_directory_projection,
    build_p2_interaction_projection,
    build_p3_planning_snapshot,
    build_p4_review,
    build_p5_diagram_projection,
    build_p6_parameter_projection,
    build_publication_input_snapshot,
)

PREPUBLICATION_STAGE_ORDER = (
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
)


def _authoritative_understanding(
    gameplay_model: dict[str, Any],
    first_class_understanding: dict[str, Any] | None,
) -> dict[str, Any]:
    candidate = first_class_understanding if isinstance(first_class_understanding, dict) else {}
    if candidate.get("version") == "gameplay_understanding_model_v1_2" and candidate.get("digest"):
        return deepcopy(candidate)
    nested = gameplay_model.get("gameplayUnderstandingModel") if isinstance(gameplay_model.get("gameplayUnderstandingModel"), dict) else {}
    if nested.get("version") == "gameplay_understanding_model_v1_2" and nested.get("digest"):
        return deepcopy(nested)
    return build_gameplay_understanding_model(gameplay_model)


def prepare_publication_input(
    gameplay_model: dict[str, Any],
    interaction_source: dict[str, Any] | None,
    config: ProviderConfig,
    *,
    first_class_understanding: dict[str, Any] | None = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    trace: list[str] = []

    understanding = _authoritative_understanding(gameplay_model, first_class_understanding)
    trace.append("gameplay_understanding")

    interaction = build_interaction_model(understanding, interaction_source)
    trace.append("interaction_model")

    p1 = build_p1_directory_projection(understanding)
    trace.append("p1_directory_projection")

    p2 = build_p2_interaction_projection(interaction)
    trace.append("p2_interaction_projection")

    p3 = build_p3_planning_snapshot(gameplay_model, understanding, interaction, p1, p2)
    trace.append("p3_planning_snapshot")

    trace.append("execution_planning")
    execution_rule_model = build_execution_rule_model(
        gameplay_model,
        p3,
        config,
        transport=transport,
    )
    trace.append("execution_rule_model")

    p4 = build_p4_review(execution_rule_model)
    trace.append("p4_review")

    p5 = build_p5_diagram_projection(gameplay_model, execution_rule_model)
    trace.append("p5_diagram_projection")

    p6 = build_p6_parameter_projection(gameplay_model, execution_rule_model)
    trace.append("p6_parameter_projection")

    snapshot = build_publication_input_snapshot(
        understanding,
        interaction,
        execution_rule_model,
        p4,
        p5,
        p6,
    )
    trace.append("publication_input_snapshot")

    if tuple(trace) != PREPUBLICATION_STAGE_ORDER:
        raise CanonicalPipelineError("canonical prepublication stage order drifted")

    return {
        "pipelineVersion": "canonical_planning_pipeline_v1",
        "stageTrace": trace,
        "gameplayUnderstandingModel": understanding,
        "interactionModel": interaction,
        "p1DirectoryProjection": p1,
        "p2InteractionProjection": p2,
        "p3PlanningSnapshot": p3,
        "executionRuleModel": execution_rule_model,
        "p4Review": p4,
        "p5DiagramProjection": p5,
        "p6ParameterProjection": p6,
        "publicationInputSnapshot": snapshot,
    }
