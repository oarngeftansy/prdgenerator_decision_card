from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .rule_status import RuleKnowledgeStatus, normalize_rule_status


SlotApplicability = Literal["core", "conditional", "optional", "derived", "presentation_only"]
RuleType = Literal["logic", "presentation", "interaction", "flow", "numeric", "config"]


@dataclass(frozen=True)
class ApplicabilityPredicate:
    operator: str
    operands: tuple["ApplicabilityPredicate | str", ...]


@dataclass(frozen=True)
class DerivationSpec:
    source_slots: tuple[str, ...]
    derivation_rule: str


@dataclass(frozen=True)
class GapPolicy:
    severity: str
    question: str
    probe_type: str | None = None
    target_property: str | None = None
    gap_domain: str = "planning"
    inference_permission: str = "evidence_required"


@dataclass(frozen=True)
class Gap:
    gap_id: str
    chapter_id: str
    schema_slot: str
    severity: str
    question: str
    status: str = "open"
    gap_kind: str = "missing_schema_slot"
    subject_entity_id: str | None = None
    intent: str | None = None
    blocking_scope: str = "rule"
    gap_domain: str = "planning"
    inference_permission: str = "evidence_required"
    applicability_status: str = "applicable"
    proposal_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gapId": self.gap_id, "chapterId": self.chapter_id,
            "schemaSlot": self.schema_slot, "severity": self.severity,
            "question": self.question, "status": self.status,
            "gapKind": self.gap_kind, "subjectEntityId": self.subject_entity_id,
            "intent": self.intent, "blockingScope": self.blocking_scope,
            "gapDomain": self.gap_domain,
            "inferencePermission": self.inference_permission,
            "applicabilityStatus": self.applicability_status,
            "proposalId": self.proposal_id,
        }


@dataclass(frozen=True)
class SchemaSlotDefinition:
    slot_id: str
    applicability: SlotApplicability
    allowed_rule_types: tuple[str, ...]
    applicable_when: ApplicabilityPredicate | None = None
    derivation: DerivationSpec | None = None
    gap_policy: GapPolicy | None = None
    content_group: str = "core"


@dataclass(frozen=True)
class GroupingStrategy:
    group_order: tuple[str, ...]
    mergeable_slots: tuple[tuple[str, ...], ...] = ()
    parent_child_relationships: tuple[tuple[str, tuple[str, ...]], ...] = ()
    inline_merge_rules: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class ChapterSchema:
    schema_version: str
    chapter_type: str
    mechanic_variant: str | None
    display_name: str
    slots: tuple[SchemaSlotDefinition, ...]
    grouping_strategy: GroupingStrategy
    base_schema_key: str | None = None

    @property
    def schema_key(self) -> str:
        return f"{self.schema_version}:{self.chapter_type}:{self.mechanic_variant or 'base'}"


@dataclass(frozen=True)
class AtomicFact:
    fact_id: str
    subject: str
    predicate: str
    object: str
    qualifiers: dict[str, str | int | float | bool]
    evidence_ids: tuple[str, ...]
    confidence: float
    review_status: str = "unreviewed"
    source_text: str = ""
    evidence_level: str = "observed"
    semantic_type: RuleType = "logic"
    semantic_validity: str = "valid"
    validation_errors: tuple[str, ...] = ()
    raw_evidence_text: str = ""
    source_claim_id: str = ""
    intent_hint: str | None = None
    entity_id: str | None = None
    property_path: str | None = None
    before_value: Any = None
    after_value: Any = None
    time_range: tuple[float, float] | None = None
    evidence_timestamps: tuple[float, ...] = ()
    source_kind: str = "claim"
    observation_mode: str = "single_frame"
    inference_level: str = "observed"
    temporal_pattern: str = "unknown"
    reference_frame_status: str = "unknown"
    persistence_score: float | None = None
    probe_request_id: str | None = None
    source_video_id: str | None = None
    evidence_window: tuple[float, float] | None = None
    track_candidate_id: str | None = None
    identity_status: str = "unknown"
    candidate_entity_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "factId": self.fact_id, "subject": self.subject, "predicate": self.predicate,
            "object": self.object, "qualifiers": dict(self.qualifiers),
            "evidenceIds": list(self.evidence_ids), "confidence": self.confidence,
            "reviewStatus": self.review_status, "sourceText": self.source_text,
            "evidenceLevel": self.evidence_level, "semanticType": self.semantic_type,
            "semanticValidity": self.semantic_validity, "validationErrors": list(self.validation_errors),
            "rawEvidenceText": self.raw_evidence_text, "sourceClaimId": self.source_claim_id,
            "intentHint": self.intent_hint, "entityId": self.entity_id,
            "propertyPath": self.property_path, "beforeValue": self.before_value,
            "afterValue": self.after_value,
            "timeRange": list(self.time_range) if self.time_range else None,
            "evidenceTimestamps": list(self.evidence_timestamps), "sourceKind": self.source_kind,
            "observationMode": self.observation_mode, "inferenceLevel": self.inference_level,
            "temporalPattern": self.temporal_pattern,
            "referenceFrameStatus": self.reference_frame_status,
            "persistenceScore": self.persistence_score,
            "probeRequestId": self.probe_request_id,
            "sourceVideoId": self.source_video_id,
            "evidenceWindow": list(self.evidence_window) if self.evidence_window else None,
            "trackCandidateId": self.track_candidate_id,
            "identityStatus": self.identity_status,
            "candidateEntityId": self.candidate_entity_id,
        }


