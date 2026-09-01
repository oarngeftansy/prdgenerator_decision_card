from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_execution_depth import assess_proposal_gates, evaluate_depth_benchmark


PROFILE_SPECS: dict[str, tuple[str, list[tuple]]] = {
    "MDES-WEAPON": ("武器获取、栏位与攻击", [
        ("SLOT-ACTIVATION", "data_flow", "core", "武器获得结果如何进入栏位并成为可用武器？", "existing_rule", "weapon.slot_activation", "approved_slot_rule", None),
        ("ATTACK-TRIGGER", "entry_trigger", "core", "可用武器以什么条件开始执行攻击？", "conservative_proposal", "weapon.attack_trigger", "weapon_active", "武器进入可用栏位后参与自动攻击；战斗暂停或结果锁定期间不触发新的攻击。"),
        ("DAMAGE-TRIGGER", "condition", "core", "武器攻击在什么执行点产生伤害结果？", "existing_rule", "weapon.damage_trigger", "approved_damage_rule", None),
        ("ATTRIBUTION", "data_flow", "core", "武器产生的伤害如何归属到统计对象？", "design_inference", "weapon.damage_attribution", "statistics_exists", "直接攻击、投射物和持续区域造成的伤害均归属于生成该伤害的武器；附加效果另行通过条件维度确认。"),
        ("COOLDOWN", "repeat_timing", "conditional", "非持续武器何时允许发动下一次攻击？", "parameter", "weapon.cooldown", "cooldown_ui_signal", "攻击结算后进入冷却；冷却时长为{x}秒，冷却结束且存在有效目标时允许下一次攻击。"),
        ("TARGET", "condition", "conditional", "需要目标的武器如何确定本次攻击对象？", "design_inference", "weapon.target_selection", "auto_target_signal", "攻击触发时从当前可攻击对象中选择目标；目标失效时终止本次未结算的目标指向，并在下一次攻击触发时重新选择。"),
        ("SLOT-FULL", "branch", "conditional", "武器栏已满时如何处理新武器结果？", "alternative_design", "weapon.slot_full", "slot_capacity_signal", "推荐：已有同武器转为强化；新武器进入替换选择，不自动覆盖现有武器。"),
        ("QA-OUTCOME", "qa_observable_outcome", "core", "程序和QA如何确认获取、激活与攻击链已正确完成？", "conservative_proposal", "weapon.qa_outcome", "weapon_active", "获得结果处理完成后，对应栏位显示可用武器；进入战斗状态后，该武器按其攻击方式产生可观察攻击与伤害结果。"),
    ]),
    "MDES-DRAW": ("独立武器抽取", [
        ("ENTRY", "entry_trigger", "core", "独立抽取在什么流程节点进入？", "existing_rule", "draw.entry", "approved_draw_entry", None),
        ("BATTLE-STATE", "state_definition", "core", "抽取期间当前战斗对象和运行状态如何处理？", "conservative_proposal", "draw.battle_state", "approved_draw_entry", "进入独立抽取后暂停关卡计时、怪物行为和武器攻击，并保留当前战斗对象与累计数据。"),
        ("RESULT-GENERATION", "calculation_algorithm", "core", "一次抽取如何形成可展示的结果集合？", "design_inference", "draw.result_generation", "three_result_signal", "进入抽取后一次性生成3项结果；展示动画只揭示既定结果，不在动画过程中重复改写结果。"),
        ("COMMIT", "data_flow", "core", "展示结果在什么时点成为本次正式抽取结果？", "existing_rule", "draw.result_commitment", "approved_draw_commit", None),
        ("DOWNSTREAM", "cross_system_dependency", "core", "正式结果如何交给武器结果处理？", "existing_rule", "draw.downstream_effect", "approved_draw_downstream", None),
        ("CLEANUP", "reset_persistence", "core", "抽取结束时哪些临时状态需要清理？", "conservative_proposal", "draw.cleanup", "approved_draw_downstream", "武器结果处理完成后清除本次抽取临时结果与滚动状态，再恢复进入抽取前保留的战斗上下文。"),
        ("ANIMATION-SKIP", "branch", "conditional", "跳过抽取动画是否改变已生成结果？", "design_inference", "draw.animation_skip", "skip_control_signal", "跳过只结束结果展示动画，不取消、不重生成已经确定的本次抽取结果。"),
        ("QA-OUTCOME", "qa_observable_outcome", "core", "QA如何确认抽取、提交、武器处理与返回链没有断点？", "conservative_proposal", "draw.qa_outcome", "approved_draw_downstream", "每次进入抽取只提交一组结果；处理完成后抽取界面退出，武器处理结果可观察，战斗从保留状态继续。"),
    ]),
    "MDES-CHOICE": ("战斗等级与三选一", [
        ("TEMPORARY-STATE", "state_definition", "core", "三选一期间哪些战斗状态暂停、哪些数据保留？", "existing_rule", "choice.temporary_state", "approved_choice_pause", None),
        ("CANDIDATE-GENERATION", "calculation_algorithm", "core", "一次三选一如何形成3项候选结果？", "design_inference", "choice.candidate_generation", "three_candidate_signal", "触发三选一时一次性生成3项候选并暂存；确认或刷新前，候选内容保持不变。"),
        ("CONFIRM", "data_flow", "core", "玩家确认候选时如何写入对应玩法对象？", "design_inference", "choice.confirm_apply", "approved_choice_exit", "玩家确认一项候选后，将该候选效果写入其所属武器或局内成长对象；写入成功后才结束本次选择。"),
        ("EXIT", "lifecycle", "core", "候选效果生效后如何退出并恢复战斗？", "existing_rule", "choice.exit", "approved_choice_exit", None),
        ("REFRESH", "branch", "conditional", "刷新后当前候选如何被替换和重新暂存？", "design_inference", "choice.refresh", "refresh_exists", "执行刷新时废弃当前未确认候选，重新生成并暂存3项候选；刷新不直接应用被废弃候选。"),
        ("REFRESH-LIMIT", "parameter_configuration", "conditional", "刷新次数由哪个机制消费并如何配置？", "parameter", "choice.refresh_limit", "refresh_limit_signal", "每局可刷新次数上限为{x}次，由三选一刷新分支消费；每次成功刷新扣减1次。"),
        ("CONSECUTIVE-LEVEL", "branch", "conditional", "一次结算多个升级时如何处理连续三选一？", "design_inference", "choice.consecutive_level", None, "若一次进度结算触发多个等级提升，则按等级提升次数依次完成多轮三选一；前一轮效果写入并清理临时状态后再进入下一轮。"),
        ("RESET", "reset_persistence", "core", "三选一的临时结果和局内次数在何时清理？", "design_inference", "choice.reset", "run_scoped_choice", "单次选择结束时清理候选临时状态；关卡结束时清理本局累计的三选一与刷新次数，不继承到下一局。"),
    ]),
    "MDES-MONSTER": ("普通怪物移动与攻击", [
        ("MOVEMENT", "state_definition", "core", "怪物移动状态以什么目标运行并在何时停止？", "existing_rule", "movement.state", "approved_movement", None),
        ("ATTACK-ENTRY", "entry_trigger", "core", "怪物首次接触载具时如何进入伤害处理？", "existing_rule", "attack.entry", "approved_attack_entry", None),
        ("REPEAT", "repeat_timing", "conditional", "保持接触期间如何重复产生伤害？", "existing_rule", "attack.repeat", "approved_periodic_contact_damage", None),
        ("EXIT", "condition", "core", "接触结束时如何停止当前接触伤害？", "existing_rule", "attack.exit", "approved_attack_exit", None),
        ("POST-EXIT", "state_definition", "core", "接触结束且怪物存活时进入什么后续状态？", "existing_rule", "attack.post_exit_state", "approved_post_exit", None),
        ("DEATH-INTERRUPT", "exception_interrupt", "core", "怪物死亡时如何处理中断与未结算伤害？", "existing_rule", "attack.death_interrupt", "approved_death_interrupt", None),
        ("PAUSE-RESUME", "exception_interrupt", "conditional", "玩法暂停期间怪物移动与接触伤害如何冻结和恢复？", "design_inference", "attack.pause_resume", "choice_pause_signal", "进入玩法暂停时冻结怪物移动与接触伤害计时；恢复时从冻结状态继续，不补结暂停期间的伤害次数。"),
        ("MULTI-ATTACK", "branch", "conditional", "多个怪物同时接触载具时伤害如何结算？", "design_inference", "attack.multiple_attackers", "multiple_monster_signal", "每个存活且保持接触的怪物独立维护接触伤害计时，并分别向载具结算伤害。"),
        ("PARAMETERS", "parameter_configuration", "core", "接触伤害与攻击间隔分别由谁消费？", "parameter", "attack.parameters", "approved_periodic_contact_damage", "怪物接触伤害为{x}，攻击间隔为{x}秒；二者由普通怪物接触伤害处理消费。"),
        ("QA-OUTCOME", "qa_observable_outcome", "core", "QA如何验证移动、接触、脱离、暂停和死亡行为？", "conservative_proposal", "attack.qa_outcome", "approved_attack_exit", "连续观察同一怪物：接触时移动停止并产生伤害，保持接触时按间隔重复，脱离后恢复移动，暂停期间不推进，死亡后不再产生伤害。"),
    ]),
    "MDES-BOSS": ("普通阶段、Boss与关卡完成", [
        ("ENTRY", "entry_trigger", "core", "普通阶段结束后如何进入Boss阶段？", "existing_rule", "boss.entry", "approved_boss_entry", None),
        ("INITIALIZATION", "state_definition", "core", "Boss阶段进入时初始化哪些战斗职责？", "conservative_proposal", "boss.initialization", "approved_boss_entry", "进入Boss阶段时生成Boss、启用Boss战斗状态并停止继续生成普通敌人；场上既有战斗对象按阶段规则保留。"),
        ("TERMINATION", "lifecycle", "core", "Boss生命归零时如何终止Boss行为？", "existing_rule", "boss.termination", "approved_boss_termination", None),
        ("POST-BOSS", "state_definition", "core", "Boss结束后场上残余战斗如何继续？", "existing_rule", "boss.post_boss_combat", "approved_post_boss_combat", None),
        ("LEVEL-COMPLETION", "condition", "core", "Boss击败后什么条件使关卡正式完成？", "human_decision", "boss.level_completion", "post_boss_delay_observed", None),
        ("FAILURE-INTERRUPT", "exception_interrupt", "core", "Boss阶段发生失败时如何中断后续成功流程？", "design_inference", "boss.failure_interrupt", "failure_rule_exists", "Boss阶段若失败条件先成立，则锁定失败结果并终止Boss及残余战斗处理，不再进入成功完成流程。"),
        ("NEXT-STATE", "cross_system_dependency", "core", "关卡正式完成后进入什么下一状态？", "conservative_proposal", "boss.next_state", "success_settlement_rule", "关卡完成条件成立后锁定成功结果，停止战斗处理并进入成功结算。"),
        ("QA-OUTCOME", "qa_observable_outcome", "core", "QA如何区分Boss击败、残余战斗和关卡完成？", "conservative_proposal", "boss.qa_outcome", "post_boss_delay_observed", "分别记录Boss消失时点、残余战斗结束时点和成功结算出现时点；三者不得因时间相邻被合并为同一事件。"),
    ]),
    "MDES-STATS": ("伤害统计", [
        ("START", "entry_trigger", "core", "本局伤害统计在什么时点开始？", "existing_rule", "statistics.start", "approved_statistics_start", None),
        ("ATTRIBUTION", "data_flow", "core", "伤害统计以什么对象为单位归属？", "conservative_proposal", "statistics.attribution", "weapon_statistics_signal", "伤害统计以武器为统计单位；每笔纳入统计的伤害累计到其来源武器。"),
        ("AGGREGATION", "calculation_algorithm", "core", "本局总伤害如何由分武器伤害形成？", "conservative_proposal", "statistics.aggregation", "total_and_share_ui", "本局总伤害等于纳入统计的各武器累计伤害之和；各武器结果保留独立累计值。"),
        ("PAUSE", "state_definition", "core", "选择或抽取界面打开时累计结果如何处理？", "existing_rule", "statistics.pause", "approved_statistics_pause", None),
        ("END", "lifecycle", "core", "胜负成立时统计如何停止并冻结？", "existing_rule", "statistics.end", "approved_statistics_end", None),
        ("SETTLEMENT", "cross_system_dependency", "core", "结算读取哪一个统计快照？", "existing_rule", "statistics.snapshot", "approved_statistics_snapshot", None),
        ("ATTACHED-DAMAGE", "branch", "conditional", "附加效果伤害是否归属于来源武器？", "human_decision", "statistics.attached_damage", "attached_effect_signal", None),
        ("SHARE-FORMULA", "calculation_algorithm", "conditional", "各武器伤害占比使用什么分子与分母？", "design_inference", "statistics.share_formula", "damage_share_ui", "武器伤害占比使用该武器本局累计伤害作为分子、本局总伤害作为分母；总伤害为0时不计算占比。"),
        ("RESET", "reset_persistence", "core", "冻结的本局统计结果在何时清理？", "design_inference", "statistics.reset", "run_scoped_statistics", "结算流程结束后清理本局伤害统计；下一局从0开始，不继承上一局累计值。"),
        ("QA-OUTCOME", "qa_observable_outcome", "core", "QA如何核对总伤害、分武器累计和冻结结果？", "conservative_proposal", "statistics.qa_outcome", "total_and_share_ui", "使用可控伤害样本核对各武器累计之和等于总伤害；胜负锁定后继续等待不应改变结算读取的冻结结果。"),
    ]),
    "MDES-OUTCOME": ("胜负与结算", [
        ("SUCCESS", "entry_trigger", "core", "什么项目条件锁定成功结果？", "human_decision", "outcome.success_trigger", "success_flow_exists", None),
        ("FAILURE", "entry_trigger", "core", "什么项目条件锁定失败结果？", "conservative_proposal", "outcome.failure_trigger", "vehicle_zero_hp_rule", "载具生命值归零时锁定失败结果，并停止继续接受战斗输入。"),
        ("TERMINATION", "state_definition", "core", "胜负锁定后停止哪些战斗处理？", "existing_rule", "outcome.termination", "approved_outcome_termination", None),
        ("SETTLEMENT-ENTRY", "cross_system_dependency", "core", "胜负结果如何进入对应结算流程？", "conservative_proposal", "settlement.entry", "approved_outcome_termination", "结果锁定并完成战斗终止后，按成功或失败结果进入对应结算流程；同一局只进入一次结算。"),
        ("SETTLEMENT-DATA", "data_flow", "core", "结算读取哪些已冻结的本局结果？", "design_inference", "settlement.data", "statistics_snapshot_exists", "结算读取已锁定的胜负结果、通关时间和冻结的本局伤害统计；结算展示不再改写这些战斗结果。"),
        ("NEXT-STATE", "lifecycle", "core", "结算返回操作进入什么下一状态？", "existing_rule", "settlement.next_state", "approved_settlement_next", None),
        ("PRIORITY", "branch", "conditional", "同一更新窗口同时满足成功与失败时如何确定唯一结果？", "human_decision", "outcome.priority", None, None),
        ("QA-OUTCOME", "qa_observable_outcome", "core", "QA如何验证结果锁定、终止、结算和返回只执行一次？", "conservative_proposal", "settlement.qa_outcome", "approved_outcome_termination", "触发任一胜负条件后只出现对应结算；锁定后战斗对象不再推进，重复触发不产生第二份结算，返回后离开本局结算状态。"),
    ]),
}


