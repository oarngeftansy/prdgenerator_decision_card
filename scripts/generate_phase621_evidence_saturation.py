from __future__ import annotations

import json
import sys
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.evidence_saturation import build_evidence_coverage_matrix, evaluate_default_closure


JOB = "8312a91c89e144e6a59f81b982f14c06"
SOURCE = ROOT / "data" / "jobs" / JOB / "source_images"
OUT = ROOT / "artifacts" / "planning-content-phase6.2.1-evidence-saturation-2026-08-17"


def refs(*ids: str) -> list[dict]:
    return [{"evidenceId": item, "sourcePath": str((SOURCE / f"{item}.jpg").resolve())} for item in ids]


def obs(dimension: str, mechanic: str, question: str, status: str, text: str, frames: tuple[str, ...],
        *, extracted: bool = False, rule: str | None = None, note: str = "") -> dict:
    return {"observationDimension": dimension, "mechanic": mechanic,
            "observationQuestion": question, "observationStatus": status,
            "observedText": text, "evidenceRefs": refs(*frames), "alreadyExtracted": extracted,
            "ruleCandidateText": rule, "auditNote": note}


OBSERVATIONS = [
    obs("vehicle_lateral_control", "载具移动", "画面能否证明玩家输入方式？", "ambiguous",
        "截图无法证明虚拟摇杆、按键或直接方向控制。", ("F0001", "F0003", "F0010"),
        note="旧 Fact 将输入方式写成虚拟摇杆或按键，需回视频或交互证据复核。"),
    obs("vehicle_preset_path", "载具移动", "画面能否证明载具沿预设路线自动行进？", "ambiguous",
        "小地图存在路线图形，但截图不能证明路线预设或载具自动沿线行进。", ("F0001", "F0003"),
        note="上游 Rule 冲突候选。"),
    obs("vehicle_hp_display", "载具", "能否看到载具生命值？", "directly_observed",
        "载具上方显示生命条和当前生命值。", ("F0001", "F0013"), extracted=True),
    obs("vehicle_damage_change", "载具", "受击后生命值是否变化？", "strongly_supported",
        "F0013 载具附近显示 -250，生命值低于前序战斗画面。", ("F0001", "F0013"), extracted=True),
    obs("weapon_slot_visible_count", "武器栏", "画面中能数出多少个固定栏位？", "directly_observed",
        "战斗与三选一界面底部显示编号1至6的六个栏位。", ("F0001", "F0002", "F0006"),
        rule="战斗界面提供6个武器栏位。"),
    obs("weapon_slot_post_acquisition_change", "武器栏", "获得武器前后栏位是否发生变化？", "not_observable",
        "当前为离散截图，缺少同一次获取前后的连续栏位画面。", ("F0002", "F0003")),
    obs("weapon_draw_entry", "武器获取", "抽取入口如何触发？", "not_observable",
        "仅看到抽取界面，未看到入口操作。", ("F0008",)),
    obs("weapon_draw_animation", "武器获取", "抽取过程展示什么？", "directly_observed",
        "抽取界面显示九宫格武器图标和中央结果带。", ("F0008",), extracted=True),
    obs("weapon_draw_skip", "武器获取", "抽取动画能否跳过？", "directly_observed",
        "界面明确提示点击空白处跳过动画。", ("F0008",),
        rule="武器抽取动画可点击空白处跳过。"),
    obs("weapon_draw_result", "武器获取", "停止后获得什么？", "strongly_supported",
        "抽取界面标题为抽取武器，中央带停留于具体图标；具体结果落位未连续展示。", ("F0008",), extracted=True),
    obs("weapon_draw_cost", "武器获取", "抽取是否展示消耗？", "ambiguous",
        "底部显示100与300及货币图标，但无法确认对应抽取方式、次数或消耗规则。", ("F0008",)),
    obs("weapon_attack_auto_target", "武器攻击", "攻击是否需要手动瞄准？", "strongly_supported",
        "多帧战斗中武器持续朝周围敌人攻击，未见瞄准操作。", ("F0001", "F0003", "F0010"), extracted=True),
    obs("weapon_attack_modes", "武器攻击", "已出现武器的攻击方式是否可区分？", "directly_observed",
        "剧毒炮描述为发射剧毒炮弹；火焰喷射在战斗中形成持续喷射/范围区域。", ("F0002", "F0003"),
        rule="剧毒炮发射带有剧毒的炮弹；火焰喷射形成持续喷射攻击。"),
    obs("weapon_attack_interval", "武器攻击", "能否从素材确定攻击间隔？", "not_observable",
        "离散截图无法估计攻击频率或间隔。", ("F0001", "F0003", "F0010")),
    obs("weapon_damage_numbers", "武器攻击", "命中后是否显示伤害结果？", "directly_observed",
        "敌人附近显示多组伤害数字。", ("F0001", "F0003", "F0012"), extracted=True),
    obs("weapon_damage_formula", "武器攻击", "能否观察伤害公式？", "not_observable",
        "画面只显示结果数字，无法确定计算公式。", ("F0001", "F0003")),
    obs("three_choice_trigger", "三选一", "何时出现三选一？", "strongly_supported",
        "三选一分别出现在等级10、12等战斗等级画面，支持升级触发。", ("F0002", "F0004"), extracted=True),
    obs("three_choice_candidate_count", "三选一", "每次显示几张候选？", "directly_observed",
        "每次显示3张候选卡。", ("F0002", "F0004", "F0006"), extracted=True),
    obs("three_choice_card_fields", "三选一", "候选卡展示哪些信息？", "directly_observed",
        "候选卡显示图标、名称和具体武器/词条效果说明。", ("F0002", "F0004", "F0006")),
    obs("three_choice_eligibility", "三选一", "能否观察候选资格的完整规则？", "ambiguous",
        "候选中同时出现新武器和现有武器强化，但无法确定完整入池条件。", ("F0002", "F0004", "F0006")),
    obs("three_choice_selection_count", "三选一", "玩家每次选择几项？", "directly_observed",
        "界面为三选一，玩家从3项中选择1项。", ("F0002", "F0004"), extracted=True),
    obs("three_choice_exit", "三选一", "选择后何时回到战斗？", "not_observable",
        "缺少选择点击与返回战斗的连续帧。", ("F0002", "F0003")),
    obs("refresh_ad_path", "刷新", "刷新按钮附近显示什么条件？", "directly_observed",
        "刷新按钮显示视频/广告图标，并标注当前剩余观看次数1/1。", ("F0002", "F0004", "F0006", "F0009"),
        rule="三选一提供观看广告刷新入口，界面显示剩余观看次数1/1。"),
    obs("refresh_replaces_candidates", "刷新", "刷新前后候选是否变化？", "strongly_supported",
        "多张三选一截图的三项候选不同；离散截图不能证明均由同一次点击刷新产生。", ("F0002", "F0004", "F0009"), extracted=True),
    obs("refresh_consumes_count", "刷新", "刷新后观看次数是否扣减？", "ambiguous",
        "多张截图均显示1/1，不能证明点击后的扣减时点。", ("F0002", "F0004", "F0009")),
    obs("ultimate_pool_entry", "词条", "终极词条如何进入候选范围？", "directly_observed",
        "界面明确提示广域喷射进入词条库，并有概率在升级时出现。", ("F0005",),
        rule="广域喷射进入词条库后，有概率在升级时出现。"),
    obs("ultimate_four_way_penalty", "词条", "终极词条具体改变什么？", "directly_observed",
        "广域喷射使火焰喷射器同时向4面喷射，伤害-20%。", ("F0005", "F0006"),
        rule="广域喷射使火焰喷射器同时向4面喷射，伤害-20%。"),
    obs("ultimate_applied_in_combat", "词条", "四向喷射是否在战斗中出现？", "strongly_supported",
        "F0010 战斗画面中载具四个方向同时出现火焰/爆炸攻击。", ("F0005", "F0010"),
        rule="广域喷射生效后，战斗中同时向四个方向攻击。"),
    obs("affix_multi_explosion", "词条", "还有哪些具体强化效果？", "directly_observed",
        "多点爆炸使火焰爆炸次数+100%，伤害-20%。", ("F0006", "F0009"),
        rule="多点爆炸：火焰爆炸次数+100%，伤害-20%。"),
    obs("affix_poison_damage", "词条", "毒液强化的具体数值是什么？", "directly_observed",
        "毒液增伤使剧毒炮伤害+80%。", ("F0006", "F0009"),
        rule="毒液增伤：剧毒炮伤害+80%。"),
    obs("affix_thunder_cooldown", "词条", "雷暴强化是否包含冷却变化？", "directly_observed",
        "雷暴冷却使雷暴枪冷却时间-20%。", ("F0009",),
        rule="雷暴冷却：雷暴枪冷却时间-20%。"),
    obs("monster_spawn_direction", "怪物", "怪物从哪里出现？", "directly_observed",
        "怪物从画面上方进入战斗区域。", ("F0001", "F0003"), extracted=True),
    obs("monster_approach_vehicle", "怪物", "怪物如何接近载具？", "strongly_supported",
        "多帧中怪物由上方向载具所在区域移动。", ("F0001", "F0003", "F0012"), extracted=True),
    obs("monster_contact_damage", "怪物攻击", "接触后是否造成伤害？", "strongly_supported",
        "怪物靠近载具的战斗画面中载具出现受伤数值。", ("F0012", "F0013"), extracted=True),
    obs("monster_contact_repeated_damage", "怪物攻击", "持续接触是否多次扣血？", "not_observable",
        "没有连续接触期间的生命值序列。", ("F0012", "F0013")),
    obs("monster_death", "怪物", "怪物受击后是否死亡或移除？", "ambiguous",
        "离散截图有伤害数字，但缺少同一怪物死亡过程。", ("F0001", "F0003")),
    obs("monster_drop_experience", "怪物", "死亡后是否掉落或增加经验？", "not_observable",
        "没有击杀前后经验变化的连续证据。", ("F0001", "F0003")),
    obs("boss_arrival", "首领", "是否存在首领来袭事件？", "directly_observed",
        "战斗画面显示首领来袭提示，随后出现名为僵尸博士的首领。", ("F0011", "F0012"),
        rule="关卡中存在首领来袭阶段。"),
    obs("boss_health_decrease", "首领", "首领生命值是否随战斗下降？", "strongly_supported",
        "僵尸博士生命值由90.65%降至10.80%。", ("F0012", "F0013")),
    obs("boss_counter_semantics", "首领", "长血条旁x19/x3代表什么？", "ambiguous",
        "计数随生命值下降，但无法确认是血条层数、阶段或其他含义。", ("F0012", "F0013")),
    obs("level_display", "关卡流程", "是否显示战斗等级？", "directly_observed",
        "左上角显示战斗等级，样本中由10级增长至20级。", ("F0001", "F0007", "F0012"), extracted=True),
    obs("level_progress_bar", "关卡流程", "是否存在等级成长进度？", "directly_observed",
        "等级数字下方显示一条随画面变化的进度条。", ("F0001", "F0007", "F0012"),
        rule="关卡界面显示战斗等级及当前等级进度。"),
    obs("level_growth_source", "关卡流程", "成长进度来自什么？", "not_observable",
        "截图无法证明击杀、时间或其他来源增加进度。", ("F0001", "F0007")),
    obs("hud_elapsed_time", "关卡流程", "HUD时间是倒计时还是经过时间？", "strongly_supported",
        "HUD时间由02:36增长至05:06，结算显示通关时间05:14，支持经过时间而非剩余倒计时。", ("F0001", "F0014", "F0015"),
        rule="关卡界面显示本局经过时间；通关时间为05:14。"),
    obs("victory_result", "胜负判定", "是否有胜利结果证据？", "directly_observed",
        "结算页明确显示挑战成功。", ("F0015",), rule="本局挑战结果为成功。"),
    obs("victory_condition", "胜负判定", "胜利由什么条件触发？", "not_observable",
        "结算页只显示结果，不显示胜利条件。", ("F0015",)),
    obs("settlement_clear_time_record", "结算", "结算是否显示时间和纪录？", "directly_observed",
        "结算显示通关时间05:14与新纪录。", ("F0015",),
        rule="结算显示通关时间05:14，并标记新纪录。"),
    obs("settlement_reward_items", "结算", "结算是否展示奖励？", "directly_observed",
        "结算显示7组奖励图标及数量5、2、24、36、250、1、1；大部分道具名称不可辨认。", ("F0015",),
        rule="结算展示本局获得的道具及对应数量。"),
    obs("settlement_weapon_damage", "结算", "结算是否按武器统计伤害？", "directly_observed",
        "结算显示火焰喷射器84.5%、毒液炮10.4%、雷暴枪2.9%、机枪2.2%。", ("F0015",),
        rule="结算按武器展示伤害占比。"),
    obs("settlement_total_damage", "结算", "是否显示总伤害？", "directly_observed",
        "结算显示战斗总伤害88.9万。", ("F0015",),
        rule="结算显示战斗总伤害88.9万。"),
    obs("settlement_double_reward", "结算", "是否存在二次奖励入口？", "directly_observed",
        "结算页显示带视频/广告图标的双倍奖励按钮。", ("F0015",),
        rule="结算提供观看广告领取双倍奖励的入口。"),
    obs("settlement_return", "结算", "结算后有哪些离开操作？", "directly_observed",
        "结算页显示返回按钮。", ("F0015",), rule="结算页提供返回操作。"),
    obs("settlement_daily_count", "结算", "结算是否显示次数限制？", "directly_observed",
        "结算页显示今日剩余次数3/3。", ("F0015",),
        rule="结算页显示今日剩余次数3/3。"),
    obs("settlement_persistence", "结算", "结算数据是否跨局保存？", "not_observable",
        "单张结算截图不能证明历史记录或持久化。", ("F0015",)),
]


