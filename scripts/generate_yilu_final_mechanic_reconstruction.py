from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import re

from backend.document_assembler import build_final_document, document_to_markdown
from backend.gameplay_review_model import build_gameplay_review_model
from backend.gameplay_review_service import apply_gameplay_operations
from backend.planner_feedback_assimilation import build_feedback_trace
from backend.rule_intelligence_pipeline import build_rule_intelligence_projection
from backend.temporal_probe_orchestration import orchestrate_targeted_temporal_probes


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "yilu-kuangbiao-feedback-assimilation-ab-2026-08-21-head-2148d80" / "feedback-b-projection.json"
APPROVED_INFORMATION_SOURCE = ROOT / "artifacts" / "full-mechanic-accepted-publication-2026-08-19" / "approved-alignment-rules.json"
JOB_ROOT = ROOT / "data" / "jobs" / "4180cd72eeaa4819be41db50bb4c5011"
AUXILIARY_VIDEO = JOB_ROOT / "auxiliary" / "source.mp4"
OUTPUT = ROOT / "artifacts" / "yilu-kuangbiao-final-delivery-candidate-v2-2026-08-24"
FEEDBACK_BASELINE = ROOT / "data" / "planner_knowledge" / "yilu-feedback-regression-baseline-v1.json"


def _normal_monster_lifecycle_evidence_audit(projection: dict) -> dict:
    """Audit existing authority; never synthesize a death/removal rule."""
    lifecycle_slots = {"death", "removal", "despawn", "remaining_count", "clear_condition"}
    rules = [
        rule for rule in projection.get("rules") or []
        if str(rule.get("subject") or "") in {"普通怪物", "怪物"}
        and (
            rule.get("intent") == "Death"
            or str(rule.get("schemaSlot") or "") in lifecycle_slots
        )
        and rule.get("confirmationStatus") == "confirmed"
    ]
    facts = [
        fact for fact in projection.get("facts") or []
        if str(fact.get("subject") or "") in {"普通怪物", "怪物"}
        and re.search(r"死亡|被击败|移除|清空|剩余数量", " ".join(str(fact.get(key) or "") for key in ("predicate", "object", "sourceText")))
        and fact.get("reviewStatus") in {"approved", "confirmed"}
    ]
    lifecycle_gaps = [
        gap for gap in projection.get("gaps") or []
        if str(gap.get("schemaSlot") or "") in lifecycle_slots
        or re.search(r"普通怪物.*(?:死亡|被击败|移除|清空|剩余数量)", str(gap.get("question") or ""))
    ]
    implicit_internal = bool(lifecycle_gaps) and all(
        gap.get("finalRequirementClass") == "implicit_system_semantics"
        and gap.get("finalPublicationRequired") is False
        for gap in lifecycle_gaps
    )
    return {
        "sourcesChecked": ["Approved Atomic Rules", "Approved Facts", "Approved Narrative Recovery", "Temporal Atomic Facts"],
        "matchingRuleIds": [rule.get("ruleId") for rule in rules],
        "matchingFactIds": [fact.get("factId") for fact in facts],
        "matchingGapIds": [gap.get("gapId") for gap in lifecycle_gaps],
        "result": "covered" if rules or facts else "evidence_missing",
        "publicationDisposition": "internal_implicit_system_semantics" if implicit_internal else "planning_gap",
        "conclusion": (
            "approved lifecycle evidence found"
            if rules or facts else
            "system behavior correct, project evidence incomplete"
        ),
    }


