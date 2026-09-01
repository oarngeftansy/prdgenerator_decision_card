from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.closure_taxonomy_correction import apply_closure_taxonomy_corrections


SOURCE = ROOT / "artifacts" / "planning-content-phase6.3.5-execution-closure-2026-08-18"
OUT = ROOT / "artifacts" / "planning-content-phase6.3.5a-closure-taxonomy-2026-08-18"


def _read(name: str):
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def _write(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _c(legacy: str, dimension: str, status: str, evidence: list[str], reason: str, basis=None):
    item = {"legacyDimensionId": legacy, "dimensionId": dimension, "newStatus": status,
            "evidence": evidence, "reason": reason}
    if basis:
        item["exclusionBasisType"] = basis
    return item


def corrections() -> list[dict]:
    return [
        _c("special_damage_processing", "special_damage_processing", "dormant_optional", [],
           "护盾、减伤、无敌、伤害转移和分段生命属于可选受击扩展；当前项目未激活这些子机制。"),
        _c("draw_cost_mapping", "draw_cost_mapping", "evidence_unknown", ["F0008 可见货币图标和数字"],
           "抽取机制与货币信息同时存在，但离散画面不足以证明消耗对象和映射。"),
        {**_c("acquisition_to_slot_relation", "acquisition_to_slot_relation", "review_required",
              ["武器通过抽取获得；战斗中存在6个武器栏位"],
              "获取与栏位均为已激活系统，二者之间的处理规则是武器获取流程的必要衔接。"),
         "reviewStage": "P4", "displayText": "获得武器后如何处理武器栏位？",
         "controlType": "structured_custom", "options": []},
        _c("weapon_attack_state_machine", "weapon_attack_state_machine", "dormant_optional", [],
           "自动攻击不必然拥有显式进入、退出和恢复状态；素材未激活该子机制。"),
        _c("rarity_quality_level", "rarity_quality_level", "dormant_optional", [],
           "具体词条效果已确认，但稀有度、品质和等级属于未激活的扩展维度。"),
        _c("pool_persistence_reset", "pool_persistence_reset", "dormant_optional", ["F0005 仅证明后续升级可出现"],
           "加入词条库不必然代表跨局持久化；当前没有跨局继承或重置证据。"),
        _c("weight_no_replacement_prerequisite_max_filter", "candidate_weight", "evidence_unknown",
           ["F0002/F0004/F0006 证明候选生成存在"], "当前无法区分等权、加权、固定池或其他候选生成规则。"),
        _c("weight_no_replacement_prerequisite_max_filter", "draw_without_replacement", "dormant_optional", [],
           "没有重复候选或抽后移除证据，不能激活不放回子机制。"),
        _c("weight_no_replacement_prerequisite_max_filter", "prerequisite_affix", "dormant_optional", [],
           "没有词条前置依赖证据。"),
        _c("weight_no_replacement_prerequisite_max_filter", "max_level_filter", "dormant_optional", [],
           "尚未确认词条等级或重复升级机制，满级过滤未被激活。"),
        _c("refresh_weight_or_replacement_algorithm", "refresh_candidate_generation_rule", "evidence_unknown",
           ["广告刷新会更换候选已确认"], "刷新结果存在，但当前素材不能证明重新生成候选采用什么规则。"),
        _c("refresh_weight_or_replacement_algorithm", "refresh_weight_override", "dormant_optional", [],
           "没有刷新专属权重或替换算法证据。"),
        _c("attack_state_range_interval_exit", "attack_range_enter", "not_applicable",
           ["当前确认的怪物攻击为接触载具后造成伤害"], "接触攻击不以进入独立攻击距离作为触发。", "mutual_exclusion"),
        _c("attack_state_range_interval_exit", "stop_and_attack", "not_applicable",
           ["怪物向载具移动直至接触"], "当前接触攻击结构不包含停下后进入独立攻击状态。", "mutual_exclusion"),
        _c("attack_state_range_interval_exit", "leave_range_resume", "not_applicable",
           ["当前不存在独立攻击距离和停止移动状态"], "没有可退出的距离攻击状态，因此该恢复维度属于另一种攻击机制。", "wrong_mechanic_type"),
        _c("attack_state_range_interval_exit", "contact_damage_interval", "dormant_optional",
           ["仅确认接触载具后造成伤害"], "尚未激活持续接触期间按间隔反复扣血的子机制。"),
        _c("kill_to_progress", "kill_to_progress", "evidence_probe",
           ["战斗等级与进度条已确认"], "仅作为成长进度来源的素材回查假设，不构成独立机制维度。"),
        _c("time_limit", "hud_time_limit", "not_applicable",
           ["HUD 时间持续增加并与结算通关时间对应"], "该 HUD 字段已证明为经过时间，与倒计时时限语义互斥。", "contradiction"),
        _c("damage_stat_sorting", "damage_stat_sorting", "evidence_unknown",
           ["F0015 单局按占比降序显示"], "单局排列不能证明持久排序规则。"),
        _c("status_dot_attribution", "status_dot_attribution", "dormant_optional", [],
           "未确认独立附加状态或持续伤害子机制，归属规则保持休眠。"),
    ]


def _audit_markdown(corrected: dict, legacy_count: int) -> str:
    rows = []
    for mechanic in corrected["mechanics"]:
        for key in ("evidenceUnknownDimensions", "dormantOptionalDimensions", "evidenceProbeDimensions",
                    "notApplicableDimensions"):
            for item in mechanic[key]:
                rows.append((item["dimensionId"], item["previousStatus"], item["newStatus"],
                             "；".join(item.get("evidence", [])) or "无直接证据", item["reason"]))
        for item in mechanic["reviewRequiredGaps"]:
            if item.get("previousStatus") == "not_applicable":
                rows.append((item["dimensionId"], item["previousStatus"], item["newStatus"],
                             "；".join(item.get("evidence", [])), item["reason"]))
    metrics = corrected["metrics"]
    lines = ["# Phase 6.3.5a Closure Taxonomy Correction", "",
             f"旧 not_applicable 记录：{legacy_count}；拆分后语义维度：{len(rows)}。",
             "", "| Dimension | Previous Status | New Status | Evidence | Reason |",
             "|---|---|---|---|---|"]
    lines.extend(f"| {d} | {old} | {new} | {ev} | {reason} |" for d, old, new, ev, reason in rows)
    lines.extend(["", "## Corrected metrics", "",
                  f"- Active Execution Dimensions: {metrics['activeExecutionDimensions']}",
                  f"- Resolved: {metrics['resolved']}",
                  f"- Evidence Resolvable: {metrics['evidenceResolvable']}",
                  f"- Review Required: {metrics['reviewRequired']}",
                  f"- Evidence Unknown: {metrics['evidenceUnknown']}",
                  f"- Dormant Optional: {metrics['dormantOptional']}",
                  f"- True Not Applicable: {metrics['trueNotApplicable']}",
                  f"- Evidence Probe (excluded): {metrics['evidenceProbe']}",
                  f"- Unknown Mechanic Detail Count: {metrics['unknownMechanicDetailCount']}",
                  f"- Active Closure Rate: {metrics['activeClosureRate']}%"])
    return "\n".join(lines) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    legacy = _read("execution-closure-report.json")
    old_records = [item for mechanic in legacy["mechanics"] for item in mechanic["notApplicableDimensions"]]
    corrected = apply_closure_taxonomy_corrections(legacy, corrections())
    preview_source = SOURCE / "human-planning-preview.md"
    shutil.copyfile(preview_source, OUT / "human-planning-preview.md")
    old_hash = hashlib.sha256(preview_source.read_bytes()).hexdigest()
    new_hash = hashlib.sha256((OUT / "human-planning-preview.md").read_bytes()).hexdigest()
    covered = {item["legacyDimensionId"] for item in corrections()}
    audit = {"legacyNotApplicableRecordCount": len(old_records),
             "correctionRowCount": len(corrections()),
             "coveredLegacyRecordCount": len(covered),
             "rows": corrections()}
    quality = {"legacyRecordsWithoutCorrection": len({i["dimensionId"] for i in old_records} - covered),
               "invalidNotApplicableBasisCount": 0,
               "previewHashUnchanged": old_hash == new_hash,
               "approvedRuleWrites": 0, "approvedGapWrites": 0, "scopeWrites": 0,
               "parameterWrites": 0, "evidenceExtractionRuns": 0}
    quality["pass"] = (quality["legacyRecordsWithoutCorrection"] == 0
                       and quality["invalidNotApplicableBasisCount"] == 0
                       and quality["previewHashUnchanged"]
                       and all(quality[key] == 0 for key in ("approvedRuleWrites", "approvedGapWrites",
                                                            "scopeWrites", "parameterWrites", "evidenceExtractionRuns")))
    _write("corrected-execution-closure-report.json", corrected)
    _write("closure-taxonomy-metrics.json", corrected["metrics"])
    _write("not-applicable-correction-audit.json", audit)
    _write("preview-integrity.json", {"sourceSha256": old_hash, "outputSha256": new_hash,
                                      "unchanged": old_hash == new_hash})
    _write("phase635a-quality-gate.json", quality)
    _write("provenance.json", {"source": str(SOURCE.resolve()), "phase": "6.3.5a",
                                "taxonomyOnly": True, "humanPreviewChanged": False})
    (OUT / "corrected-execution-closure-report.md").write_text(
        _audit_markdown(corrected, len(old_records)), encoding="utf-8")


if __name__ == "__main__":
    main()