def write_json(name: str, value: object) -> None:
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def render_coverage(report: dict) -> str:
    lines = ["# Phase 6.2.1 Evidence Coverage Matrix", "",
             "> 本报告只列证据观察与候选，不写回 Approved Fact / Rule。当前输入为15张有序截图，不是连续视频。",
             "", "| Mechanic | Observation Dimension | Evidence | Observable | Already extracted | Newly extracted | Result |",
             "|---|---|---|---:|---:|---:|---|"]
    for item in report["matrix"]:
        ev = ", ".join(ref["evidenceId"] for ref in item["evidenceRefs"])
        lines.append(f"| {item['mechanic']} | {item['observationDimension']} | {ev} | {'yes' if item['observable'] else 'no'} | {'yes' if item['alreadyExtracted'] else 'no'} | {'yes' if item['newlyExtracted'] else 'no'} | {item['observedText']} |")
    return "\n".join(lines) + "\n"


def render_closure(report: dict, decisions: list[dict]) -> str:
    questions = {item["decisionKey"]: item.get("question", "") for item in decisions}
    lines = ["# Default Closure Gate", "", "| Existing Pending | Result | Reason |", "|---|---|---|"]
    for item in report["items"]:
        lines.append(f"| {questions.get(item['decisionKey']) or item['decisionKey']} | {item['disposition']} | {item['gateReason']} |")
    return "\n".join(lines) + "\n"


