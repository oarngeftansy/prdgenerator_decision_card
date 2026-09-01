from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.gameplay_rule_chain_reconstruction import evaluate_chain_coherence, reconstruct_gameplay_rule_chains


ROOT = Path(__file__).resolve().parents[1]
GROUPS = ROOT / "artifacts/planning-content-phase5.5-game-rule-groups-2026-08-17/game-rule-groups.json"
SCOPED = ROOT / "artifacts/planning-content-phase5.4.4-mechanic-scope-2026-08-17/scoped-game-rule-models.json"
ENTITY = ROOT / "artifacts/planning-content-phase5-2026-08-17/entity-graph.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.6-gameplay-rule-chains-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_steps(label: str, steps: list[dict[str, Any]]) -> list[str]:
    lines = [f"### {label}", ""]
    lines += [f"{index}. {step['text']}\n   - supportingRuleIds: {', '.join(step['ruleIds']) or '-'}"
              for index, step in enumerate(steps, 1)] or ["- 当前没有已确认步骤。"]
    lines.append("")
    return lines


def _markdown(chains: list[dict[str, Any]], report: dict[str, Any]) -> str:
    lines = ["# Phase 5.6 Gameplay Loop & Rule Chain Reconstruction", "",
             "> 仅重建已确认/strongly implied 玩法的规则链。Missing Link 不生成答案，不修改 Rule / Gap，不生成最终正文。", ""]
    for chain in chains:
        lines += [f"## {chain['title']}", ""]
        if chain["entry"]:
            lines += ["### Entry", "", f"- {chain['entry']['text']}",
                      f"  - supportingRuleIds: {', '.join(chain['entry']['ruleIds']) or '-'}", ""]
        else:
            lines += ["### Entry", "", "- 当前证据尚未确认该跨系统链的关卡进入方式。", ""]
        for label, field in (("Player Action", "playerAction"), ("System Response", "systemResponse"),
                             ("State Change", "stateChange"), ("Progression Result", "progressionResult"),
                             ("Exit / Next", "exitOrNext")):
            lines += _render_steps(label, chain[field])
        lines += ["### Missing Links", ""]
        lines += [f"- {link['question']}\n  - internal semantic: `{link['semanticKey']}`\n  - after: {link['afterStep']}"
                  for link in chain["missingLinks"]] or ["- 无。"]
        lines += ["", "### Gameplay Parameters in chain", ""]
        lines += [f"- {p['attachedTo']} → `{p['semantic']}` → `{p.get('contract', '待定义')}`"
                  for p in chain["gameplayParameters"]] or ["- 无。"]
        lines += ["", f"- supportingRuleIds：{', '.join(chain['supportingRuleIds']) or '-'}", ""]
    lines += ["## Chain Coherence Gate", "", f"- qualityGate：`{report['qualityGate']}`",
              f"- chainCount：{report['chainCount']}", f"- crossSystemChainCount：{report['crossSystemChainCount']}",
              f"- known Rule placement rate：{report['knownRulePlacementRate'] * 100:.2f}%",
              f"- classification-only chain：{report['classificationOnlyChainCount']}",
              f"- implementation detail pollution：{report['implementationDetailPollutionCount']}",
              f"- unreadable Missing Link：{report['unreadableMissingLinkCount']}", ""]
    return "\n".join(lines)


def generate_phase56(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    sources = [GROUPS, SCOPED, ENTITY]
    before = {str(p.relative_to(ROOT)): _sha(p) for p in sources}
    groups = json.loads(GROUPS.read_text(encoding="utf-8"))
    models = json.loads(SCOPED.read_text(encoding="utf-8"))
    entity = json.loads(ENTITY.read_text(encoding="utf-8"))
    chains = reconstruct_gameplay_rule_chains(groups, models, entity)
    report = evaluate_chain_coherence(chains, groups)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "gameplay-rule-chains.json").write_text(json.dumps(chains, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "chain-coherence-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "three-core-gameplay-chains.md").write_text(_markdown(chains, report), encoding="utf-8")
    after = {str(p.relative_to(ROOT)): _sha(p) for p in sources}
    summary = {"phase": "5.6-gameplay-loop-rule-chain-reconstruction", "chainCount": len(chains),
               "coherenceGate": report["qualityGate"], "knownRulePlacementRate": report["knownRulePlacementRate"],
               "sourceFilesUnchanged": before == after, "modifiedApprovedRuleCount": 0, "modifiedApprovedGapCount": 0,
               "finalDocumentGenerated": False, "parameterResolverInvoked": False}
    (output_dir / "phase56-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "provenance.json").write_text(json.dumps({"sourceHashes": before, **summary}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(generate_phase56(), ensure_ascii=False, indent=2))