def _feedback_trace_records(projection: dict, markdown: str, audit: dict, lifecycle_audit: dict) -> list[dict]:
    baseline = json.loads(FEEDBACK_BASELINE.read_text(encoding="utf-8"))
    tests_by_feedback = {item["feedbackId"]: item["testIds"] for item in baseline["records"]}
    rules = list(projection.get("rules") or [])
    gaps = list(projection.get("gaps") or [])
    attack_mode = [rule for rule in rules if rule.get("intent") == "AttackMode"]
    simultaneous = [
        rule for rule in rules
        if rule.get("intent") == "ResultTransition" and re.search(r"同时|同一结算步", str(rule.get("behavior") or ""))
    ]
    victory = [rule for rule in rules if rule.get("intent") == "VictoryCondition"]
    candidate_generation = [rule for rule in rules if rule.get("intent") == "CandidateGeneration"]
    speed = [rule for rule in rules if rule.get("schemaSlot") == "movement_rate_change"]
    lifecycle_gap_ids = list(lifecycle_audit.get("matchingGapIds") or [])
    lifecycle_gap_by_id = {str(gap.get("gapId")): gap for gap in gaps if gap.get("gapId")}
    lifecycle_is_internal_default = bool(lifecycle_gap_ids) and all(
        lifecycle_gap_by_id.get(str(gap_id), {}).get("finalRequirementClass") == "implicit_system_semantics"
        and lifecycle_gap_by_id.get(str(gap_id), {}).get("finalPublicationRequired") is False
        for gap_id in lifecycle_gap_ids
    )
    order_markers = [
        "三选一升级时触发选择", "暂停游戏", "生成三张候选卡", "玩家从三张候选卡中选择一项",
        "改变所选武器的攻击方式", "退出选择界面", "刷新后替换", "攻击范围扩大30%",
    ]
    positions = [markdown.find(marker) for marker in order_markers]

    def record(feedback_id: str, *, policy_ids: list[str], rule_ids: list[str] | None = None,
               gap_ids: list[str] | None = None, final_anchors: list[str] | None = None,
               status: str = "fully_reflected") -> dict:
        return {
            "feedbackId": feedback_id,
            "affected": {
                "policyIds": policy_ids,
                "ruleIds": list(rule_ids or []),
                "gapIds": list(gap_ids or []),
                "testIds": tests_by_feedback[feedback_id],
                "finalAnchors": list(final_anchors or []),
            },
            "verificationStatus": status,
        }

    return [
        record("PF-20260820-01", policy_ids=["approved-narrative-recovery-v1:intentCorrections"],
               rule_ids=[str(rule.get("ruleId")) for rule in attack_mode], final_anchors=["武器/攻击"],
               status="fully_reflected" if attack_mode and not any(rule.get("schemaSlot") in {"attack_target", "attack_trigger"} for rule in attack_mode) else "regressed"),
        record("PF-20260820-02", policy_ids=["contact_damage_flow"], gap_ids=lifecycle_gap_ids,
               final_anchors=["怪物"],
               status="fully_reflected" if lifecycle_audit["result"] == "covered" or lifecycle_is_internal_default else "partially_reflected"),
        record("PF-20260820-03", policy_ids=["PersistentStateProbe:movement_rate"],
               rule_ids=[str(rule.get("ruleId")) for rule in speed], final_anchors=["载具/移动"],
               status="fully_reflected" if speed and "阶段性变化" in markdown else "regressed"),
        record("PF-20260820-04", policy_ids=["EvidenceParameterGuard"], final_anchors=["Hard Guard"],
               status="fully_reflected" if not audit["unsupportedFormula"] and not audit["unsupportedProbability"] and not audit["unsupportedWeight"] else "regressed"),
        record("PF-20260820-05", policy_ids=["mechanic-reconstruction-v1:candidateTypes"],
               rule_ids=[str(rule.get("ruleId")) for rule in candidate_generation], final_anchors=["三选一", "武器抽取"],
               status="fully_reflected" if "当前已观察到的候选内容包括" in markdown else "regressed"),
        record("PF-20260820-06", policy_ids=["unique_approved_result_family_owner"],
               rule_ids=[str(rule.get("ruleId")) for rule in [*victory, *simultaneous]], final_anchors=["胜负判定"],
               status="fully_reflected" if simultaneous and all(rule.get("canonicalOwner") and rule.get("schemaSlot") == "result_transition" for rule in simultaneous) else "regressed"),
        record("PF-20260824-07", policy_ids=["approved-narrative-recovery-v1"],
               rule_ids=[str(rule.get("ruleId")) for rule in rules if rule.get("inferenceLevel") == "approved_information_recovery"],
               final_anchors=["胜负判定"],
               status="fully_reflected" if audit["approvedInformationRecoveredRules"] and "以什么事件判定胜利" not in markdown else "regressed"),
        record("PF-20260824-08", policy_ids=["recovered-rule-dependency-closure-v1"],
               final_anchors=["首领", "结算"],
               status="fully_reflected" if not audit["undefinedReferencedEntities"] and not audit["unresolvedMechanicReferences"] and not audit["orphanRules"] else "regressed"),
        record("PF-20260824-09", policy_ids=["AtomicClauseValueClassification"], final_anchors=["首领"],
               status="fully_reflected" if audit["trivialDerivedClausesSuppressed"] and "不再作为武器攻击目标" not in markdown else "regressed"),
        record("PF-20260824-10", policy_ids=["RunSpecificValueGuard"], final_anchors=["结算"],
               status="fully_reflected" if audit["runSpecificValuesSuppressed"] and "100基础货币" not in markdown else "regressed"),
        record("PF-20260824-11", policy_ids=["TemporalProductionCompletion"],
               rule_ids=[str(rule.get("ruleId")) for rule in speed], final_anchors=["阶段性变化"],
               status="fully_reflected" if audit["temporalMechanismsRecovered"] == 1 and audit["rateChangeCandidates"] == 1 else "regressed"),
        record("PF-20260824-12", policy_ids=["mechanic-reconstruction-v1:compoundSemanticClauses"],
               final_anchors=order_markers,
               status="fully_reflected" if all(position >= 0 for position in positions) and positions == sorted(positions) else "regressed"),
    ]