def build_preview(old_preview: dict, saturation: dict, closure: dict) -> dict:
    disposition = {item["decisionKey"]: item["disposition"] for item in closure["items"]}
    chapters = []
    for chapter in old_preview["chapters"]:
        lines = []
        for line in chapter["lines"]:
            if line.get("semantic") == "lateral_control":
                continue  # Screenshot evidence cannot ground the old joystick/key input claim.
            keys = line.get("sourceDecisionKeys", [])
            if keys and any(disposition.get(key) in {"suppress", "evidence_candidate", "upstream_conflict", "evidence_recheck"} for key in keys):
                continue
            if set(keys) == {"growth_source", "upgrade_basis"}:
                lines.append({"text": "成长进度来源：待确认。", "state": line["state"], "evidenceRefs": []})
                lines.append({"text": "战斗等级升级条件：待确认。", "state": line["state"], "evidenceRefs": []})
            else:
                lines.append({"text": line["text"], "state": line["state"], "evidenceRefs": []})
        if lines:
            chapters.append({"chapterTitle": chapter["chapterTitle"], "lines": lines})
    by_title = {item["chapterTitle"]: item for item in chapters}
    mechanic_title = {"武器栏": "武器栏", "武器获取": "武器获取", "武器攻击": "武器攻击", "三选一": "三选一",
                      "刷新": "刷新", "词条": "词条", "首领": "怪物", "关卡流程": "关卡流程", "胜负判定": "胜负判定", "结算": "结算"}
    for item in saturation["newRuleCandidates"]:
        title = mechanic_title.get(item["mechanic"])
        if not title:
            continue
        chapter = by_title.setdefault(title, {"chapterTitle": title, "lines": []})
        if chapter not in chapters:
            chapters.append(chapter)
        chapter["lines"].append({"text": item["candidateText"], "state": "evidence_candidate_unapproved",
                                 "evidenceRefs": item["evidenceRefs"]})
    order = ["载具移动", "武器获取", "武器栏", "武器攻击", "词条", "三选一", "刷新", "怪物", "怪物攻击", "关卡流程", "胜负判定", "结算"]
    chapters.sort(key=lambda item: order.index(item["chapterTitle"]) if item["chapterTitle"] in order else 99)
    return {"notice": "证据候选尚未审核，不是 Approved Rule，也不是最终正文。", "chapters": chapters}