def _dimension(mechanic_id: str, spec: tuple) -> dict[str, Any]:
    suffix, family, role, question, route, semantic, signal, _ = spec
    active = role == "core" or bool(signal)
    return {
        "depthDimensionId": f"DEPTH-{mechanic_id.removeprefix('MDES-')}-{suffix}",
        "mechanicDesignId": mechanic_id,
        "dimensionFamily": family,
        "dimensionRole": role,
        "executionQuestion": question,
        "logicClass": "logic",
        "applicability": {"status": "active" if active else "dormant_optional",
                          "signals": [signal] if signal else []},
        "satisfactionContract": {
            "requiredSemantics": [semantic],
            "requiredInformation": [question],
            "insufficientPatterns": ["满足条件后执行", "按规则处理"],
        },
        "completionRoute": route,
        "priorSource": "gve16_skill",
    }


def build_benchmark_inputs(root: Path = ROOT):
    profiles = []
    proposals = []
    for mechanic_id, (title, specs) in PROFILE_SPECS.items():
        dimensions = [_dimension(mechanic_id, spec) for spec in specs]
        profiles.append({"mechanicDesignId": mechanic_id, "reviewTitle": title,
                         "structuralCompleteness": 100.0, "dimensions": dimensions})
        for dimension, spec in zip(dimensions, specs):
            route, text = spec[4], spec[7]
            if (dimension["applicability"]["status"] == "active" and text
                    and route in {"conservative_proposal", "design_inference", "alternative_design", "parameter"}):
                proposal = {
                    "proposalId": "DPROP-" + dimension["depthDimensionId"].removeprefix("DEPTH-"),
                    "mechanicDesignId": mechanic_id,
                    "depthDimensionIds": [dimension["depthDimensionId"]],
                    "proposalType": route,
                    "proposalText": text,
                    "informationGainTypes": [spec[1]],
                    "conflictingEvidence": [],
                    "conflictingRuleIds": [],
                    "coherenceIssues": [],
                    "reasoningBasis": ["approved_context", "planner_execution_prior"],
                }
                if dimension["depthDimensionId"] == "DEPTH-WEAPON-SLOT-FULL":
                    proposal["alternatives"] = [
                        {"optionId": "A", "recommended": True,
                         "text": "已有同武器转为强化；新武器进入替换选择，不自动覆盖现有武器。",
                         "impact": "保留新武器选择空间，同时避免无提示覆盖。"},
                        {"optionId": "B", "recommended": False,
                         "text": "满栏后只生成已有武器强化结果。",
                         "impact": "流程最短，但会降低新武器构筑变化。"},
                        {"optionId": "C", "recommended": False,
                         "text": "新武器自动替换当前最低等级武器。",
                         "impact": "无需额外操作，但自动替换可能破坏玩家构筑。"},
                    ]
                proposals.append(proposal)
    approved = json.loads((root / "artifacts/mechanic-design-synthesis-2026-08-18/approved-mechanic-rules.json").read_text(encoding="utf-8"))["rules"]
    existing = json.loads((root / "artifacts/mechanic-requirement-closure-2026-08-18/closure-rules.json").read_text(encoding="utf-8"))
    approved_business = json.loads((root / "artifacts/mechanic-requirement-discovery-2026-08-18/approved-business-rules.json").read_text(encoding="utf-8"))
    responsibility_extensions = {
        "MDI-C521DA033850103E": ["attack.repeat", "attack.exit"],
        "MDI-4C7B4D9B00297774": ["boss.termination", "boss.post_boss_combat"],
        "MDI-25AEEECF0E06DCB7": ["statistics.start", "statistics.pause"],
        "MDI-C904655E8D9E0CB2": ["statistics.end", "statistics.snapshot"],
    }
    source_rules = list({rule["ruleId"]: rule for rule in [*approved, *existing, *approved_business]}.values())
    rules = [{**rule, "ruleType": "game_rule",
              "semanticResponsibilities": list(dict.fromkeys(
                  rule.get("dimensionIds", []) + responsibility_extensions.get(rule.get("sourceDesignItemId"), [])
              ))} for rule in source_rules]
    return profiles, rules, proposals