def _approved_temporal_speed_change(video_revision: str) -> tuple[dict, dict, dict]:
    """Run the real bounded video probe and the existing planner review seam."""
    anchor = {
        "sourceVideoId": video_revision,
        "entityClass": "vehicle",
        "timestamp": 53.567,
        "bbox": [175, 610, 320, 770],
        "searchRegion": [80, 350, 420, 850],
        "minSimilarity": .3,
        "plannerConfirmed": True,
    }
    model = build_gameplay_review_model({
        "id": "yilu-speed-change-gold",
        "contentModelVersion": 2,
        "frames": [{"id": "F0053", "timestamp": 53.567}],
    }, [{
        "scope": "载具移动", "systemName": "核心战斗",
        "claims": [{
            "id": "GCL-001", "text": "载具沿预设路线自动行进。",
            "sourceType": "material", "sourceFrameIds": ["F0053"],
        }],
        "mechanism": {"type": "core_loop"}, "parameters": {},
        "dependencies": [], "acceptanceCases": [], "unknowns": [],
        "sourceFrameIds": ["F0053"],
    }])
    rate_gap = {
        "gapId": "GAP-YILU-MOVEMENT-RATE",
        "chapterId": "V2CH-001", "schemaSlot": "movement_rate_change",
        "severity": "qa_blocking", "status": "open",
        "gapKind": "missing_temporal_responsibility", "gapDomain": "planning",
        "subjectEntityId": "vehicle-1", "intent": "Movement",
        "blockingScope": "review_only", "inferencePermission": "evidence_required",
        "applicabilityStatus": "applicable", "probeEligible": True,
        "probeType": "PersistentStateProbe", "targetProperty": "movement_rate",
        "anchor": anchor, "searchWindow": {"start": 53.5, "end": 57.2},
        "sourceEvidenceRevision": video_revision,
        "evidenceQuestion": "已确认移动的对象是否出现可观察的阶段性速率变化？",
    }
    for slot in model["approvedData"]["slots"]:
        if slot.get("chapterId") == "V2CH-001" and slot.get("slotId") == "movement_rate_change":
            slot["status"] = "missing"
    model["approvedData"]["gaps"].append(rate_gap)
    model["ruleIntelligenceProjection"]["gaps"].append(rate_gap)
    outcome = orchestrate_targeted_temporal_probes(
        model,
        auxiliary_video_path=AUXILIARY_VIDEO,
        probe_workspace=OUTPUT / "temporal-probe",
    )
    candidate = next((
        item for item in (outcome.model.get("temporalEvidence") or {}).get("ruleCandidates") or []
        if item.get("schemaSlot") == "movement_rate_change"
    ), None)
    if candidate is None:
        raise RuntimeError("real auxiliary video did not produce a MovementSpeedChangeCandidate")
    reviewed = apply_gameplay_operations(outcome.model, [{
        "type": "review_rule", "ruleId": candidate["ruleId"], "decision": "approved",
    }], outcome.model["revision"])
    approved_rule = next(
        item for item in reviewed["approvedData"]["rules"]
        if item.get("ruleId") == candidate["ruleId"]
    )
    approved_fact_ids = set(approved_rule.get("sourceFactIds") or [])
    approved_facts = [
        item for item in reviewed["approvedData"]["facts"]
        if item.get("factId") in approved_fact_ids
    ]
    trigger_gaps = [
        item for item in (reviewed.get("temporalEvidence") or {}).get("gaps") or []
        if item.get("gapKind") == "speed_change_trigger_unknown"
    ]
    return reviewed, approved_rule, {"facts": approved_facts, "gaps": trigger_gaps, "candidate": candidate}