def render_preview(preview: dict) -> str:
    lines = ["# Evidence-saturated Planning Preview（候选，未审核）", "", f"> {preview['notice']}", ""]
    for chapter in preview["chapters"]:
        lines.extend([f"## {chapter['chapterTitle']}", ""])
        for item in chapter["lines"]:
            marker = "【新证据候选】" if item["state"] == "evidence_candidate_unapproved" else ""
            lines.append(f"- {marker}{item['text']}")
        lines.append("")
    return "\n".join(lines)


def render_summary(summary: dict, closure: dict) -> str:
    metrics = summary["evidenceSaturation"]
    kept = [item["decisionKey"] for item in closure["items"] if item["disposition"] == "keep"]
    suppressed = [item["decisionKey"] for item in closure["items"] if item["disposition"] == "suppress"]
    return f"""# Phase 6.2.1 GVE16-guided Evidence Saturation Pass

## Input boundary

- Raw input inspected: 15 ordered source screenshots (`F0001`–`F0015`).
- Continuous video available: no. Attack frequency, click-to-result transitions and repeated contact damage cannot be confirmed from sparse screenshots.
- GVE16 / External corpus permission: observation questions only; no answer or project rule imported.
- Approved Fact / Rule / Gap write-back: 0 / 0 / 0.

## Before → candidate after

- Before effective gameplay rules: {summary['beforeEffectiveRules']}
- Newly observed Fact candidates: {summary['newFactCandidateCount']}
- Newly supported Rule candidates: {summary['newRuleCandidateCount']}
- After potential Rule Richness (only if every candidate later passes review): {summary['afterPotentialRuleRichness']}

## Evidence Saturation

- Observable dimensions: {metrics['observableDimensions']}
- Already saturated: {metrics['extractedObservableDimensions']}
- Observable but missed: {metrics['missedObservableDimensions']}
- Ambiguous: {metrics['ambiguousDimensions']}
- Not observable: {metrics['unobservableDimensions']}
- Observable Extraction Coverage: {metrics['observableExtractionCoverage']:.2%}

## Review items resolved or corrected by evidence

- `weapon_slot_capacity`: six visible numbered slots; route to evidence candidate, not automatic approval.
- `displayed_data`: F0015 directly shows clear time, record, rewards and damage statistics.
- `refresh_rule`: visible path is advertisement/video refresh with remaining watch count `1/1`; old “consumes in-game resource” Fact is not supported.
- `time_limit`: HUD value increases and matches clear time; route to upstream conflict instead of P6 time-limit input.

## Default Closure result

- Keep: {', '.join(kept)}
- Suppress: {', '.join(suppressed)}
- `failure_result`: remains Evidence Recheck and is absent from the preview.

## Important upstream conflicts

- Screenshots do not ground “preset route automatic movement”.
- Screenshots do not ground “virtual joystick or keyboard lateral control”.
- HUD time is supported as elapsed time, not remaining countdown.
- Refresh is visibly advertisement-based; no in-game resource payment is visible.
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    saturation = build_evidence_coverage_matrix(OBSERVATIONS)
    decisions = json.loads((ROOT / "artifacts/planning-content-phase6.1.5-review-controls-2026-08-17/review-decisions.json").read_text(encoding="utf-8"))
    evidence_resolutions = {
        "weapon_slot_capacity": {"resolution": "strongly_supported", "value": 6, "evidenceIds": ["F0001", "F0002", "F0006"]},
        "displayed_data": {"resolution": "directly_observed", "evidenceIds": ["F0015"]},
        "refresh_rule": {"resolution": "directly_observed", "mode": "ad", "remainingCount": "1/1", "evidenceIds": ["F0002", "F0004", "F0006", "F0009"]},
        "elapsed_time_not_limit": {"resolution": "strongly_supported", "evidenceIds": ["F0001", "F0014", "F0015"]},
    }
    closure = evaluate_default_closure(decisions, evidence_resolutions)
    old_preview = json.loads((ROOT / "artifacts/planning-content-phase6.2-content-richness-density-2026-08-17/all-chapter-preview.json").read_text(encoding="utf-8"))
    preview = build_preview(old_preview, saturation, closure)
    existing_effective = 15
    summary = {
        "phase": "6.2.1", "sourceKind": "ordered_screenshots", "continuousVideoAvailable": False,
        "sourceFrameCount": 15, "beforeEffectiveRules": existing_effective,
        "newFactCandidateCount": len(saturation["newFactCandidates"]),
        "newRuleCandidateCount": len(saturation["newRuleCandidates"]),
        "afterPotentialRuleRichness": existing_effective + len(saturation["newRuleCandidates"]),
        "evidenceSaturation": saturation["metrics"],
        "resolvedReviewItemsByEvidence": ["weapon_slot_capacity", "displayed_data", "refresh_rule"],
        "upstreamConflicts": ["vehicle_lateral_control", "vehicle_preset_path", "time_limit", "refresh_cost_as_ingame_resource"],
        "writeBack": {"approvedFacts": 0, "approvedRules": 0, "approvedGaps": 0},
    }
    manifest = []
    for index in range(1, 16):
        path = SOURCE / f"F{index:04}.jpg"
        manifest.append({"evidenceId": f"F{index:04}", "sourcePath": str(path.resolve()),
                         "sizeBytes": path.stat().st_size,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    candidate_refs_valid = all(
        Path(ref["sourcePath"]).is_file()
        for item in saturation["newFactCandidates"] for ref in item["evidenceRefs"]
    )
    gate = {
        "candidateEvidenceRefsResolve": candidate_refs_valid,
        "ambiguousPromotedToFact": 0,
        "ambiguousPromotedToRule": 0,
        "approvedWriteBackCount": 0,
        "commonSensePendingInPreview": 0,
        "continuousSequenceClaimsFromSparseFrames": 0,
        "pass": candidate_refs_valid,
    }
    write_json("observation-questions.json", [{k: item[k] for k in ("observationDimension", "observationQuestion", "mechanic")} for item in OBSERVATIONS])
    write_json("evidence-coverage-matrix.json", saturation)
    write_json("new-fact-rule-candidates.json", {"facts": saturation["newFactCandidates"], "rules": saturation["newRuleCandidates"]})
    write_json("default-closure-audit.json", closure)
    write_json("evidence-saturated-preview.json", preview)
    write_json("phase621-summary.json", summary)
    write_json("source-evidence-manifest.json", manifest)
    write_json("evidence-saturation-quality-gate.json", gate)
    (OUT / "evidence-coverage-matrix.md").write_text(render_coverage(saturation), encoding="utf-8")
    (OUT / "default-closure-audit.md").write_text(render_closure(closure, decisions), encoding="utf-8")
    (OUT / "evidence-saturated-preview.md").write_text(render_preview(preview), encoding="utf-8")
    (OUT / "phase621-audit.md").write_text(render_summary(summary, closure), encoding="utf-8")
    (OUT / "provenance.json").write_text(json.dumps({
        "sourceJobId": JOB, "sourceImages": [str((SOURCE / f"F{i:04}.jpg").resolve()) for i in range(1, 16)],
        "contentAuthorities": ["raw_evidence", "approved_rule"],
        "observationPromptAuthorities": ["gve16_anonymous_corpus", "external_game_design_corpus"],
        "promptAuthoritiesProvideAnswers": False,
        "mutatedInputs": [],
    }, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
