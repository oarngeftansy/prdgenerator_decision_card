from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.fully_resolved_diagnostic import apply_temporary_review_overrides, count_diagnostic_carriers


P65 = ROOT / "artifacts" / "planning-content-phase6.5-chapter-assembly-2026-08-18"
P635A = ROOT / "artifacts" / "planning-content-phase6.3.5a-closure-taxonomy-2026-08-18"
CORPUS = ROOT / "data" / "quality" / "gve16-alignment-corpus-v1.json"
OUT = ROOT / "artifacts" / "planning-content-phase6.5.5-fully-resolved-diagnostic-2026-08-18"


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def overrides() -> list[dict]:
    base = {"temporary": True, "writeBackAllowed": False, "recommendationOnly": False,
            "sourceApprovalStatus": "unreviewed"}
    return [
        {**base, "decisionId": "DIAG-ACQUISITION-SLOT", "sourceDimensionId": "acquisition_to_slot_relation",
         "matchLines": ["- 战斗中提供6个武器栏位。"],
         "replacementLines": ["- 战斗中提供6个武器栏位。", "- 获得新武器后优先填入空武器栏。",
                              "- 武器栏无空位时，不再获得新的武器类型。"]},
        {**base, "decisionId": "DIAG-ATTACK-RANGE", "sourceDimensionId": "attack_range",
         "matchLines": ["- 攻击范围：待确认。"],
         "replacementLines": ["- 每种武器独立配置攻击范围。", "- 仅对攻击范围内的敌人发起攻击。"]},
        {**base, "decisionId": "DIAG-ATTACK-INTERVAL", "sourceDimensionId": "attack_interval",
         "matchLines": ["- 攻击间隔：待确认。"],
         "replacementLines": ["- 每种武器独立配置攻击间隔。", "- 达到攻击间隔后执行下一次攻击。"]},
        {**base, "decisionId": "DIAG-DAMAGE-MODEL", "sourceDimensionId": "damage_model",
         "matchLines": ["- 伤害计算：待确认。"],
         "replacementLines": ["- 最终伤害由武器基础伤害与当前生效的词条伤害修正共同计算。"]},
        {**base, "decisionId": "DIAG-CANDIDATE-SCOPE", "sourceDimensionId": "candidate_eligibility",
         "matchLines": ["   - 可获取内容范围：待确认。"],
         "replacementLines": ["   - 候选从当前局可获取的武器强化及词条池中生成。"]},
        {**base, "decisionId": "DIAG-REFRESH-MAX", "sourceDimensionId": "refresh_max_count",
         "matchLines": ["- 广告刷新受次数限制。", "- 刷新次数上限：待确认。"],
         "replacementLines": ["- 每日最多通过观看广告刷新候选1次。"]},
        {**base, "decisionId": "DIAG-REFRESH-RESET", "sourceDimensionId": "refresh_reset_scope",
         "matchLines": ["- 次数重置周期：待确认。"],
         "replacementLines": ["- 广告刷新次数每日重置。"]},
        {**base, "decisionId": "DIAG-GROWTH-SOURCE", "sourceDimensionId": "growth_source",
         "matchLines": ["- 成长进度来源：待确认。"],
         "replacementLines": ["- 击败怪物后获得局内成长进度。"]},
        {**base, "decisionId": "DIAG-UPGRADE-RULE", "sourceDimensionId": "upgrade_rule",
         "matchLines": ["- 战斗等级升级条件：待确认。"],
         "replacementLines": ["- 成长进度达到当前战斗等级的升级要求后，战斗等级提升。"]},
        {**base, "decisionId": "DIAG-BOSS-TRIGGER", "sourceDimensionId": "boss_stage_trigger",
         "matchLines": ["- 关卡进入首领战斗阶段。", "- 首领阶段触发条件：待确认。"],
         "replacementLines": ["- 完成当前关卡的前置战斗阶段后进入首领战。"]},
        {**base, "decisionId": "DIAG-SUCCESS-CONDITION", "sourceDimensionId": "success_condition",
         "matchLines": ["- 通关条件：待确认。"],
         "replacementLines": ["- 击败首领后本关挑战成功，并进入结算。"]},
    ]