@dataclass(frozen=True)
class SchemaSlotState:
    chapter_id: str
    slot_id: str
    fact_ids: tuple[str, ...]
    status: str

    def to_dict(self) -> dict[str, Any]:
        return {"chapterId": self.chapter_id, "slotId": self.slot_id, "factIds": list(self.fact_ids), "status": self.status}


@dataclass(frozen=True)
class Rule:
    rule_id: str
    semantic_key: str
    owner_chapter_id: str
    definition_mode: str
    rule_type: RuleType
    schema_slot: str
    subject: str
    behavior: str
    evidence_ids: tuple[str, ...]
    source_fact_ids: tuple[str, ...] = ()
    trigger: str | None = None
    conditions: tuple[str, ...] = ()
    result: str | None = None
    state_change: str | None = None
    exit_condition: str | None = None
    exception: str | None = None
    parameter_refs: tuple[str, ...] = ()
    review_status: str = "unreviewed"
    semantic_validity: str = "valid"
    validation_errors: tuple[str, ...] = ()
    intent: str = "Unknown"
    canonical_owner: str | None = None
    authority_status: str = "unreviewed"
    confidence: float = 0.0
    inference_level: str = "observed"
    knowledge_status: str = RuleKnowledgeStatus.CONFIRMED.value
    exact_semantic_fingerprint: str = ""
    similarity_group: str = ""
    publication_eligibility: str = "review_required"
    reference_chapter_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        status = normalize_rule_status(self.knowledge_status, inference_level=self.inference_level)
        return {
            "ruleId": self.rule_id, "semanticKey": self.semantic_key,
            "ownerChapterId": self.owner_chapter_id, "definitionMode": self.definition_mode,
            "ruleType": self.rule_type, "schemaSlot": self.schema_slot, "subject": self.subject,
            "trigger": self.trigger, "conditions": list(self.conditions), "behavior": self.behavior,
            "result": self.result, "stateChange": self.state_change, "exitCondition": self.exit_condition,
            "exception": self.exception, "parameterRefs": list(self.parameter_refs),
            "evidenceIds": list(self.evidence_ids), "sourceFactIds": list(self.source_fact_ids), "reviewStatus": self.review_status,
            "semanticValidity": self.semantic_validity, "validationErrors": list(self.validation_errors),
            "intent": self.intent, "canonicalOwner": self.canonical_owner,
            "authorityStatus": self.authority_status, "confidence": self.confidence,
            "inferenceLevel": self.inference_level, "knowledgeStatus": status,
            "exactSemanticFingerprint": self.exact_semantic_fingerprint,
            "similarityGroup": self.similarity_group,
            "publicationEligibility": self.publication_eligibility,
            "referenceChapterIds": list(self.reference_chapter_ids),
        }


@dataclass(frozen=True)
class ApprovedData:
    schema_version: str
    chapters: tuple[dict[str, Any], ...]
    facts: tuple[AtomicFact, ...]
    slots: tuple[SchemaSlotState, ...]
    rules: tuple[Rule, ...]
    approval_revision: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "contentModelVersion": 2, "schemaVersion": self.schema_version,
            "chapters": [dict(item) for item in self.chapters],
            "facts": [item.to_dict() for item in self.facts],
            "slots": [item.to_dict() for item in self.slots],
            "rules": [item.to_dict() for item in self.rules], "gaps": [],
            "approvalRevision": self.approval_revision,
        }
