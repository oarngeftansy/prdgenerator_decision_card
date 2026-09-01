from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
import hashlib
import re
from typing import Any


BLOCKING = {
    "implementation": "P0 implementation_blocking", "qa": "P1 qa_blocking",
    "parameter": "P2 parameter_required", "documentation": "P3 documentation_detail",
}
GENERIC = re.compile(r"^(?:.+)?(?:规则|逻辑|条件|处理)是什么[？?]$")
LEADING = re.compile(r"(?:建议|通常|默认应|应当为|一般采用)")
REUSABLE_SLOTS = frozenset({"movement_speed_source", "attack_range", "damage_reference", "candidate_pool_source",
                            "pool_entry_condition", "pool_exit_condition", "duplicate_rule", "replacement_rule",
                            "weight_rule", "max_level_rule", "prerequisite_rule", "refresh_count", "refresh_cost"})


def _gap_id(mechanic_id: str, semantic_key: str) -> str:
    return "RGAP-" + hashlib.sha1(f"{mechanic_id}:{semantic_key}".encode()).hexdigest()[:12].upper()


def _confirmed(graph: dict[str, Any], semantic: str) -> dict[str, Any] | None:
    return next((node for node in graph.get("nodes", []) if node["semantic"] == semantic and node["status"] in {"confirmed", "derived_structure"}), None)


def _node(graph: dict[str, Any], semantic: str) -> dict[str, Any] | None:
    return next((node for node in graph.get("nodes", []) if node["semantic"] == semantic), None)


def _target_name(graph: dict[str, Any]) -> str:
    text = " ".join(item.get("sourceBehavior", "") for item in graph.get("ruleDecompositions", []))
    return "载具" if "载具" in text else "目标"


def _spec(key: str, source: list[dict[str, Any]], missing: str, relation: str | None, gap_type: str,
          question: str, implementation: str, qa: str, priority: str, reason: str,
          existing_slots: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"semanticKeySuffix": key, "sourceNodes": source, "missingNodeSemantic": missing,
            "missingRelation": relation, "gapType": gap_type, "question": question,
            "implementationImpact": implementation, "qaImpact": qa, "blockingLevel": BLOCKING[priority],
            "derivationReason": reason, "existingSlots": existing_slots}