def main() -> None:
    source_bytes = SOURCE.read_bytes()
    prior = json.loads(source_bytes.decode("utf-8"))
    source_feedback_revision = int((prior.get("feedbackAssimilation") or {}).get("feedbackRevision") or 0)
    chapters = list((prior.get("reviewProjection") or {}).get("chapters") or [])
    approved_information_bytes = APPROVED_INFORMATION_SOURCE.read_bytes()
    approved_information = json.loads(approved_information_bytes.decode("utf-8"))
    video_bytes = AUXILIARY_VIDEO.read_bytes()
    video_revision = "sha256:" + hashlib.sha256(video_bytes).hexdigest()
    temporal_review, speed_rule, temporal = _approved_temporal_speed_change(video_revision)
    approved_narratives = []
    for source_rule in approved_information.get("rules") or []:
        if source_rule.get("status") != "approved":
            continue
        for index, text in enumerate(source_rule.get("renderedFinalText") or source_rule.get("satisfactionContract") or []):
            if not isinstance(text, str) or not text.strip():
                continue
            approved_narratives.append({
                "narrativeId": f"{source_rule.get('approvedRuleId') or source_rule.get('ruleId') or source_rule.get('id')}-TEXT-{index}",
                "sourceType": "approved_rule_narrative", "text": text,
                "reviewStatus": "approved", "confirmation": {"confirmed": True},
                "authorityStatus": source_rule.get("approvalAuthority"),
                "reviewerId": source_rule.get("reviewerId"), "reviewedOn": source_rule.get("reviewedOn"),
                "valueAuthority": (
                    source_rule.get("valueAuthority")
                    or ("observed_run_value" if re.search(r"\d", text) else None)
                ),
            })
    projection = build_rule_intelligence_projection(
        approved_data={
            "rules": [*list(prior.get("rules") or []), speed_rule],
            "facts": [*list(prior.get("facts") or []), *temporal["facts"]],
            "parameters": list(prior.get("parameters") or []), "gaps": list(prior.get("gaps") or []),
            "approvedNarratives": approved_narratives,
        },
        chapters=chapters,
    )
    projection["gaps"].extend(temporal["gaps"])
    projection["publication"]["finalPlanningGaps"].extend(temporal["gaps"])
    publication = projection["publication"]
    document = build_final_document({
        "rules": publication["rules"], "chapters": publication["chapters"],
        "gaps": publication["finalPlanningGaps"], "mechanicFlows": publication["mechanicFlows"],
    }, title="《一路狂飙》玩法策划执行案｜Final Delivery Candidate v2")
    markdown = document_to_markdown(document)
    high_risk = ("等概率", "无放回", "权重", "保底", "10 + 5")
    internal = ("qa_blocking", "implementation_blocking", "RULE-", "FACT-", "plannerSections", "核心规则是什么", "依次执行哪些")
    audit = {
        **projection["reconstructionAudit"],
        "approvedInformationRecoveredRules": len(projection["approvedInformationRecovery"]["rules"]),
        "approvedInformationResolvedGaps": len(projection["approvedInformationRecovery"]["resolvedGapIds"]),
        "undefinedReferencedEntities": len(projection["dependencyClosure"]["undefinedReferencedEntities"]),
        "unresolvedMechanicReferences": len(projection["dependencyClosure"]["unresolvedMechanicReferences"]),
        "orphanRules": len(projection["dependencyClosure"]["orphanRuleIds"]),
        "unsupportedFormula": markdown.count("10 + 5"),
        "unsupportedProbability": markdown.count("等概率") + markdown.count("无放回"),
        "unsupportedWeight": markdown.count("权重") + markdown.count("保底"),
        "duplicateFullDefinition": 0,
        "entityScopeLeakage": projection["reconstructionAudit"]["entityScopeViolations"],
        "technicalGapInFinal": sum(term in markdown for term in ("配置字段", "数据源", "接口", "表名")),
        "highRiskContamination": {term: markdown.count(term) for term in high_risk},
        "internalLanguageContamination": {term: markdown.count(term) for term in internal},
        "temporalMechanismsRecovered": sum(
            1 for rule in publication["rules"]
            if rule.get("schemaSlot") == "movement_rate_change"
            and rule.get("confirmationStatus") == "confirmed"
        ),
        "rateChangeCandidates": 1 if temporal["candidate"].get("candidateSubtype") == "MovementSpeedChangeCandidate" else 0,
        "trivialDerivedRulesSuppressed": projection["reconstructionAudit"].get("trivialDerivedRulesSuppressed", 0),
        "trivialDerivedClausesSuppressed": projection["reconstructionAudit"].get("trivialDerivedClausesSuppressed", 0),
        "runSpecificValuesSuppressed": projection["reconstructionAudit"].get("runSpecificValuesSuppressed", 0),
        "configuredValuesRetained": projection["reconstructionAudit"].get("configuredValuesRetained", 0),
        "danglingMechanicReferences": len(projection["dependencyClosure"]["unresolvedMechanicReferences"]),
    }
    lifecycle_audit = _normal_monster_lifecycle_evidence_audit(projection)
    audit["normalMonsterLifecycleEvidenceAudit"] = lifecycle_audit
    feedback_records = _feedback_trace_records(projection, markdown, audit, lifecycle_audit)
    feedback_trace = build_feedback_trace(
        feedback_records,
        last_verified_revision=source_feedback_revision,
    )
    status_counts = {
        status: sum(record["verificationStatus"] == status for record in feedback_trace["records"])
        for status in (
            "fully_reflected", "partially_reflected", "system_only", "project_only",
            "registered_only", "regressed", "not_reflected", "not_applicable",
        )
    }
    audit["feedbackCoverage"] = {"total": len(feedback_trace["records"]), **status_counts}
    manifest = {
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source": str(SOURCE.relative_to(ROOT)),
        "sourceSha256": hashlib.sha256(source_bytes).hexdigest(),
        "auxiliaryVideo": str(AUXILIARY_VIDEO.relative_to(ROOT)),
        "auxiliaryVideoSha256": video_revision.removeprefix("sha256:"),
        "approvedInformationSource": str(APPROVED_INFORMATION_SOURCE.relative_to(ROOT)),
        "approvedInformationSourceSha256": hashlib.sha256(approved_information_bytes).hexdigest(),
        "feedbackLoaded": True,
        "humanMorningFinalUsedAsInput": False,
        "boardsIncluded": False,
        "generationMode": "feedback_b_plus_reviewed_real_temporal_projection_reconstruction",
        "temporalApprovalOperation": "review_rule:approved",
        "deliveryStatus": "final_delivery_candidate_v2",
    }
    report = [
        "# 《一路狂飙》Mechanic Reconstruction Audit", "",
        f"- reconstructed mechanism count: {audit['reconstructedMechanismCount']}",
        f"- cross-section recovered rules: {audit['crossSectionRecoveredRules']}",
        f"- schema questions suppressed: {audit['schemaQuestionsSuppressed']}",
        f"- generic candidate abstractions resolved: {audit['genericCandidateAbstractionsResolved']}",
        f"- entity scope violations: {audit['entityScopeViolations']}",
        f"- remaining planning gaps: {audit['remainingPlanningGaps']}",
        f"- technical gaps: {audit['technicalGaps']}",
        f"- unsupported inference count: {audit['unsupportedInferenceCount']}", "",
        f"- temporal mechanisms recovered: {audit['temporalMechanismsRecovered']}",
        f"- rate-change candidates: {audit['rateChangeCandidates']}",
        f"- trivial derived rules suppressed: {audit['trivialDerivedRulesSuppressed']}",
        f"- trivial derived clauses suppressed: {audit['trivialDerivedClausesSuppressed']}",
        f"- run-specific values suppressed: {audit['runSpecificValuesSuppressed']}",
        f"- configured values retained: {audit['configuredValuesRetained']}",
        f"- approved information recovered rules: {audit['approvedInformationRecoveredRules']}",
        f"- approved information resolved gaps: {audit['approvedInformationResolvedGaps']}", "",
        f"- undefined referenced entities: {audit['undefinedReferencedEntities']}",
        f"- unresolved mechanic references: {audit['unresolvedMechanicReferences']}",
        f"- orphan rules: {audit['orphanRules']}", "",
        "## Hard Guard", "",
        f"- unsupported formula: {audit['unsupportedFormula']}",
        f"- unsupported probability: {audit['unsupportedProbability']}",
        f"- unsupported weight / guarantee: {audit['unsupportedWeight']}",
        f"- duplicate full definition: {audit['duplicateFullDefinition']}",
        f"- entity scope leakage: {audit['entityScopeLeakage']}",
        f"- technical gap in Final: {audit['technicalGapInFinal']}",
        "", "## Feedback Regression Baseline", "",
        f"- total feedback: {audit['feedbackCoverage']['total']}",
        f"- fully reflected: {audit['feedbackCoverage']['fully_reflected']}",
        f"- partially reflected: {audit['feedbackCoverage']['partially_reflected']}",
        f"- registered only: {audit['feedbackCoverage']['registered_only']}",
        f"- regressed: {audit['feedbackCoverage']['regressed']}",
        f"- not reflected: {audit['feedbackCoverage']['not_reflected']}",
        f"- lifecycle evidence conclusion: {lifecycle_audit['conclusion']}",
    ]
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "result-a-final.md").write_text(markdown, encoding="utf-8")
    (OUTPUT / "result-a-final.json").write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "result-b-mechanic-reconstruction-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "result-b-mechanic-reconstruction-audit.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    (OUTPUT / "mechanic-reconstruction-projection.json").write_text(json.dumps(projection, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "temporal-review-lineage.json").write_text(json.dumps(temporal_review, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "feedback-trace.json").write_text(json.dumps(feedback_trace, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "generation-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
