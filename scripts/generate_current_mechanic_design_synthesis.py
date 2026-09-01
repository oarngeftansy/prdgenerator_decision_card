from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_design_synthesis import build_mechanic_review_view, synthesize_mechanic_design
from backend.planning_hierarchy_normalization import normalize_planning_hierarchy


SOURCE = ROOT / "artifacts/mechanic-requirement-ai-proposals-2026-08-18/ai-proposed-rules.json"
OUT = ROOT / "artifacts/mechanic-design-synthesis-2026-08-18"

GROUPS = [
    ("MDES-WEAPON", "武器获取、栏位与攻击", ["weapon.slot_activation", "weapon.damage_trigger"],
     ["entry", "core_processing", "next_state"], [["entry", "next_state"], ["core_processing"]]),
    ("MDES-DRAW", "独立武器抽取", ["draw.entry", "draw.result_commitment", "draw.downstream_effect"],
     ["entry", "core_processing", "exit", "next_state"], [["entry"], ["core_processing"], ["exit", "next_state"]]),
    ("MDES-CHOICE", "三选一", ["choice.temporary_state", "choice.exit"],
     ["entry", "core_processing", "exit", "next_state"], [["entry", "core_processing"], ["exit", "next_state"]]),
    ("MDES-MONSTER", "普通怪物行为", ["movement.state", "attack.entry", "attack.exit", "attack.post_exit_state", "attack.death_interrupt"],
     ["entry", "core_processing", "branch_or_repeat", "exit", "next_state"],
     [["entry"], ["core_processing"], ["branch_or_repeat"], ["exit"], ["next_state"]]),
    ("MDES-BOSS", "Boss 与关卡阶段", ["boss.entry", "boss.termination"],
     ["entry", "core_processing", "exit", "next_state"], [["entry", "core_processing"], ["exit", "next_state"]]),
    ("MDES-STATS", "伤害统计", ["statistics.start", "statistics.end"],
     ["entry", "core_processing", "exit", "next_state"], [["entry", "core_processing"], ["exit", "next_state"]]),
    ("MDES-OUTCOME", "胜负与结算", ["outcome.termination", "settlement.next_state"],
     ["entry", "core_processing", "exit", "next_state"], [["entry", "core_processing", "exit"], ["next_state"]]),
]

OWNER_PATHS = {
    "MDES-WEAPON": ["核心战斗", "武器", "获取、栏位与攻击"],
    "MDES-DRAW": ["局内成长", "独立武器抽取"],
    "MDES-CHOICE": ["局内成长", "三选一"],
    "MDES-MONSTER": ["怪物", "普通怪物", "行为逻辑"],
    "MDES-BOSS": ["关卡", "Boss 与关卡阶段"],
    "MDES-STATS": ["伤害统计", "统计规则"],
    "MDES-OUTCOME": ["关卡", "胜负与结算"],
}

PLANNING_TITLES = {
    "MDES-WEAPON": "武器", "MDES-DRAW": "独立抽取", "MDES-CHOICE": "三选一",
    "MDES-MONSTER": "普通怪物", "MDES-BOSS": "关卡流程",
    "MDES-STATS": "战斗统计", "MDES-OUTCOME": "关卡结果",
}

PLANNING_OWNER_BY_DIMENSION = {
    "weapon.slot_activation": ["核心战斗", "武器", "武器栏"],
    "weapon.damage_trigger": ["核心战斗", "武器", "攻击"],
    "draw.entry": ["局内成长", "独立抽取"],
    "draw.result_commitment": ["局内成长", "独立抽取"],
    "draw.downstream_effect": ["局内成长", "独立抽取"],
    "choice.temporary_state": ["局内成长", "三选一"],
    "choice.exit": ["局内成长", "三选一"],
    "movement.state": ["关卡推进", "怪物行为", "普通怪物", "移动"],
    "attack.entry": ["关卡推进", "怪物行为", "普通怪物", "攻击"],
    "attack.exit": ["关卡推进", "怪物行为", "普通怪物", "攻击"],
    "attack.post_exit_state": ["关卡推进", "怪物行为", "普通怪物", "攻击"],
    "attack.death_interrupt": ["关卡推进", "怪物行为", "普通怪物", "死亡处理"],
    "boss.entry": ["关卡推进", "关卡流程", "首领阶段"],
    "boss.termination": ["关卡推进", "关卡流程", "首领阶段"],
    "statistics.start": ["关卡结束", "战斗统计"],
    "statistics.end": ["关卡结束", "战斗统计"],
    "outcome.termination": ["关卡推进", "胜负判定"],
    "settlement.next_state": ["关卡结束", "结算"],
}

