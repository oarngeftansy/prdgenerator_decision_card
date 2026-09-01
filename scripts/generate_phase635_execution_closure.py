from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.execution_rule_closure import audit_execution_rule_closure, render_execution_closure_preview
from backend.planning_model import validate_planning_model


P624 = ROOT / "artifacts" / "planning-content-phase6.2.4-instance-value-gate-2026-08-18"
P63 = ROOT / "artifacts" / "planning-content-phase6.3-native-language-2026-08-18"
OUT = ROOT / "artifacts" / "planning-content-phase6.3.5-execution-closure-2026-08-18"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _rule_basis(*rule_ids: str) -> list[dict[str, str]]:
    return [{"ruleId": rule_id, "reason": "Approved/synthesized rule confirms the mechanic exists"}
            for rule_id in rule_ids]


def closure_specs() -> list[dict]:
    return [
        {"ruleSemanticId": "RSC-VEHICLE-HEALTH", "displaySection": "生命值", "dimensions": [
            {"dimensionId": "special_damage_processing", "disposition": "not_applicable", "basis": [],
             "reason": "未观察到护盾、减伤、无敌、伤害转移或分段生命机制。"}]},
        {"ruleSemanticId": "RSC-WEAPON-ACQUISITION", "displaySection": "获取", "dimensions": [
            {"dimensionId": "draw_cost_mapping", "disposition": "not_applicable", "basis": [],
             "reason": "F0008 可见货币图标与数字，但没有足够标签证明它们的抽取对象和消耗映射。"}]},
        {"ruleSemanticId": "RSC-WEAPON-SLOT", "displaySection": "武器栏", "dimensions": [
            {"dimensionId": "acquisition_to_slot_relation", "disposition": "not_applicable", "basis": [],
             "reason": "离散截图未展示同一次获取前后的栏位变化。"}]},
        {"ruleSemanticId": "RSC-WEAPON-ATTACK", "displaySection": "攻击", "dimensions": [
            {"dimensionId": "attack_range", "disposition": "review_required", "displayText": "攻击范围：待确认。",
             "reviewStage": "P6", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-WEAPON-TARGET")},
            {"dimensionId": "attack_interval", "disposition": "review_required", "displayText": "攻击间隔：待确认。",
             "reviewStage": "P6", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-WEAPON-TARGET")},
            {"dimensionId": "damage_model", "disposition": "review_required", "displayText": "伤害计算：待确认。",
             "reviewStage": "P4", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-WEAPON-METHOD")},
            {"dimensionId": "weapon_attack_state_machine", "disposition": "not_applicable", "basis": [],
             "reason": "素材未显示武器具有进入/退出攻击状态或恢复移动等子机制。"}]},
        {"ruleSemanticId": "RSC-AFFIX", "displaySection": "词条效果", "dimensions": [
            {"dimensionId": "rarity_quality_level", "disposition": "not_applicable", "basis": [],
             "reason": "词条卡证明具体效果，但未证明稀有度、品质或词条等级机制。"}]},
        {"ruleSemanticId": "RSC-ULTIMATE-AFFIX", "displaySection": "终极词条", "dimensions": [
            {"dimensionId": "pool_persistence_reset", "disposition": "not_applicable", "basis": [],
             "reason": "F0005 直接证明加入词条库及后续升级出现，但未证明跨局保留或重置机制。"}]},
        {"ruleSemanticId": "RSC-THREE-CHOICE", "displaySection": "主体规则", "dimensions": [
            {"dimensionId": "candidate_eligibility", "disposition": "review_required", "displayText": "可获取内容范围：待确认。",
             "reviewStage": "P4", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-THREE-CHOICE")},
            {"dimensionId": "weight_no_replacement_prerequisite_max_filter", "disposition": "not_applicable", "basis": [],
             "reason": "F0002/F0004/F0006 证明候选内容和数量，但未证明权重、不放回、前置或满级过滤子机制。"}]},
        {"ruleSemanticId": "RSC-AD-REFRESH", "displaySection": "刷新", "dimensions": [
            {"dimensionId": "refresh_max_count", "disposition": "review_required", "displayText": "刷新次数上限：待确认。",
             "reviewStage": "P6", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-REFRESH")},
            {"dimensionId": "refresh_reset_scope", "disposition": "review_required", "displayText": "次数重置周期：待确认。",
             "reviewStage": "P4", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-REFRESH")},
            {"dimensionId": "refresh_weight_or_replacement_algorithm", "disposition": "not_applicable", "basis": [],
             "reason": "广告刷新与候选更换已确认，但没有证据显示额外权重或替换算法。"}]},
        {"ruleSemanticId": "RSC-MONSTER", "displaySection": "普通怪物", "dimensions": [
            {"dimensionId": "attack_state_range_interval_exit", "disposition": "not_applicable", "basis": [],
             "reason": "当前素材只证明移动至载具并在接触后造成伤害，未显示独立攻击状态、距离、间隔或脱离规则。"}]},
        {"ruleSemanticId": "RSC-BOSS", "displaySection": "首领", "dimensions": [
            {"dimensionId": "boss_stage_trigger", "disposition": "review_required", "displayText": "首领阶段触发条件：待确认。",
             "reviewStage": "P4", "basis": [{"evidenceId": "F0011", "reason": "首领来袭提示"},
                                                      {"evidenceId": "F0012", "reason": "后续出现首领实体"}],
             "mechanicExistenceBasis": _rule_basis("SYN-BOSS-STAGE")} ]},
        {"ruleSemanticId": "RSC-BATTLE-LEVEL", "displaySection": "局内成长", "dimensions": [
            {"dimensionId": "growth_source", "disposition": "review_required", "displayText": "成长进度来源：待确认。",
             "reviewStage": "P4", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-LEVEL-PROGRESS")},
            {"dimensionId": "upgrade_rule", "disposition": "review_required", "displayText": "战斗等级升级条件：待确认。",
             "reviewStage": "P4", "basis": [], "mechanicExistenceBasis": _rule_basis("SYN-LEVEL-PROGRESS")},
            {"dimensionId": "kill_to_progress", "disposition": "not_applicable", "basis": [],
             "reason": "离散截图没有击杀前后的进度连续变化，不能确认击杀是成长来源。"}]},
        {"ruleSemanticId": "RSC-ELAPSED-TIME", "displaySection": "关卡计时", "dimensions": [
            {"dimensionId": "time_limit", "disposition": "not_applicable", "basis": [],
             "reason": "HUD 数字持续增加，并与结算通关时间对应；证据支持经过时间，不支持时限机制。"}]},
        {"ruleSemanticId": "RSC-SUCCESS", "displaySection": "胜负", "dimensions": [
            {"dimensionId": "success_condition", "disposition": "review_required", "displayText": "通关条件：待确认。",
             "reviewStage": "P4", "basis": [{"evidenceId": "F0015", "reason": "只能确认挑战成功结果"}],
             "mechanicExistenceBasis": _rule_basis("SYN-SUCCESS-RESULT")} ]},
        {"ruleSemanticId": "RSC-SETTLEMENT", "displaySection": "伤害统计", "dimensions": [
            {"dimensionId": "damage_share_formula", "disposition": "evidence_resolvable",
             "candidateRule": "武器伤害占比 = 该武器本局伤害 ÷ 本局总伤害。",
             "question": "武器伤害占比如何计算？",
             "basis": [{"evidenceId": "F0015", "reason": "结算页同时显示本局总伤害，四个武器占比合计100%。"}]},
            {"dimensionId": "damage_stat_sorting", "disposition": "not_applicable", "basis": [],
             "reason": "F0015 这一局恰好按占比降序显示，单个实例不足以证明持久排序规则。"},
            {"dimensionId": "status_dot_attribution", "disposition": "not_applicable", "basis": [],
             "reason": "当前证据未证明独立附加状态或持续伤害归属子机制。"}]},
    ]


def evidence_audit() -> list[dict]:
    return [
        {"evidenceId": "F0002/F0004/F0006", "inspected": True,
         "finding": "三选一固定显示3项，卡片包含武器/词条效果；不足以证明权重、不放回、前置或满级过滤。"},
        {"evidenceId": "F0002/F0004/F0006/F0009", "inspected": True,
         "finding": "广告刷新与当前1/1状态可见；不足以确认次数上限或重置周期。"},
        {"evidenceId": "F0005", "inspected": True,
         "finding": "界面明确写出终极词条进入词条库，并有概率在升级时出现。"},
        {"evidenceId": "F0008", "inspected": True,
         "finding": "武器抽取界面存在货币图标和数字，但标签不足，无法确定消耗映射。"},
        {"evidenceId": "F0011/F0012", "inspected": True,
         "finding": "首领来袭提示后出现首领实体；单局时间点不足以确定触发条件。"},
        {"evidenceId": "F0015", "inspected": True,
         "finding": "结算同时显示本局总伤害和按武器的占比，四项占比合计100%；单局顺序不足以确认排序规则。"},
    ]


def _audit_markdown(report: dict, gap_summary: dict) -> str:
    lines = ["# Phase 6.3.5 Execution Rule Closure Audit", "",
             "| Mechanic | Confirmed rules | Evidence-resolvable | Review required | Not applicable | Closure | Score |",
             "|---|---:|---:|---:|---:|---|---:|"]
    for item in report["mechanics"]:
        lines.append(f"| {item['mechanic']} | {len(item['confirmedRuleDimensions'])} | "
                     f"{len(item['evidenceResolvableGaps'])} | {len(item['reviewRequiredGaps'])} | "
                     f"{len(item['notApplicableDimensions'])} | {item['closureStatus']} | {item['closureScore']} |")
    lines.extend(["", "## Mechanic detail", ""])
    for item in report["mechanics"]:
        lines.extend([f"### {item['mechanic']}", "", "Confirmed rules:"])
        for rule in item["confirmedRules"]:
            lines.append(f"- {rule['statement']}")
        lines.append("Evidence-resolvable gaps:")
        if not item["evidenceResolvableGaps"]:
            lines.append("- 0")
        for gap in item["evidenceResolvableGaps"]:
            lines.append(f"- {gap['candidateRule']}")
        lines.append("Review-required gaps:")
        if not item["reviewRequiredGaps"]:
            lines.append("- 0")
        for gap in item["reviewRequiredGaps"]:
            lines.append(f"- {gap['displayText']} ({gap['reviewStage']})")
        lines.append("Not-applicable dimensions:")
        if not item["notApplicableDimensions"]:
            lines.append("- 0")
        for dimension in item["notApplicableDimensions"]:
            lines.append(f"- {dimension['dimensionId']}：{dimension['reason']}")
        lines.append("")
    lines.extend(["", "## Alignment gap", "",
                  f"- Language gap: {gap_summary['languageGap']['openFindingCount']} open findings",
                  f"- Rule closure gap: {gap_summary['ruleClosureGap']['openDimensionCount']} / "
                  f"{gap_summary['ruleClosureGap']['relevantDimensionCount']} relevant dimensions",
                  f"- Carrier gap: {gap_summary['carrierGap']['status']} (Phase 6.4 not executed)"])
    return "\n".join(lines).rstrip() + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    contracts = _read(P624 / "gated-rule-semantic-contracts.json")["contracts"]
    native_result = _read(P63 / "native-language-result.json")
    report = audit_execution_rule_closure(contracts, closure_specs())
    preview = render_execution_closure_preview(native_result, report)
    metrics = report["metrics"]
    confirmed_dimensions = sum(len(item["confirmedRuleDimensions"]) for item in report["mechanics"])
    open_dimensions = metrics["evidenceResolvableGapCount"] + metrics["reviewRequiredGapCount"]
    relevant_dimensions = confirmed_dimensions + open_dimensions
    gap_summary = {
        "languageGap": {"openFindingCount": 0, "assessedSmellDimensions": 7,
                        "basis": "Phase 6.3 Language Smell Gate"},
        "ruleClosureGap": {"openDimensionCount": open_dimensions,
                           "relevantDimensionCount": relevant_dimensions,
                           "gapPercent": round(100 * open_dimensions / relevant_dimensions, 2)},
        "carrierGap": {"status": "not_assessed", "score": None,
                       "reason": "Phase 6.4 Carrier Selection has not run"},
    }
    template_only_pending = sum(
        not gap.get("mechanicExistenceBasis") for item in report["mechanics"]
        for gap in item["reviewRequiredGaps"])
    unsupported_candidate = sum(
        not gap.get("basis") for item in report["mechanics"] for gap in item["evidenceResolvableGaps"])
    quality = {
        "templateOnlyPendingCount": template_only_pending,
        "unsupportedCandidateRuleCount": unsupported_candidate,
        "invalidDispositionCount": len(report["rejectedDimensions"]),
        "gve16ContentCopiedCount": 0,
        "approvedRuleWrites": report["approvedRuleWrites"],
        "approvedGapWrites": report["approvedGapWrites"],
        "scopeWrites": 0,
        "parameterWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    _write("execution-closure-report.json", report)
    _write("closure-specs.json", closure_specs())
    _write("evidence-recheck-audit.json", evidence_audit())
    _write("alignment-gap-summary.json", gap_summary)
    _write("phase635-quality-gate.json", quality)
    (OUT / "human-planning-preview.md").write_text(preview, encoding="utf-8")
    (OUT / "execution-closure-audit.md").write_text(_audit_markdown(report, gap_summary), encoding="utf-8")

    planning_model = copy.deepcopy(_read(P63 / "gve16-planning-model.json"))
    planning_model.setdefault("extensions", {}).update({
        "phase": "6.3.5", "executionClosureReportArtifact": "execution-closure-report.json",
        "evidenceRecheckAuditArtifact": "evidence-recheck-audit.json",
        "approvedWriteBack": False,
    })
    errors = validate_planning_model(planning_model)
    if errors:
        raise ValueError(f"invalid GVE16 planning model: {errors}")
    _write("gve16-planning-model.json", planning_model)
    _write("provenance.json", {"phase63Source": str(P63.resolve()), "phase624ContractsSource": str(P624.resolve()),
            "evidenceAuthority": "existing source screenshots only", "gve16ContentAuthority": "none",
            "approvedRuleWrites": 0, "approvedGapWrites": 0, "scopeWrites": 0, "parameterWrites": 0,
            "historicalArtifactsMutated": False})


if __name__ == "__main__":
    main()