def _breakpoint_specs(graph: dict[str, Any]) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    mechanic_type = graph.get("mechanicType")
    if mechanic_type == "movement":
        moving, path, process, control = (_confirmed(graph, value) for value in ("moving_object", "movement_path", "position_update", "movement_input"))
        if moving and path and process:
            specs += [
                _spec("path_contract", [path, process], "movement_path_contract", "requires", "processing",
                      "预设路线由哪项关卡数据提供，载具如何确定当前路径段和下一个移动目标？",
                      "程序需要路径数据来源、寻段方式和移动目标才能实现自动行进。", "QA 需要验证路径切段和路线数据异常时的行为。", "implementation",
                      "已确认自动行进依赖预设路线，但路径的数据契约和消费方式未定义。", ("movement_path",)),
                _spec("movement_exit", [moving, process], "movement_stop", "persists_until", "exit_condition",
                      "哪些事件会终止载具自动行进，终止后当前移动状态如何处理？",
                      "程序需要终止事件和状态清理规则才能停止移动循环。", "QA 需要覆盖各终止事件及终止后的载具状态。", "implementation",
                      "已确认自动行进处理，但其持续终点和退出后的状态未定义。", ("movement_stop_condition",)),
                _spec("movement_speed", [process], "movement_speed", "depends_on", "parameter",
                      "载具自动行进的速度读取哪项配置，速度值采用什么单位？",
                      "程序需要速度参数来源和单位才能计算位移。", "QA 需要按配置值验证单位时间位移。", "parameter",
                      "已确认位置持续更新，因此位移计算必须有速度参数。", ("movement_speed_source",)),
            ]
        if control and process and path:
            specs += [
                _spec("input_composition", [control, path, process], "movement_input_composition", "requires", "ordering",
                      "横向微调与自动沿路线行进同时发生时，两种位移按什么顺序和规则合成？",
                      "程序需要明确自动位移与输入位移的合成顺序，避免位置更新结果不确定。", "QA 需要验证持续输入、反向输入和路径转向时的最终位置。", "implementation",
                      "两个已确认输入共同作用于同一位置更新节点，但合成关系未定义。"),
                _spec("input_release", [control, process], "movement_input_release", "persists_until", "boundary",
                      "玩家停止横向输入后，载具的横向位置按什么规则继续处理？",
                      "程序需要输入结束后的状态处理，避免微调状态悬空。", "QA 需要验证松开输入后的连续帧位置变化。", "qa",
                      "已确认横向输入会改变位置，但输入结束后的边界行为未定义。"),
            ]
    elif mechanic_type == "attack":
        trigger, result = _confirmed(graph, "attack_trigger"), _confirmed(graph, "damage_output")
        execution, selection, target_set = (_confirmed(graph, value) for value in ("attack_execution", "target_selection", "target_set_build"))
        if trigger and result:
            target = _target_name(graph)
            specs += [
                _spec("contact_damage_mode", [trigger, result], "contact_damage_processing", "triggers", "processing",
                      f"怪物与{target}接触后，伤害是仅结算一次，还是在持续接触期间重复结算？",
                      "程序需要选择一次性事件或持续结算循环。", "QA 需要分别验证首次接触、持续接触和重复进入接触状态。", "implementation",
                      "接触条件与伤害结果已确认，但两者之间的结算模式未定义。"),
                _spec("damage_interval", [trigger, result], "contact_damage_interval", "depends_on", "parameter",
                      "若接触伤害会重复结算，每次结算的时间间隔由哪项参数控制？",
                      "程序需要持续结算循环的计时参数契约。", "QA 需要测量连续伤害触发间隔及边界帧。", "parameter",
                      "持续接触是现有 Rule 的未决解释分支；若采用该分支，必须有结算间隔。", ("damage_interval",)),
                _spec("damage_aggregation", [trigger, result], "contact_damage_aggregation", "produces", "aggregation",
                      f"多只怪物同时与{target}接触时，各怪物造成的伤害是否分别独立结算？",
                      "程序需要确定多来源伤害的聚合与结算实例边界。", "QA 需要覆盖单只、多只同时接触及同帧伤害。", "qa",
                      "已确认攻击者接触会产生伤害，但多攻击者并发时的聚合关系未定义。"),
                _spec("contact_exit", [trigger, result], "contact_exit_condition", "persists_until", "exit_condition",
                      f"怪物与{target}脱离接触后，尚未完成的接触伤害处理在什么时点停止？",
                      "程序需要退出条件来终止接触伤害处理。", "QA 需要验证脱离接触当帧及下一结算时点不再产生额外伤害。", "implementation",
                      "接触条件已确认，但条件失效后的处理终点未定义。", ("attack_exit_condition",)),
            ]
        if selection and target_set and execution:
            specs += [
                _spec("target_ordering", [target_set, selection], "target_priority", "produces", "ordering",
                      "射程内同时存在多个合法目标时，武器按什么优先级选择目标；优先级相同时如何处理？",
                      "程序需要稳定的排序键与同序处理才能确定攻击目标。", "QA 需要构造多目标及优先级相同场景验证选中结果。", "implementation",
                      "目标集合和目标选择均已成立，但集合到单一目标的排序关系未定义."),
                _spec("empty_target", [target_set, selection], "empty_target_behavior", "branches_to", "exception",
                      "射程内没有合法目标时，武器保持等待、重新检测还是执行其他已定义处理？",
                      "程序需要无目标分支，避免目标选择返回空值后继续攻击。", "QA 需要验证空目标集合及目标刚失效场景。", "qa",
                      "目标选择依赖目标集合，因此空集合是已证明适用的执行边界。"),
                _spec("attack_repeat", [selection, execution], "next_attack_trigger", "repeats_to", "trigger",
                      "一次攻击执行完成后，下一次攻击在什么条件和时点触发？",
                      "程序需要攻击循环的再次触发条件。", "QA 需要验证连续攻击间隔、目标仍有效和目标失效三种情况。", "implementation",
                      "目标选择会触发一次攻击执行，但后续循环关系未定义。"),
                _spec("attack_method_branch", [execution], "attack_method_selection", "branches_to", "processing",
                      "每种武器依据什么已确认数据选择发射投射物或生成持续伤害区域的攻击处理？",
                      "程序需要把武器类型映射到唯一攻击处理分支。", "QA 需要逐武器验证处理分支及分支切换。", "implementation",
                      "已确认存在两类攻击处理，但具体武器到处理分支的选择依据未定义。", ("attack_method",)),
            ]
            for semantic, question, slots in (
                ("attack_entry", "武器在什么距离和状态条件下允许开始本次攻击？", ("attack_range",)),
                ("damage_output", "攻击处理完成后，伤害读取哪条计算规则并写入哪个受击对象？", ("damage_reference",)),
                ("exit_condition", "当前目标失效或不再满足攻击条件时，本次攻击在什么时点结束，后续是否重新选取目标？", ("attack_exit_condition",)),
            ):
                unresolved = _node(graph, semantic)
                if unresolved and unresolved["status"] == "unresolved":
                    specs.append(_spec(semantic, [selection, execution], semantic, "requires", "exit_condition" if semantic == "exit_condition" else "condition" if semantic == "attack_entry" else "result",
                        question, "程序需要补齐该机制链断点。", "QA 需要覆盖该断点的正常与边界输入。", "implementation",
                        "已确认目标选择和攻击执行，但相邻必要节点仍未定义。", slots))
    elif mechanic_type == "randomization":
        generation, selection, refresh, state, draw = (_confirmed(graph, value) for value in ("candidate_generation", "selection_processing", "refresh_processing", "selection_state", "candidate_draw"))
        if draw and generation:
            random_contracts = (
                ("candidate_pool_source", "candidate_set", "dependency", "候选生成读取的候选池来自哪份已确认配置或数据集合？", "candidate_pool_source", "implementation"),
                ("pool_entry_condition", "candidate_filter", "condition", "候选项满足哪些可执行条件后进入本次候选池？", "pool_entry_condition", "implementation"),
                ("pool_exit_condition", "candidate_filter", "condition", "候选项满足哪些条件后从后续抽取中移出？", "pool_exit_condition", "implementation"),
                ("duplicate_rule", "candidate_constraints", "boundary", "同一次生成三项候选时，是否允许出现语义相同的重复项？", "duplicate_rule", "qa"),
                ("replacement_rule", "candidate_constraints", "processing", "候选项被本次抽取后，在同一次生成流程中是否继续参与后续位置的抽取？", "replacement_rule", "qa"),
                ("weight_rule", "candidate_weight_contract", "parameter", "各候选项的抽取权重读取哪项数据，权重在什么时点参与计算？", "weight_rule", "parameter"),
                ("max_level_rule", "candidate_filter", "boundary", "候选项达到最大等级后，是否继续参与候选池及候选结果生成？", "max_level_rule", "implementation"),
                ("prerequisite_rule", "candidate_filter", "dependency", "存在前置关系的候选项，在什么时点检查前置条件并决定是否允许入池？", "prerequisite_rule", "implementation"),
                ("empty_result_rule", "empty_candidate", "exception", "过滤后没有任何合法候选时，本次选择流程如何结束或继续？", "empty_result_rule", "implementation"),
            )
            for key, missing, gap_type, question, slot, priority in random_contracts:
                specs.append(_spec(key, [draw, generation], missing, "requires", gap_type, question,
                    "程序需要该候选抽取契约才能构造确定性的合法候选结果。", "QA 需要围绕该契约构造候选池边界与抽取结果。", priority,
                    "候选抽取和三项候选生成已证明适用，因此该抽取契约对应真实机制断点。", (slot,)))
        if generation and selection:
            specs += [
                _spec("candidate_shortage", [generation, selection], "candidate_shortage_behavior", "branches_to", "boundary",
                      "合法候选不足三项时，本次候选结果如何组成，玩家是否仍可继续选择？",
                      "程序需要定义候选数量不足时的输出结构和流程分支。", "QA 需要覆盖合法候选为零、一项、两项和三项的场景。", "implementation",
                      "已确认系统生成三项候选，但候选池过滤可能使合法项不足，数量边界未定义。"),
                _spec("selection_atomicity", [generation, selection], "selection_commit", "transitions_to", "ordering",
                      "玩家确认某项候选时，系统在哪个时点锁定本次选择并禁止其他候选重复生效？",
                      "程序需要原子提交边界，防止同一候选流程多次结算。", "QA 需要验证连续点击和同帧点击多个候选时仅生效一次。", "qa",
                      "候选生成与选择处理已确认，但选择提交的原子边界未定义。"),
            ]
        if refresh and generation:
            specs += [
                _spec("refresh_pipeline", [refresh, generation], "refresh_candidate_pipeline", "repeats_to", "processing",
                      "刷新后重新生成候选时，是否重新执行与首次生成相同的入池、过滤、去重和抽取步骤？",
                      "程序需要明确刷新复用的候选生成管线。", "QA 需要对比首次生成与刷新后的候选合法性。", "implementation",
                      "刷新会替换候选并回到候选生成，但回环中经过哪些处理节点未定义。"),
                _spec("refresh_selection_race", [refresh, selection, generation], "refresh_selection_exclusion", "branches_to", "ordering",
                      "刷新与候选确认操作同时到达时，系统按什么顺序处理，并保证哪一个操作生效？",
                      "程序需要互斥或排序规则，避免刷新结果与选择结果同时提交。", "QA 需要模拟快速连续点击刷新与候选卡。", "qa",
                      "候选结果同时允许选择和刷新两个分支，但分支互斥关系未定义。"),
            ]
            specs += [
                _spec("refresh_count", [refresh, generation], "refresh_count", "repeats_to", "parameter",
                      "单次选择流程允许刷新多少次？", "程序需要刷新次数上限控制回环。", "QA 需要验证零次、上限内和超过上限的刷新操作。", "qa",
                      "刷新回到候选生成的回环已经确认，因此回环次数边界适用。", ("refresh_count",)),
                _spec("refresh_cost", [refresh, generation], "refresh_cost_contract", "depends_on", "parameter",
                      "刷新采用资源消耗还是广告条件；资源类型、数量、校验时点和扣除时点分别是什么？",
                      "程序需要刷新前置条件与消耗事务契约。", "QA 需要覆盖资源足够、不足、广告完成及扣除失败。", "parameter",
                      "刷新处理已确认且现有 Rule 只证明存在消耗或替代条件，具体契约仍未定义。", ("refresh_cost",)),
            ]
        if state and selection:
            specs.append(_spec("selection_resume", [state, selection], "selection_state_exit", "persists_until", "state_transition",
                "候选确认完成后，暂停状态在什么时点解除，候选界面与战斗状态按什么顺序恢复？",
                "程序需要暂停状态退出顺序。", "QA 需要验证效果生效、界面关闭和战斗恢复的先后关系。", "implementation",
                "选择期间的暂停状态已确认，但状态退出和恢复顺序未定义。", ("confirm_effect_timing",)))
    return specs


