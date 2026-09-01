from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.game_rule_synthesis import attach_approved_requirement_rules
from backend.gve16_carrier_selection import (
    append_synthesis_rules_to_chapters,
    build_carrier_plan,
    enrich_structured_chapters,
)
from backend.gve16_chapter_assembly import assemble_gve16_chapters
from backend.rule_provenance_bridge import build_rule_provenance_bridge, project_chains_to_synthesized_rules


P622 = ROOT / "artifacts/planning-content-phase6.2.2-game-rule-synthesis-2026-08-17"
P63 = ROOT / "artifacts/planning-content-phase6.3-native-language-2026-08-18"
P624 = ROOT / "artifacts/planning-content-phase6.2.4-instance-value-gate-2026-08-18"
P62 = ROOT / "artifacts/planning-content-phase6.2-content-richness-density-2026-08-17"
REQ = ROOT / "artifacts/mechanic-requirement-discovery-2026-08-18"
OWNER = ROOT / "artifacts/current-system-hierarchy-audit-2026-08-18/current-system-hierarchy-audit.json"
OUT = ROOT / "artifacts/mechanic-requirement-publication-2026-08-18"

# Benchmark wiring only. Owners come from the accepted current hierarchy audit;
# the reusable backend receives this as data and contains no game-specific owner rule.
OWNER_BY_MECHANIC = {
    "PMECH-B1DB0C6035A1": {"ownerChapter": "关卡结束", "ruleGroup": "战斗统计"},
    "PMECH-BBD7CED5E8D0": {"ownerChapter": "关卡推进", "ruleGroup": "关卡流程"},
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    baseline_synthesis = read(P622 / "game-rule-synthesis.json")
    approved_rules = read(REQ / "approved-business-rules.json")
    synthesis = attach_approved_requirement_rules(
        baseline_synthesis, approved_rules, owner_by_mechanic=OWNER_BY_MECHANIC)
    new_rules = [item for item in synthesis["gameRules"] if item.get("sourceRuleIds")]

    source_lines = [line for chapter in read(P62 / "all-chapter-preview.json")["chapters"]
                    for line in chapter.get("lines", [])]
    bridge = build_rule_provenance_bridge(synthesis["gameRules"], source_lines)
    chains = read(REQ / "gameplay-rule-chains-with-requirements.json")
    projection = project_chains_to_synthesized_rules(chains, bridge)

    native = read(P63 / "native-language-result.json")
    chapters = append_synthesis_rules_to_chapters(native["chapters"], new_rules)
    typed_rules = read(P624 / "semantic-typed-synthesized-rules.json") + new_rules
    chapters = enrich_structured_chapters(chapters, typed_rules, read(OWNER), projection)

    requirement_report = read(REQ / "current-requirements-probed.json")
    requirement_mechanics = {item["requirementId"]: item["mechanicId"]
                             for item in requirement_report.get("requirements", [])}
    review_items: dict[str, list[dict]] = {}
    for item in requirement_report.get("reviewItems", []):
        mechanic_id = requirement_mechanics.get(item["requirementId"])
        if mechanic_id:
            review_items.setdefault(mechanic_id, []).append(item)
    stats_section = next(
        section for chapter in chapters if chapter["title"] == "关卡结束"
        for section in chapter["sections"] if section["title"] == "战斗统计")
    for review in review_items.get("PMECH-B1DB0C6035A1", []):
        stats_section["items"][-1].setdefault("reviewAttachments", []).append({
            "requirementId": review["requirementId"], "text": review["question"]})

    plans = build_carrier_plan(chapters)
    assembly = assemble_gve16_chapters(plans, list(dict.fromkeys(plan["chapter"] for plan in plans)))
    markdown = assembly["markdown"]
    (OUT / "human-planning-preview.md").write_text(markdown, encoding="utf-8")

    write("game-rule-synthesis.json", synthesis)
    write("rule-provenance-bridge.json", bridge)
    write("synthesized-chain-projection.json", projection)
    write("structured-chapters.json", chapters)
    write("carrier-plan.json", plans)
    write("chapter-assembly-result.json", assembly)
    write("publication-integrity.json", {
        "sha256": hashlib.sha256(markdown.encode("utf-8")).hexdigest().upper(),
        "publishedRequirementRuleIds": [item["sourceRuleIds"][0] for item in new_rules],
        "unmappedPublishedRequirementRules": [item["ruleId"] for item in new_rules
                                                 if not bridge["synToRules"].get(item["ruleId"])],
        "lowLevelImplementationTerms": [term for term in ("DamageEvent", "底层事件", "监听哪些具体事件")
                                         if term in markdown],
        "forbiddenImmediateBossSettlement": "Boss死亡后立即结算" in markdown or "Boss 击败后立即结算" in markdown,
        "duplicateExactStatements": sum(
            count - 1 for text in {text for plan in plans for text in plan["sourceTexts"]}
            if (count := sum(text in plan["sourceTexts"] for plan in plans)) > 1
        ),
        "jobJsonModified": False,
    })


if __name__ == "__main__":
    main()
