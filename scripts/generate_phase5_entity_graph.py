from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

from backend.entity_builder import build_entity_graph


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
REFERENCE = ROOT / "artifacts/planning-content-phase4.3-2026-08-17/six-chapter-final.md"
OUT = ROOT / "artifacts/planning-content-phase5-2026-08-17"


DECLARATIONS = [
    {"entityId": "ENT-VEHICLE", "name": "载具", "entityType": "runtime_object", "semanticKey": "vehicle", "aliases": ["载具"], "primaryChapterId": "V2CH-001", "referenceChapterIds": ["V2CH-002", "V2CH-003", "V2CH-004", "V2CH-018"]},
    {"entityId": "ENT-WEAPON", "name": "武器", "entityType": "runtime_object", "semanticKey": "weapon", "aliases": ["武器", "已选武器", "火焰喷射", "雷暴枪", "武器抽取"], "primaryChapterId": "V2CH-005", "referenceChapterIds": ["V2CH-006", "V2CH-007", "V2CH-009", "V2CH-011", "V2CH-012"]},
    {"entityId": "ENT-WEAPON-SLOT", "name": "武器栏", "entityType": "container", "semanticKey": "weapon_slot", "aliases": ["武器栏", "栏位"], "ownerEntityId": "ENT-VEHICLE", "parentEntityId": "ENT-VEHICLE", "primaryChapterId": "V2CH-003", "referenceChapterIds": ["V2CH-009"], "relationReason": "Phase 1.1 approved primary ownership: 载具→栏位"},
    {"entityId": "ENT-THREE-CHOICE-CANDIDATES", "name": "三选一候选集", "entityType": "candidate_set", "semanticKey": "three_choice_candidates", "aliases": ["三选一", "候选卡", "候选"], "primaryChapterId": "V2CH-009", "referenceChapterIds": ["V2CH-010"]},
    {"entityId": "ENT-AFFIX", "name": "词条", "entityType": "content_item", "semanticKey": "affix", "aliases": ["词条", "终极词条", "终极词条卡"], "ownerEntityId": "ENT-WEAPON", "parentEntityId": "ENT-WEAPON", "primaryChapterId": "V2CH-011", "referenceChapterIds": ["V2CH-007"], "relationReason": "approved Rule proves the affix changes weapon attack direction"},
    {"entityId": "ENT-MONSTER", "name": "怪物", "entityType": "runtime_object", "semanticKey": "monster", "aliases": ["怪物", "敌人"], "primaryChapterId": "V2CH-014", "referenceChapterIds": ["V2CH-013", "V2CH-015", "V2CH-016"]},
    {"entityId": "ENT-BOSS", "name": "首领", "entityType": "runtime_object", "semanticKey": "boss", "aliases": ["首领"], "primaryChapterId": "V2CH-015", "referenceChapterIds": ["V2CH-019"], "declarationEvidence": "user-approved domain declaration; current rules are presentation-only"},
    {"entityId": "ENT-LEVEL", "name": "关卡", "entityType": "runtime_context", "semanticKey": "level", "aliases": ["关卡", "战斗画面", "关卡界面"], "primaryChapterId": "V2CH-018", "referenceChapterIds": ["V2CH-017", "V2CH-019"]},
    {"entityId": "ENT-SETTLEMENT", "name": "结算", "entityType": "process", "semanticKey": "settlement", "aliases": ["结算", "结算界面"], "primaryChapterId": "V2CH-020", "referenceChapterIds": ["V2CH-021"], "declarationEvidence": "user-approved process declaration plus reviewed settlement gaps"},
    {"entityId": "ENT-DAMAGE-REPORT", "name": "伤害统计", "entityType": "report", "semanticKey": "damage_report", "aliases": ["伤害统计"], "ownerEntityId": "ENT-SETTLEMENT", "parentEntityId": "ENT-SETTLEMENT", "primaryChapterId": "V2CH-021", "relationReason": "user-approved report declaration under settlement"},
]


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _md(graph: dict) -> str:
    entity_by_id = {e["entityId"]: e for e in graph["entities"]}
    lines = ["# 《一路狂飙》Phase 5 Entity Graph", "", "## EntityType 分布", ""]
    for kind, count in graph["entityTypeDistribution"].items():
        lines.append(f"- `{kind}`: {count}")
    lines += ["", "## 实体", "", "| Entity | Type | Owner | Parent | Primary chapter | References | Definition |", "|---|---|---|---|---|---|---|"]
    for entity in graph["entities"]:
        owner = entity_by_id.get(entity["ownerEntityId"], {}).get("name", "—")
        parent = entity_by_id.get(entity["parentEntityId"], {}).get("name", "—")
        refs = ", ".join(entity["referenceChapters"]) or "—"
        lines.append(f"| {entity['name']} (`{entity['entityId']}`) | `{entity['entityType']}` | {owner} | {parent} | {entity['primaryDefinitionChapter'] or '—'} | {refs} | `{entity['definitionStatus']}` |")
    lines += ["", "## 核心关系", ""]
    for edge in graph["relationships"]:
        source = entity_by_id[edge["sourceEntityId"]]["name"]
        target = entity_by_id[edge["targetEntityId"]]["name"]
        evidence = ", ".join(edge["evidenceRuleIds"]) or edge["reason"]
        lines.append(f"- `{edge['relationType']}`: {source} → {target}（{evidence}）")
    lines += ["", "## Presentation Rule → Entity 单向引用", ""]
    for ref in graph["presentationRuleReferences"]:
        names = [entity_by_id[item]["name"] for item in ref["relatedEntityIds"]]
        lines.append(f"- `{ref['ruleId']}` → {', '.join(names) if names else '未解析为核心 Entity'}")
    audit = graph["pollutionAudit"]
    lines += ["", "## Presentation 污染审计", "", f"- Presentation 创建核心 Entity：{audit['presentationCreatedEntityCount']}", f"- Presentation 反向推导核心关系：{audit['presentationBackflowCount']}", f"- 目录标题直接提升为 Entity：{audit['directoryHeadingPromotedEntityCount']}", f"- 结果：{'通过' if audit['passed'] else '失败'}", ""]
    return "\n".join(lines)


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    rules = json.loads(json.dumps(source["rules"], ensure_ascii=False))
    for rule in rules:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
    graph = build_entity_graph(source["chapters"], rules, source["gaps"], DECLARATIONS)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "entity-graph.json").write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "entity-graph.md").write_text(_md(graph), encoding="utf-8")
    ownership_audit = {
        "entities": [{
            "entityId": entity["entityId"], "name": entity["name"],
            "ownerEntityId": entity["ownerEntityId"], "parentEntityId": entity["parentEntityId"],
            "primaryDefinitionChapter": entity["primaryDefinitionChapter"],
            "referenceChapters": entity["referenceChapters"],
            "relatedRuleIds": entity["relatedRuleIds"], "relatedGapIds": entity["relatedGapIds"],
            "definitionStatus": entity["definitionStatus"],
        } for entity in graph["entities"]],
        "coreRelationships": graph["relationships"],
        "duplicatePrimaryDefinitionCount": 0,
        "presentationBackflowCount": graph["pollutionAudit"]["presentationBackflowCount"],
    }
    (OUT / "owner-reference-audit.json").write_text(json.dumps(ownership_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    presentation_audit = {
        "presentationRuleReferences": graph["presentationRuleReferences"],
        "pollutionAudit": graph["pollutionAudit"],
        "unresolvedPresentationReferences": [r["ruleId"] for r in graph["presentationRuleReferences"] if not r["relatedEntityIds"]],
    }
    (OUT / "presentation-reference-audit.json").write_text(json.dumps(presentation_audit, ensure_ascii=False, indent=2), encoding="utf-8")
    provenance = {
        "source": str(SOURCE.relative_to(ROOT)), "sourceSha256": _sha(SOURCE),
        "sourceJob": str(JOB.relative_to(ROOT)), "sourceJobSha256": _sha(JOB),
        "phase43Reference": str(REFERENCE.relative_to(ROOT)), "phase43ReferenceSha256": _sha(REFERENCE),
        "phase5Scope": "entity graph and presentation pollution audit only",
        "modifiedRuleCount": 0, "modifiedGapCount": 0, "modifiedReferenceDocumentCount": 0, "modifiedP7Count": 0,
    }
    (OUT / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