def _existing_for(spec: dict[str, Any], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots = set(spec["existingSlots"])
    if spec["semanticKeySuffix"] == "damage_interval":
        slots.add("damage_interval")
    return [gap for gap in existing if gap.get("schemaSlot") in slots and gap.get("status") not in {"closed", "resolved"}]


def validate_reasoning_gap(gap: dict[str, Any], graph: dict[str, Any]) -> dict[str, Any]:
    findings = []
    node_by_id = {node["nodeId"]: node for node in graph.get("nodes", [])}
    sources = [node_by_id.get(node_id) for node_id in gap.get("sourceNodeIds", [])]
    if not sources or any(node is None or node.get("status") not in {"confirmed", "derived_structure"} for node in sources):
        findings.append({"code": "breakpoint_not_grounded"})
    if any(node.get("semantic") == gap.get("missingNodeSemantic") and node.get("status") in {"confirmed", "derived_structure"} for node in graph.get("nodes", [])):
        findings.append({"code": "breakpoint_already_resolved"})
    if GENERIC.match(str(gap.get("question") or "").strip()):
        findings.append({"code": "generic_question"})
    if LEADING.search(str(gap.get("question") or "")):
        findings.append({"code": "leading_answer"})
    if not gap.get("implementationImpact"):
        findings.append({"code": "implementation_impact_missing"})
    if not gap.get("qaImpact"):
        findings.append({"code": "qa_impact_missing"})
    if not gap.get("derivationReason") or not gap.get("evidenceBasis"):
        findings.append({"code": "derivation_basis_missing"})
    return {"gapId": gap.get("gapId"), "valid": not findings, "findings": findings}


def expand_reasoning_gaps(mechanic_graphs: list[dict[str, Any]], existing_gaps: list[dict[str, Any]]) -> dict[str, Any]:
    existing = deepcopy(existing_gaps)
    all_gaps, audits = [], []
    for graph in deepcopy(mechanic_graphs):
        grounded = [node for node in graph.get("nodes", []) if node.get("status") in {"confirmed", "derived_structure"}]
        related_gap_ids = {gap_id for node in graph.get("nodes", []) for gap_id in node.get("supportingGapIds", [])}
        chapter_existing = [gap for gap in existing if gap.get("chapterId") == graph.get("chapterId") or gap.get("chapterId") in set(graph.get("chapterIds", [])) or gap.get("gapId") in related_gap_ids]
        specs = _breakpoint_specs(graph) if grounded else []
        generated = []
        consumed_ids, reused_ids, rewritten_ids = set(), set(), set()
        for spec in specs:
            semantic_key = f"{graph['mechanicId']}:{spec['semanticKeySuffix']}"
            matches = _existing_for(spec, chapter_existing)
            consumed_ids.update(gap["gapId"] for gap in matches)
            evidence = sorted({value for node in spec["sourceNodes"] for value in node.get("supportingRuleIds", []) + node.get("supportingEvidenceIds", [])})
            gap = {"gapId": _gap_id(graph["mechanicId"], semantic_key), "mechanicId": graph["mechanicId"],
                   "sourceNodeIds": [node["nodeId"] for node in spec["sourceNodes"]], "missingNodeSemantic": spec["missingNodeSemantic"],
                   "missingRelation": spec["missingRelation"], "gapType": spec["gapType"], "question": spec["question"],
                   "implementationImpact": spec["implementationImpact"], "qaImpact": spec["qaImpact"],
                   "blockingLevel": spec["blockingLevel"], "evidenceBasis": evidence,
                   "derivationReason": spec["derivationReason"], "ownerLayer": "Gap", "semanticKey": semantic_key,
                   "existingGapIds": sorted(gap["gapId"] for gap in matches),
                   "disposition": "reuse_existing" if matches and all(gap.get("schemaSlot") in REUSABLE_SLOTS for gap in matches) else "rewrite_existing" if matches else "new"}
            if gap["disposition"] == "reuse_existing":
                gap["question"] = matches[0]["question"]
                reused_ids.update(item["gapId"] for item in matches)
            elif gap["disposition"] == "rewrite_existing":
                rewritten_ids.update(item["gapId"] for item in matches)
            if validate_reasoning_gap(gap, graph)["valid"]:
                generated.append(gap)
        deduped = {gap["semanticKey"]: gap for gap in generated}
        all_gaps.extend(deduped.values())
        low_value = [gap for gap in chapter_existing if gap["gapId"] not in consumed_ids and GENERIC.match(str(gap.get("question") or "").strip())]
        defer = [gap for gap in chapter_existing if gap["gapId"] not in consumed_ids and gap not in low_value]
        # Known coarse attack slots become deletion candidates once contact semantics has grounded the actual target/result.
        if graph.get("mechanicType") == "attack" and _confirmed(graph, "attack_trigger") and _confirmed(graph, "damage_output"):
            coarse = [gap for gap in defer if gap.get("schemaSlot") in {"attack_target", "attack_method"}]
            low_value.extend(coarse)
            defer = [gap for gap in defer if gap not in coarse]
        audits.append({"mechanicId": graph["mechanicId"], "name": graph.get("name"),
                       "groundedBreakpointCount": len(specs), "reasoningGapIds": [gap["gapId"] for gap in deduped.values()],
                       "reusedExistingGapIds": sorted(reused_ids), "deleteLowValueGapIds": sorted({gap["gapId"] for gap in low_value}),
                       "rewrittenExistingGapIds": sorted(rewritten_ids),
                       "deferUntilGroundedGapIds": sorted(gap["gapId"] for gap in defer),
                       "suppressionReason": None if grounded else "no_grounded_breakpoint"})
    return {"reasoningGaps": all_gaps, "mechanisms": audits, "writesBackExistingGap": False,
            "createsApprovedRule": False, "templateSlotsConsumed": False}