PLANNING_ORDER_BY_DIMENSION = {
    "weapon.slot_activation": 20, "weapon.damage_trigger": 30,
    "choice.temporary_state": 20, "choice.exit": 21,
    "draw.entry": 30, "draw.result_commitment": 31, "draw.downstream_effect": 32,
    "movement.state": 10, "attack.entry": 20, "attack.exit": 21,
    "attack.post_exit_state": 22, "attack.death_interrupt": 30,
    "boss.entry": 20, "boss.termination": 21,
    "statistics.start": 10, "statistics.end": 20,
    "outcome.termination": 30, "settlement.next_state": 10,
}

PARAMETERS = {
    "MDES-WEAPON": [{"parameterId": "PAR-WEAPON-DAMAGE", "text": "武器伤害", "consumerMechanicId": "MDES-WEAPON"}],
    "MDES-MONSTER": [{"parameterId": "PAR-CONTACT-DAMAGE", "text": "接触伤害", "consumerMechanicId": "MDES-MONSTER"},
                     {"parameterId": "PAR-ATTACK-INTERVAL", "text": "攻击间隔", "consumerMechanicId": "MDES-MONSTER"}],
    "MDES-STATS": [{"parameterId": "PAR-STATS-REFRESH", "text": "实时刷新频率（若启用）", "consumerMechanicId": "MDES-STATS"}],
}

CONFIRMED_RULES = {
    "MDES-WEAPON": [
        {"ruleId": "RULE-FFF28C63B44E", "text": "独立抽取结束后获得武器或技能。"},
        {"ruleId": "RULE-477C6F80B92D", "text": "武器自动攻击射程内的敌人。"},
    ],
    "MDES-DRAW": [{"ruleId": "RULE-CF719EA1E5E4", "text": "抽取滚动结束后展示3项结果。"}],
    "MDES-CHOICE": [
        {"ruleId": "RULE-A7829AA570B9", "text": "战斗等级提升时进入三选一。"},
        {"ruleId": "RULE-D4EA9E7B723E", "text": "界面生成3项候选，玩家选择其中1项。"},
    ],
    "MDES-MONSTER": [
        {"ruleId": "RULE-E63DC2C7A31E", "text": "怪物向载具方向移动。"},
        {"ruleId": "RULE-00320555D7EA", "text": "怪物接触载具后对载具造成伤害。"},
    ],
    "MDES-BOSS": [
        {"ruleId": "RULE-6297BE181A80", "text": "普通阶段之后进入首领阶段。"},
        {"ruleId": "RULE-37CB76D8A11F", "text": "Boss 消失后战斗仍继续运行。"},
    ],
    "MDES-STATS": [
        {"ruleId": "RULE-A87C8D4C1A10", "text": "结算按武器展示本局伤害统计。"},
        {"ruleId": "RULE-0D847899C3A9", "text": "结算展示本局总伤害及各武器伤害占比。"},
    ],
    "MDES-OUTCOME": [
        {"ruleId": "RULE-6D655A0E67FF", "text": "载具生命值归零时关卡失败。"},
        {"ruleId": "RULE-66E4A778C0D5", "text": "关卡完成后进入成功结算。"},
    ],
}