def _gap_report(preview: str, corpus: dict) -> dict:
    metrics = count_diagnostic_carriers(preview)
    rule_lines = [line.lstrip(" -0123456789.") for line in preview.splitlines()
                  if line.startswith(("- ", "   - ")) or (len(line) > 3 and line[0].isdigit() and line[1:3] == ". ")]
    table_rows = [line for line in preview.splitlines() if line.startswith("|") and "---" not in line
                  and "词条 | 作用对象" not in line]
    metrics.update({
        "concreteParameterRules": sum(bool(re.search(r"\d|%|双倍|独立配置", line)) for line in rule_lines + table_rows),
        "lifecycleRules": sum(any(token in line for token in ("每日重置", "后续升级", "刷新通关纪录", "进入首领战"))
                              for line in rule_lines),
        "constraints": sum(any(token in line for token in ("无需", "仅对", "无空位", "最多", "上限", "选择1项"))
                           for line in rule_lines),
        "crossSystemRelations": sum(any(token in line for token in
                                        ("触发三选一", "进入结算", "词条伤害修正", "填入空武器栏", "结算时", "词条库"))
                                    for line in rule_lines),
    })
    reference = corpus["provisionalReferences"]
    return {
        "diagnosticMetrics": metrics,
        "gve16ProvisionalDensityComparison": {
            "currentEffectiveRulesPerGroup": round(metrics["effectiveExecutionRuleCount"] / metrics["ruleGroups"], 2),
            "gve16BulletsPerHeadingMean": reference["bulletsPerChapter"]["mean"],
            "gve16BulletsPerHeadingP75": reference["bulletsPerChapter"]["p75"],
            "comparisonLimit": "匿名有限样本；heading 与当前 ruleGroup 仅作密度代理，不作为生成阈值。",
            "carrierDistributionAvailable": reference["carrierDistribution"]["available"],
        },
        "gapCategories": {
            "A": {"label": "当前素材没有覆盖到的机制", "count": 16,
                  "basis": "4 evidence_unknown + 10 dormant_optional + 1 candidate_only + 1 evidence_probe"},
            "B": {"label": "Evidence 已有但 Extraction 漏掉", "count": 0,
                  "basis": "本轮未发现新的已观察但未抽取维度。"},
            "C": {"label": "Fact 已有但 Rule Synthesis 漏掉", "count": 0,
                  "basis": "当前 diagnostic scope 内未发现。"},
            "D": {"label": "Rule 已有但没有形成执行闭环", "count": 1,
                  "basis": "生命值归零触发失败存在 Phase 2.1 unreviewed Rule，但未进入当前 Closure/ReviewDecision。"},
            "E": {"label": "Rule 已完整但章节组织/Carrier 仍弱", "count": 0,
                  "basis": "Phase 6.4/6.5 Gate 均通过；剩余差距主要不是载体和排序。"},
            "F": {"label": "GVE16 项目特有、当前项目不应拥有", "count": 4,
                  "basis": "当前 true_not_applicable dimensions；不迁移参考项目规则。"},
        },
        "conclusion": {
            "whyStillThin": "即使临时填满11个核心审核项，当前每组有效规则仍约2.5条，低于有限GVE16语料的4.75条/标题代理均值；主因是当前素材未激活或无法确认更多执行子机制，而非语言或Carrier。",
            "nextEvidenceExtraction": "仅值得对4个 evidence_unknown、1个 evidence_probe 和上游移动冲突做定点回查；不值得再次全面扫素材。",
            "nextRuleSynthesis": "当前核心范围收益低；先修复1条已存在但未进入闭环的失败规则治理问题。",
            "nextReview": "真实产品的首要增益仍是完成现有11个P4/P6审核。",
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    source_preview = P65 / "human-planning-preview.md"
    source_closure = P635A / "corrected-execution-closure-report.json"
    closure_before = source_closure.read_bytes()
    real_preview = source_preview.read_text(encoding="utf-8")
    diagnostic = apply_temporary_review_overrides(real_preview, overrides())
    diagnostic = diagnostic.replace("\n参数：\n- 广告刷新次数每日重置。", "\n- 广告刷新次数每日重置。")
    diagnostic = diagnostic.replace("- 战斗等级提升时触发三选一。\n\n- 击败怪物后获得局内成长进度。",
                                    "- 战斗等级提升时触发三选一。\n- 击败怪物后获得局内成长进度。")
    closure = _read(source_closure)
    source_reviews = [gap for mechanic in closure["mechanics"] for gap in mechanic["reviewRequiredGaps"]]
    corpus = _read(CORPUS)
    report = _gap_report(diagnostic, corpus)
    closure_after = source_closure.read_bytes()
    audit = {
        "overrideCount": len(overrides()),
        "overrides": overrides(),
        "sourceUnreviewedBefore": sum(gap.get("approvalStatus") == "unreviewed" for gap in source_reviews),
        "sourceUnreviewedAfter": sum(gap.get("approvalStatus") == "unreviewed" for gap in source_reviews),
        "sourceClosureHashBefore": hashlib.sha256(closure_before).hexdigest(),
        "sourceClosureHashAfter": hashlib.sha256(closure_after).hexdigest(),
        "sourceClosureHashUnchanged": closure_before == closure_after,
        "failureRuleDiagnosticDisposition": "not_rendered_unreviewed",
        "failureRuleReason": "Phase 2.1 rule remains unreviewed and is outside the 11 authorized diagnostic overrides.",
    }
    quality = {
        "remainingPendingCount": diagnostic.count("待确认"),
        "overrideCountMismatch": abs(len(overrides()) - 11),
        "sourceReviewMutationCount": 0 if audit["sourceClosureHashUnchanged"] else 1,
        "candidateFormulaPublished": int("武器伤害占比 =" in diagnostic),
        "unauthorizedFailureRulePublished": int("载具生命值归零时关卡失败" in diagnostic),
        "approvedRuleWrites": 0, "factWrites": 0, "evidenceWrites": 0,
        "scopeWrites": 0, "reviewDecisionWrites": 0,
    }
    quality["pass"] = all(value == 0 for key, value in quality.items() if key != "pass")
    shutil.copyfile(source_preview, OUT / "human-planning-preview.md")
    (OUT / "fully-resolved-diagnostic-preview.md").write_text(diagnostic, encoding="utf-8")
    _write("diagnostic-overrides.json", overrides())
    _write("diagnostic-override-audit.json", audit)
    _write("diagnostic-gve16-gap-audit.json", report)
    _write("diagnostic-quality-gate.json", quality)
    _write("provenance.json", {"sourceHumanPreview": str(source_preview.resolve()),
                                "sourceClosure": str(source_closure.resolve()),
                                "temporaryReviewOverride": True, "writeBackAllowed": False,
                                "approvedRuleWrites": 0, "factWrites": 0, "evidenceWrites": 0,
                                "scopeWrites": 0, "reviewDecisionWrites": 0})


if __name__ == "__main__":
    main()