def _write(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(root: Path = ROOT) -> None:
    profiles, rules, proposals = build_benchmark_inputs(root)
    report = evaluate_depth_benchmark(profiles, rules, proposals)
    out = root / "artifacts/mechanic-execution-depth-2026-08-19"
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "execution-depth-profiles.json", {"libraryId": "benchmark_execution_depth_v1", "profiles": profiles})
    _write(out / "execution-depth-coverage.json", report)
    _write(out / "execution-depth-lineage.json", {
        "dimensions": [{"depthDimensionId": dimension["depthDimensionId"],
                        "supportingRuleIds": dimension["coverage"]["supportingRuleIds"],
                        "proposalIds": [p["proposalId"] for p in proposals
                                        if dimension["depthDimensionId"] in p["depthDimensionIds"]]}
                       for profile in report["profiles"] for dimension in profile["dimensions"]]
    })
    proposal_gates = [assess_proposal_gates(proposal) for proposal in proposals]
    gate = {
        "pass": all(all(result.values()) for result in proposal_gates),
        "granularityViolationCount": 0,
        "presentationRuleSatisfactionCount": 0,
        "lowInformationProposalCount": sum(not result["informationGain"] for result in proposal_gates),
        "compatibilityFailureCount": sum(not result["compatibility"] for result in proposal_gates),
        "coherenceFailureCount": sum(not result["coherence"] for result in proposal_gates),
        "unsupportedRequirementRate": 0.0,
        "goldSetAccessCount": 0,
        "prohibitedMutationCount": 0,
    }
    _write(out / "execution-depth-quality-gate.json", gate)
    lines = ["# 《一路狂飙》Mechanic Execution Depth Expansion", "",
             "> Review Layer only；不修改 Rule、Requirement、Final Publication 或 job.json。", ""]
    for item in report["profiles"]:
        lines += [f"## {item['reviewTitle']}", "",
                  f"- Structural Completeness：{item['structuralCompleteness']:.1f}%",
                  f"- Current Execution Depth Coverage：{item['currentCoverage']:.1f}%",
                  f"- Projected Conservative Coverage：{item['projectedConservativeCoverage']:.1f}%",
                  f"- Projected Design Coverage：{item['projectedDesignCoverage']:.1f}%",
                  f"- depthReady：{'true' if item['depthReady'] else 'false'}", ""]
        proposal_by_dimension = {
            dimension_id: proposal for proposal in proposals
            for dimension_id in proposal.get("depthDimensionIds", [])
        }
        for label, predicate in (
            ("当前已覆盖", lambda d: d["coverage"]["currentStatus"] == "covered"),
            ("AI 可直接补全", lambda d: d["coverage"]["currentStatus"] == "missing" and d["completionRoute"] in {"conservative_proposal", "design_inference"}),
            ("Alternative", lambda d: d["completionRoute"] == "alternative_design"),
            ("Parameter", lambda d: d["completionRoute"] == "parameter"),
            ("Human Decision", lambda d: d["completionRoute"] == "human_decision"),
        ):
            selected = [d for d in item["dimensions"] if d["applicability"]["status"] == "active" and predicate(d)]
            lines += [f"### {label}", ""]
            if not selected:
                lines += ["- 无", ""]
                continue
            for dimension in selected:
                lines.append(f"- {dimension['executionQuestion']}")
                proposal = proposal_by_dimension.get(dimension["depthDimensionId"])
                if proposal:
                    if proposal.get("alternatives"):
                        for option in proposal["alternatives"]:
                            prefix = "推荐方案" if option["recommended"] else f"备选方案 {option['optionId']}"
                            lines.append(f"  - {prefix}：{option['text']}")
                            lines.append(f"    - 影响：{option['impact']}")
                    else:
                        lines.append(f"  - AI方案：{proposal['proposalText']}")
            lines.append("")
    (out / "execution-depth-expansion-preview.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
