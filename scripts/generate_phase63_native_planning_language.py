from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.gve16_native_planning_language import (
    evaluate_gve16_language_smells,
    render_gve16_native_planning_language,
)
from backend.planning_model import validate_planning_model


P626 = ROOT / "artifacts" / "planning-content-phase6.2.6-hierarchy-flattening-2026-08-18"
STYLE = ROOT / "artifacts" / "planning-style-distillation-2026-08-17"
OUT = ROOT / "artifacts" / "planning-content-phase6.3-native-language-2026-08-18"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _audit_markdown(audit: list[dict[str, str]]) -> str:
    lines = ["# GVE16 Native Planning Language Audit", "",
             "本审计只记录同一规则语义的表达变化；GVE16 不作为内容来源。", "",
             "| Before sentence | After sentence | Why |", "|---|---|---|"]
    for item in audit:
        lines.append(f"| {item['beforeSentence']} | {item['afterSentence']} | {item['why']} |")
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    flattened = _read(P626 / "flattened-mechanic-rule-hierarchy.json")
    before = (P626 / "human-planning-preview.md").read_text(encoding="utf-8")
    result = render_gve16_native_planning_language(flattened)
    after = result["markdown"]
    smell_report = evaluate_gve16_language_smells(before, after, result["traceability"])
    source_rules = {rule_id for chapter in flattened["chapters"] for section in chapter["sections"]
                    for item in section["items"] for rule_id in item.get("supportingRuleIds", [])}
    source_dimensions = {dimension_id for chapter in flattened["chapters"] for section in chapter["sections"]
                         for item in section["items"] for dimension_id in item.get("sourceDimensionIds", [])}
    final_rules = {rule_id for item in result["traceability"] for rule_id in item["supportingRuleIds"]}
    final_dimensions = {dimension_id for item in result["traceability"] for dimension_id in item["sourceDimensionIds"]}
    quality = {
        "lostRuleSemanticCount": len(result["semanticCoverage"]["lostDimensionIds"]),
        "lostRuleProvenanceCount": len(source_rules - final_rules),
        "untraceableFinalSentenceCount": sum(
            not item["supportingRuleIds"] or not item["sourceDimensionIds"] for item in result["traceability"]),
        "unsupportedSemanticAddition": len(final_rules - source_rules) + len(final_dimensions - source_dimensions),
        "languageSmellCount": sum(smell_report["after"].values()),
        "hardSemanticLossCount": sum(smell_report["hardLosses"].values()),
        "internalIdLeakCount": sum(token in after for token in ("RSC-", "RULE-", "SYN-", "GAP-", "MB-", "VIS-")),
        "approvedRuleWrites": 0,
        "approvedGapWrites": 0,
        "scopeWrites": 0,
        "parameterWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    _write("native-language-result.json", result)
    _write("final-sentence-traceability.json", result["traceability"])
    _write("gve16-language-smell-report.json", smell_report)
    _write("phase63-quality-gate.json", quality)
    (OUT / "human-planning-preview.md").write_text(after, encoding="utf-8")
    (OUT / "language-audit.md").write_text(_audit_markdown(result["languageAudit"]), encoding="utf-8")

    planning_model = copy.deepcopy(_read(P626 / "gve16-planning-model.json"))
    planning_model.setdefault("extensions", {}).update({
        "phase": "6.3",
        "nativeLanguageArtifact": "native-language-result.json",
        "humanPlanningPreviewArtifact": "human-planning-preview.md",
        "styleProfileSource": str((STYLE / "planning_style_profile.yaml").resolve()),
        "styleProfileContentAuthority": "none",
        "approvedWriteBack": False,
    })
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError(f"invalid GVE16 planning model: {errors}")
    _write("gve16-planning-model.json", planning_model)
    _write("provenance.json", {
        "phase626Source": str(P626.resolve()),
        "styleProfileSource": str((STYLE / "planning_style_profile.yaml").resolve()),
        "styleProfileReadableScope": "renderer_allowlist + forbidden expressions only",
        "contentAuthority": "Phase 6.2.6 rule hierarchy",
        "approvedRuleWrites": 0, "approvedGapWrites": 0, "scopeWrites": 0, "parameterWrites": 0,
        "historicalArtifactsMutated": False,
    })


if __name__ == "__main__":
    main()