def main() -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    proposals = source["proposals"]
    by_dimension = {item["executionDimensionId"]: item for item in proposals}
    syntheses = []
    owners = {}
    for mechanic_id, title, dimensions, applicable_roles, roles in GROUPS:
        selected = [by_dimension[dimension] for dimension in dimensions]
        for proposal in selected:
            owners[proposal["proposalId"]] = [mechanic_id]
        items = []
        for sequence, (proposal, completeness_roles) in enumerate(zip(selected, roles), 1):
            text = proposal["proposalText"]
            if proposal["executionDimensionId"] == "draw.downstream_effect":
                text = "抽取结果确认后进入武器结果处理；处理完成后返回战斗。"
            items.append({"sequence": sequence, "text": text, "role": completeness_roles[0],
                          "completenessRoles": completeness_roles,
                          "proposalIds": [proposal["proposalId"]]})
        references = ([{"referenceId": "REF-DRAW-WEAPON-RESULT", "primaryMechanicId": "MDES-WEAPON",
                        "consumerMechanicId": "MDES-DRAW", "relation": "uses_weapon_result_processing",
                        "sourceProposalIds": [by_dimension["weapon.slot_activation"]["proposalId"]]}]
                      if mechanic_id == "MDES-DRAW" else [])
        synthesis = synthesize_mechanic_design(
            mechanic_spec={"mechanicDesignId": mechanic_id, "mechanicId": mechanic_id,
                           "planningTitle": PLANNING_TITLES[mechanic_id], "reviewTitle": title,
                           "ownerPath": OWNER_PATHS[mechanic_id],
                           "applicableRoles": applicable_roles, "items": items},
            proposals=selected, confirmed_rules=CONFIRMED_RULES.get(mechanic_id, []),
            parameter_placeholders=PARAMETERS.get(mechanic_id, []),
            rule_references=references, atomic_primary_owners={p["proposalId"]: [mechanic_id] for p in selected},
        )
        syntheses.append(synthesis)

    proposal_dimension = {item["proposalId"]: item["executionDimensionId"] for item in proposals}
    owner_assignments = []
    for synthesis in syntheses:
        for item in synthesis["recommendedDesign"]:
            dimension = proposal_dimension[item["sourceProposalIds"][0]]
            assignment = {
                "designItemId": item["designItemId"],
                "ownerPath": PLANNING_OWNER_BY_DIMENSION[dimension],
                "ownerEvidenceRefs": ["current-system-hierarchy-audit-2026-08-18"],
                "planningOrder": PLANNING_ORDER_BY_DIMENSION[dimension],
            }
            if dimension.startswith("movement.") or dimension.startswith("attack."):
                assignment["ownerSignals"] = [
                    {"ownerType": "entity", "ownerPath": ["怪物", "普通怪物"]},
                    {"ownerType": "flow", "ownerPath": ["关卡推进", "怪物行为"]},
                ]
            owner_assignments.append(assignment)
    owner_assignments.extend([
        {"contentId": "RULE-FFF28C63B44E", "ownerPath": ["核心战斗", "武器", "获取"],
         "contentSummary": "独立抽取结束后获得武器或技能。", "sourceRuleIds": ["RULE-FFF28C63B44E"],
         "sourceReviewUnitId": "MDES-WEAPON", "planningOrder": 10,
         "ownerEvidenceRefs": ["current-system-hierarchy-audit-2026-08-18"]},
        {"contentId": "RULE-A7829AA570B9", "ownerPath": ["局内成长", "战斗等级"],
         "contentSummary": "战斗等级提升时进入三选一。", "sourceRuleIds": ["RULE-A7829AA570B9"],
         "sourceReviewUnitId": "MDES-CHOICE", "planningOrder": 10,
         "ownerEvidenceRefs": ["current-system-hierarchy-audit-2026-08-18"]},
        {"contentId": "RULE-6297BE181A80", "ownerPath": ["关卡推进", "关卡流程", "普通阶段"],
         "contentSummary": "普通阶段完成后进入首领阶段。", "sourceRuleIds": ["RULE-6297BE181A80"],
         "sourceReviewUnitId": "MDES-BOSS", "planningOrder": 10,
         "ownerEvidenceRefs": ["current-system-hierarchy-audit-2026-08-18"]},
    ])
    normalization = normalize_planning_hierarchy(syntheses, owner_assignments)
    for synthesis in syntheses:
        for item in synthesis["recommendedDesign"]:
            assignment = normalization["assignments"][item["designItemId"]]
            item["planningNodeId"] = assignment["planningNodeId"]
            item["planningOwnerPath"] = assignment["ownerPath"]
            item["planningOwnerEvidenceRefs"] = assignment["ownerEvidenceRefs"]

    all_items = [item for synthesis in syntheses for item in synthesis["recommendedDesign"]]
    knowledge = Counter(item["knowledgeClass"] for item in all_items)
    payload = {
        "syntheses": syntheses,
        "metrics": {
            "mechanicCount": len(syntheses), "atomicProposalCount": len(proposals),
            "uniquePrimaryOwnerProposalCount": len(owners), "duplicateProposalMergedCount": 1,
            "crossProposalConflictCount": sum(len(s["coherenceFindings"]) + len(s["compatibilityFindings"]) for s in syntheses),
            "ruleReuseCount": sum(len(s["ruleReferences"]) for s in syntheses),
            "unclosedLifecycleCount": sum(len(s["unclosedLifecycleSlots"]) for s in syntheses),
            "knowledgeClassItemCounts": dict(knowledge),
            "confirmedRuleMutationCount": 0, "requirementStatusMutationCount": 0,
            "formalPublicationMutationCount": 0, "publicationEligibleMechanicCount": 0,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "mechanic-design-syntheses.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    queue = [build_mechanic_review_view(item, expand_lineage=False) for item in syntheses]
    (OUT / "mechanic-design-review-queue.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "review-hierarchy.json").write_text(
        json.dumps({"reviewUnits": normalization["reviewHierarchy"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    (OUT / "planning-hierarchy.json").write_text(
        json.dumps(normalization, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = ["# 《一路狂飙》Mechanic-level AI Design Review Preview", "",
             "> 内部主策审核产物；不是正式执行策划案，不产生 Confirmed Rule。", ""]
    for synthesis in syntheses:
        items = synthesis["recommendedDesign"]
        counts = Counter(item["knowledgeClass"] for item in items)
        confirmed_count = len(synthesis["confirmedRules"])
        placeholder_count = len(synthesis["parameterPlaceholders"])
        total = confirmed_count + len(items) + placeholder_count or 1
        inference_count = sum(item["knowledgeClass"] != "confirmed" for item in items)
        lines.extend([f"## {synthesis['reviewTitle']}", "", "### 已确认规则", ""])
        lines.extend(f"- {rule['text']}" for rule in synthesis["confirmedRules"])
        lines.extend(["", "### AI 推荐完整机制", ""])
        lines.extend(f"{item['sequence']}. {item['text']}" for item in items)
        lines.extend(["", "### 审核构成", "",
                      f"- Confirmed：{confirmed_count / total * 100:.1f}%",
                      f"- Inference：{inference_count / total * 100:.1f}%",
                      f"- Placeholder：{placeholder_count / total * 100:.1f}%",
                      f"- Mechanic Execution Completeness：{synthesis['executionCompleteness']['score']:.1f}%",
                      f"- Review Eligibility：{synthesis['reviewEligibility']}"])
        if synthesis["parameterPlaceholders"]:
            lines.extend(["", "### 待配置参数", ""])
            lines.extend(f"- {p['text']}：{{待配置}}" for p in synthesis["parameterPlaceholders"])
        if synthesis["ruleReferences"]:
            lines.extend(["", "### 规则复用", "", "- 抽取确认结果后调用武器结果处理，不重复定义入栏与重复武器规则。"])
        lines.extend(["", "操作：Accept Mechanic / Edit / Reject / Expand Evidence", ""])
    (OUT / "mechanic-level-ai-design-review-preview.md").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "review-hierarchy-preview.md").write_text("\n".join(lines), encoding="utf-8")

    planning_lines = ["# 《一路狂飙》Planning Hierarchy Preview", "",
                      "> 仅用于核对自然策划层级与内容归属，不是 Final Publication。", ""]
    nodes_by_path = {tuple(node["ownerPath"]): node for node in normalization["planningNodes"]}
    root_order = list(dict.fromkeys(assignment["ownerPath"][0] for assignment in owner_assignments))

    def render_path(path: tuple[str, ...]) -> None:
        node = nodes_by_path[path]
        planning_lines.extend([f"{'#' * len(path)} {path[-1]}", ""])
        for summary in node["designItemSummaries"]:
            planning_lines.append(f"- {summary}")
        if node["designItemSummaries"]:
            planning_lines.append("")
        children = [candidate for candidate in nodes_by_path
                    if len(candidate) == len(path) + 1 and candidate[:-1] == path]
        children.sort(key=lambda child: (nodes_by_path[child].get("planningOrder", 1000), child[-1]))
        for child in children:
            render_path(child)

    for root in root_order:
        render_path((root,))
    (OUT / "planning-hierarchy-preview.md").write_text("\n".join(planning_lines), encoding="utf-8")

    normalization_audit = ["# Planning Hierarchy Normalization Audit", "",
                           f"- Assignment Rate：{normalization['metrics']['assignmentRate']}%",
                           f"- Composite Planning Title：{normalization['metrics']['compositePlanningTitleCount']}",
                           f"- Duplicate Primary Planning Node：{normalization['metrics']['duplicatePrimaryPlanningNodeCount']}",
                           f"- Owner Structure Finding：{normalization['metrics']['ownerStructureFindingCount']}",
                           f"- Gate Passed：{normalization['metrics']['gatePassed']}", "",
                           "## Owner Structure Findings", ""]
    normalization_audit.extend(
        f"- {finding['designItemId']}：Entity/Flow/Lifecycle owner signals 存在职责分离风险；本轮未迁移 Owner。"
        for finding in normalization["ownerStructureFindings"]
    )
    normalization_audit.extend(["", "## Lineage", ""])
    normalization_audit.extend(
        f"- {item_id} → {assignment['planningNodeId']} → {' / '.join(assignment['ownerPath'])}"
        for item_id, assignment in normalization["assignments"].items()
    )
    (OUT / "planning-hierarchy-normalization-audit.md").write_text(
        "\n".join(normalization_audit) + "\n", encoding="utf-8")

    audit = ["# Mechanic Design Synthesis Audit", "",
             f"- Mechanic：{len(syntheses)}", f"- Atomic Proposal：{len(proposals)}",
             "- Duplicate Proposal merged：1", f"- Cross-Proposal Conflict：{payload['metrics']['crossProposalConflictCount']}",
             f"- Rule Reuse：{payload['metrics']['ruleReuseCount']}",
             f"- Unclosed Lifecycle：{payload['metrics']['unclosedLifecycleCount']}",
             "- Confirmed/Requirement/Final Publication mutation：0", ""]
    for synthesis in syntheses:
        audit.append(f"- {synthesis['reviewTitle']}：Completeness {synthesis['executionCompleteness']['score']:.1f}%，Atomic {len(synthesis['atomicProposalIds'])}")
    (OUT / "mechanic-design-synthesis-audit.md").write_text("\n".join(audit) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
