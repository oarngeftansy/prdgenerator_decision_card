from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.core_loop_rule_projection import evaluate_projection_integrity, project_core_loop_rules


ROOT = Path(__file__).resolve().parents[1]
CHAINS = ROOT / "artifacts/planning-content-phase5.6-gameplay-rule-chains-2026-08-17/gameplay-rule-chains.json"
GROUPS = ROOT / "artifacts/planning-content-phase5.5-game-rule-groups-2026-08-17/game-rule-groups.json"
SCOPED = ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json"
ENTITY = ROOT / "artifacts/planning-content-phase5-2026-08-17/entity-graph.json"
RULES = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.7-core-loop-projection-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _markdown(result: dict[str, Any], report: dict[str, Any]) -> str:
    core = result["coreGameplayLoop"]
    lines = ["# Phase 5.7 Core Loop → System Rule Projection", "",
             "> Core Loop 只展示整体玩法；完整规则投影到唯一系统章节。未生成最终正文，未调用 ParameterResolver。", "",
             "## Core Gameplay Loop", "", " → ".join(core["steps"]), "",
             f"- definitionMode：`{core['definitionMode']}`", "- 完整规则定义：0", "",
             "## Rule → Primary Owner → Reference Owner", "",
             "| Rule | Role | Primary owner | Reference owner | Definition mode |",
             "|---|---|---|---|---|"]
    for p in result["ruleProjections"]:
        refs = ", ".join(p["referenceOwners"]) or "-"
        lines.append(f"| `{p['sourceRuleId']}` | `{p['ruleRole']}` | `{p['primaryOwner']}` | `{refs}` | `{p['definitionMode']}` |")
    lines += ["", "## Missing Link → Owner", ""]
    for item in result["missingLinkProjections"]:
        lines += [f"- {item['question']}", f"  - owner：`{item['primaryOwner']}`",
                  f"  - internal semantic：`{item['semanticKey']}`", f"  - sourceChain：`{item['sourceChainId']}`"]
    lines += ["", "## Projected System Chapter Skeleton", ""]
    for chapter in result["systemChapterSkeletons"]:
        lines += [f"### {chapter['chapterTitle']}（{chapter['chapterOwner']}）", ""]
        lines += [f"- 规则组：{', '.join(g['title'] for g in chapter['ruleGroups']) or '-'}",
                  f"- 完整定义：{', '.join(chapter['fullDefinitionRuleIds']) or '-'}",
                  f"- 短引用：{', '.join(chapter['shortReferenceRuleIds']) or '-'}",
                  f"- Missing Link：{', '.join(chapter['missingLinkProjectionIds']) or '-'}",
                  f"- Parameter carrier：{', '.join(chapter['parameterProjectionIds']) or '-'}",
                  f"- 来源 Chain：{', '.join(chapter['sourceChainIds']) or '-'}", ""]
    lines += ["## Projection Integrity", "", f"- qualityGate：`{report['qualityGate']}`",
              f"- Rule 完整定义重复数：{report['duplicateFullDefinitionCount']}",
              f"- Missing Link 无 owner：{report['missingLinkWithoutOwnerCount']}",
              f"- Core Loop 完整定义数：{report['coreLoopFullDefinitionCount']}",
              f"- 未追踪 Chain：{report['untrackedSourceChainCount']}",
              f"- Rule → Chain 追溯率：{report['ruleProjectionTraceabilityRate'] * 100:.2f}%", ""]
    return "\n".join(lines)


def generate_phase57(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = [CHAINS, GROUPS, SCOPED, ENTITY, RULES]
    before = {str(p.relative_to(ROOT)): _sha(p) for p in sources}
    chains = json.loads(CHAINS.read_text(encoding="utf-8"))
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))
    models = json.loads(SCOPED.read_text(encoding="utf-8"))
    entity = json.loads(ENTITY.read_text(encoding="utf-8"))
    rules = json.loads(RULES.read_text(encoding="utf-8"))["rules"]
    result = project_core_loop_rules(chains, groups, models, entity, rules)
    report = evaluate_projection_integrity(result)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "rule-projections.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "projection-integrity-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "core-loop-system-projection.md").write_text(_markdown(result, report), encoding="utf-8")
    after = {str(p.relative_to(ROOT)): _sha(p) for p in sources}
    summary = {"phase": "5.7-core-loop-system-rule-projection", "ruleProjectionCount": len(result["ruleProjections"]),
               "missingLinkProjectionCount": len(result["missingLinkProjections"]),
               "parameterProjectionCount": len(result["parameterProjections"]),
               "systemChapterCount": len(result["systemChapterSkeletons"]), "integrityGate": report["qualityGate"],
               "sourceFilesUnchanged": before == after, "modifiedApprovedRuleCount": 0, "modifiedApprovedGapCount": 0,
               "finalDocumentGenerated": False, "parameterResolverInvoked": False}
    (output_dir / "phase57-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase57(), ensure_ascii=False, indent=2))
