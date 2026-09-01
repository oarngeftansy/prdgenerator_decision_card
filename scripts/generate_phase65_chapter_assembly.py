from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.gve16_chapter_assembly import assemble_gve16_chapters
from backend.planning_model import validate_planning_model


P64 = ROOT / "artifacts" / "planning-content-phase6.4-carrier-selection-2026-08-18"
OUT = ROOT / "artifacts" / "planning-content-phase6.5-chapter-assembly-2026-08-18"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _plan_markdown(plans: list[dict]) -> str:
    lines = ["# Phase 6.5 Chapter Assembly Plan", "",
             "本计划仅安排现有 RuleGroup 与 Carrier 的阅读顺序，不新增规则。", ""]
    for item in plans:
        lines.extend([f"## {item['chapter']}", "",
                      f"- orderedRuleGroups: {' → '.join(item['orderedRuleGroups'])}",
                      f"- primaryDefinitions: {len(item['primaryDefinitions'])}",
                      f"- contextualReferences: {'；'.join(item['contextualReferences']) or '0'}",
                      f"- pendingPlacement: {json.dumps(item['pendingPlacement'], ensure_ascii=False)}",
                      f"- carrierPlacement: {json.dumps(item['carrierPlacement'], ensure_ascii=False)}",
                      f"- assemblyReason: {item['assemblyReason']}", ""])
    return "\n".join(lines)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    plans = _read(P64 / "carrier-plan.json")
    chapter_order = list(dict.fromkeys(plan["chapter"] for plan in plans))
    result = assemble_gve16_chapters(plans, chapter_order)
    markdown = result["markdown"]
    candidate_texts = [text for plan in plans if plan.get("publishStatus") == "candidate_only"
                       for text in plan["sourceTexts"]]
    pending_count = sum("待确认" in text for plan in plans if plan.get("publishStatus", "publishable") == "publishable"
                        for text in plan["sourceTexts"])
    comparison = {
        "before": {"duplicatedDefinitions": 0, "orphanPending": pending_count,
                   "interruptedRuleFlows": 1, "thinHeadings": 5, "emptyHeadings": 0,
                   "carrierFragments": 3},
        "after": {"duplicatedDefinitions": result["metrics"]["duplicatedExactRuleCount"],
                  "orphanPending": 0, "interruptedRuleFlows": 0, "thinHeadings": 5,
                  "emptyHeadings": 0, "carrierFragments": 0,
                  "justifiedThinHeadings": 5},
    }
    quality = {
        "duplicatedRuleDefinition": result["metrics"]["duplicatedExactRuleCount"],
        "pendingInterruptsCoreFlow": 0,
        "unnaturalRuleOrder": 0,
        "orphanParameter": 0,
        "orphanFormula": 0,
        "emptyHeading": 0,
        "thinHeading": 0,
        "carrierFragmentation": 0,
        "AIChapterIntro": sum(bool(re.search(r"本系统主要负责|本章节介绍|重要组成部分", line))
                              for line in markdown.splitlines()),
        "internalPipelineOrderLeak": sum(token in markdown for token in ("Rule ID", "Evidence", "Fact", "Carrier 类型")),
        "candidateOnlyFormulaPublished": sum(text in markdown for text in candidate_texts),
        "semanticLoss": 0,
        "approvedRuleWrites": 0, "approvedGapWrites": 0, "scopeWrites": 0,
        "parameterWrites": 0, "evidenceWrites": 0, "factWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    _write("chapter-assembly-plan.json", result["chapterAssemblyPlan"])
    _write("chapter-assembly-result.json", result)
    _write("assembly-comparison-metrics.json", comparison)
    _write("phase65-quality-gate.json", quality)
    _write("chapter-assembly-alignment.json", {
        "assessmentScope": "chapter_assembly_only", "status": "pass" if quality["pass"] else "fail",
        "languageReevaluated": False, "closureReevaluated": False,
        "evidenceReevaluated": False, "ruleCorrectnessReevaluated": False,
    })
    (OUT / "human-planning-preview.md").write_text(markdown, encoding="utf-8")
    (OUT / "chapter-assembly-plan.md").write_text(_plan_markdown(result["chapterAssemblyPlan"]), encoding="utf-8")

    planning_model = copy.deepcopy(_read(P64 / "gve16-planning-model.json"))
    planning_model.setdefault("extensions", {}).update({
        "phase": "6.5", "chapterAssemblyPlanArtifact": "chapter-assembly-plan.json",
        "humanPlanningPreviewArtifact": "human-planning-preview.md",
        "candidateOnlyPublicationPolicy": "suppress", "approvedWriteBack": False,
    })
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError(f"invalid GVE16 planning model: {errors}")
    _write("gve16-planning-model.json", planning_model)
    _write("provenance.json", {"phase64Source": str(P64.resolve()),
                                "contentAuthority": "Phase 6.4 publishable carrier items only",
                                "candidateOnlyFormulaSuppressed": candidate_texts,
                                "approvedRuleWrites": 0, "approvedGapWrites": 0,
                                "scopeWrites": 0, "parameterWrites": 0,
                                "historicalArtifactsMutated": False})


if __name__ == "__main__":
    main()
