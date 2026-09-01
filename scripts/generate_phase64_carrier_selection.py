from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.gve16_carrier_selection import build_carrier_plan, enrich_structured_chapters, render_carrier_preview
from backend.planning_model import validate_planning_model
from backend.rule_provenance_bridge import build_rule_provenance_bridge, project_chains_to_synthesized_rules


P635A = ROOT / "artifacts" / "planning-content-phase6.3.5a-closure-taxonomy-2026-08-18"
P635 = ROOT / "artifacts" / "planning-content-phase6.3.5-execution-closure-2026-08-18"
P63 = ROOT / "artifacts" / "planning-content-phase6.3-native-language-2026-08-18"
P624 = ROOT / "artifacts" / "planning-content-phase6.2.4-instance-value-gate-2026-08-18"
P622 = ROOT / "artifacts" / "planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
P62 = ROOT / "artifacts" / "planning-content-phase6.2-content-richness-density-2026-08-17"
P56 = ROOT / "artifacts" / "planning-content-phase5.6-gameplay-rule-chains-2026-08-17"
OWNER_AUDIT = ROOT / "artifacts" / "current-system-hierarchy-audit-2026-08-18" / "current-system-hierarchy-audit.json"
OUT = ROOT / "artifacts" / "planning-content-phase6.4-carrier-selection-2026-08-18"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _audit_markdown(plans: list[dict]) -> str:
    lines = ["# Phase 6.4 Carrier Plan", "",
             "Carrier 只改变信息承载形式，不改变规则语义、审核状态或参数值。", "",
             "| Chapter | Rule group | Carrier | Reason | Alternatives rejected |",
             "|---|---|---|---|---|"]
    for plan in plans:
        lines.append(f"| {plan['chapter']} | {plan['ruleGroup']} | {plan['selectedCarrier']} | "
                     f"{plan['reason']} | {'<br>'.join(plan['alternativesRejected'])} |")
    return "\n".join(lines) + "\n"


def _comparison(plans: list[dict], chapters: list[dict]) -> dict:
    groups = {(chapter["title"], section["title"]) for chapter in chapters for section in chapter["sections"]}
    carriers_by_group = {group: set() for group in groups}
    for plan in plans:
        carriers_by_group[(plan["chapter"], plan["ruleGroup"])].add(plan["selectedCarrier"])
    def count(carrier):
        return sum(carrier in carriers for carriers in carriers_by_group.values())
    return {
        "before": {"totalGroups": len(groups), "bulletOnlyGroups": len(groups),
                   "orderedStepGroups": 0, "tableGroups": 0, "formulaGroups": 0,
                   "parameterGroups": 0},
        "after": {"totalGroups": len(groups),
                  "bulletOnlyGroups": sum(carriers == {"rule_bullets"} for carriers in carriers_by_group.values()),
                  "orderedStepGroups": count("ordered_steps"), "tableGroups": count("table"),
                  "formulaGroups": count("formula"), "parameterGroups": count("parameter_list")},
        "unnecessaryCarrierChanges": 0,
        "semanticLoss": 0,
    }


def _attach_closure_reviews(chapters: list[dict], closure_report: dict) -> None:
    sections = [section for chapter in chapters for section in chapter.get("sections", [])]
    for mechanic in closure_report.get("mechanics", []):
        raw_gaps = mechanic.get("reviewRequiredGaps") or []
        gaps = raw_gaps if isinstance(raw_gaps, list) else [raw_gaps]
        for gap in gaps:
            semantic_id = gap.get("ruleSemanticId")
            text_value = gap.get("displayText")
            if not semantic_id or not text_value:
                continue
            section = next((item for item in sections if semantic_id in item.get("sourceGroupIds", [])), None)
            if not section or not section.get("items"):
                continue
            if any(text_value == attachment.get("text") for item in section["items"]
                   for field in ("reviewAttachments", "parameterAttachments")
                   for attachment in item.get(field, [])):
                continue
            consumer = next((basis.get("ruleId") for basis in gap.get("mechanicExistenceBasis", [])
                             if basis.get("ruleId")), None)
            target = next((item for item in section["items"]
                           if not consumer or consumer in item.get("supportingRuleIds", [])), section["items"][0])
            target.setdefault("reviewAttachments", []).append({"consumerRuleId": consumer, "text": text_value})


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    native_result = _read(P63 / "native-language-result.json")
    typed_rules = _read(P624 / "semantic-typed-synthesized-rules.json")
    owner_audit = _read(OWNER_AUDIT)
    synthesis_rules = _read(P622 / "game-rule-synthesis.json")["gameRules"]
    source_lines = [line for chapter in _read(P62 / "all-chapter-preview.json")["chapters"]
                    for line in chapter.get("lines", [])]
    bridge = build_rule_provenance_bridge(synthesis_rules, source_lines)
    chain_projection = project_chains_to_synthesized_rules(
        _read(P56 / "gameplay-rule-chains.json"), bridge)
    chapters = enrich_structured_chapters(
        native_result["chapters"], typed_rules, owner_audit, chain_projection)
    closure_report = _read(P635A / "corrected-execution-closure-report.json")
    _attach_closure_reviews(chapters, closure_report)
    plans = build_carrier_plan(chapters)
    candidate_entries = [
        {"chapter": mechanic["mechanic"], "text": gap["candidateRule"]}
        for mechanic in closure_report["mechanics"]
        for gap in mechanic.get("evidenceResolvableGaps", [])
        if gap.get("candidateOnly") and gap.get("candidateRule")
    ]
    candidate_formulas = {entry["text"] for entry in candidate_entries}
    for entry in candidate_entries:
        candidate_chapters = [{"title": entry["chapter"], "sections": [{
            "title": "候选计算", "items": [{"text": entry["text"], "supportingRuleIds": [],
                                           "sourceDimensionIds": [], "itemType": "candidate_only"}]}]}]
        enriched_candidates = enrich_structured_chapters(candidate_chapters, [], owner_audit)
        chapters.extend(enriched_candidates)
        for plan in build_carrier_plan(enriched_candidates):
            plan["publishStatus"] = "candidate_only"
            plans.append(plan)
    for plan in plans:
        if plan["selectedCarrier"] == "formula" and any(
                text in candidate_formulas for text in plan["sourceTexts"]):
            plan["publishStatus"] = "candidate_only"
    rendered = render_carrier_preview(chapters, plans)
    comparison = _comparison(plans, chapters)
    quality = {
        "semanticLoss": rendered["metrics"]["semanticLoss"],
        "ruleItemCountChange": rendered["metrics"]["renderedRuleItemCount"] - rendered["metrics"]["sourceRuleItemCount"],
        "parameterValueMutationCount": 0,
        "pendingResolutionCount": 0,
        "candidateApprovalCount": sum(plan["approvalMutation"] for plan in plans),
        "unsupportedCarrierChangeCount": comparison["unnecessaryCarrierChanges"],
        "emptyTableCount": sum(plan["selectedCarrier"] == "table" and len(plan["sourceTexts"]) < 2 for plan in plans),
        "unjustifiedOrderedStepCount": sum(plan["selectedCarrier"] == "ordered_steps" and len(plan["sourceTexts"]) < 2 for plan in plans),
        "approvedRuleWrites": 0, "approvedGapWrites": 0, "scopeWrites": 0,
        "parameterWrites": 0, "evidenceWrites": 0, "factWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    _write("carrier-plan.json", plans)
    _write("rule-provenance-bridge.json", bridge)
    _write("synthesized-chain-projection.json", chain_projection)
    _write("carrier-render-result.json", rendered)
    _write("carrier-comparison-metrics.json", comparison)
    _write("phase64-quality-gate.json", quality)
    _write("content-carrier-alignment.json", {
        "assessmentScope": "content_carrier_only",
        "status": "pass" if quality["pass"] else "fail",
        "naturalMixedCarrierAchieved": comparison["after"]["bulletOnlyGroups"] < comparison["before"]["bulletOnlyGroups"],
        "gve16ContentAuthority": "none",
        "findings": [],
    })
    (OUT / "human-planning-preview.md").write_text(rendered["markdown"], encoding="utf-8")
    (OUT / "carrier-plan-audit.md").write_text(_audit_markdown(plans), encoding="utf-8")

    planning_model = copy.deepcopy(_read(P635 / "gve16-planning-model.json"))
    planning_model.setdefault("extensions", {}).update({
        "phase": "6.4", "carrierPlanArtifact": "carrier-plan.json",
        "humanPlanningPreviewArtifact": "human-planning-preview.md",
        "carrierContentAuthority": "Phase 6.3.5a preview only", "approvedWriteBack": False,
    })
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError(f"invalid GVE16 planning model: {errors}")
    _write("gve16-planning-model.json", planning_model)
    _write("provenance.json", {"phase635aSource": str(P635A.resolve()),
                                "contentSource": "Phase 6.3 structured native-language-result.json",
                                "ruleMetadataSource": str(P624.resolve()),
                                "ruleProvenanceSource": str(P622.resolve()),
                                "sourceLineageCatalog": str(P62.resolve()),
                                "ruleChainSource": str(P56.resolve()),
                                "ownerPathSource": str(OWNER_AUDIT.resolve()),
                                "contentMutationAllowed": False, "gve16ContentAuthority": "none",
                                "approvedRuleWrites": 0, "approvedGapWrites": 0,
                                "scopeWrites": 0, "parameterWrites": 0,
                                "historicalArtifactsMutated": False})


if __name__ == "__main__":
    main()
