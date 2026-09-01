from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping


RULE_CLASSES = {"rule_choice", "boolean_rule", "multi_select_rule", "complex_rule", "evidence_conflict"}
PARAMETER_CLASSES = {"numeric_parameter", "enum_parameter"}
INTERNAL_TERMS = ("candidate_filter", "damage_resolution", "parameter_contract", "breakpoint", "semantic", "node", "edge")


def _id(source: str, key: str) -> str:
    digest = hashlib.sha1(f"{source}:{key}".encode("utf-8")).hexdigest()[:12].upper()
    return f"DEC-{digest}"


def _option(option_id: str, label: str, basis: str) -> dict[str, Any]:
    return {"optionId": option_id, "label": label, "basis": basis, "recommendationOnly": True}


def _decision(source: str, owner: str, topic: str, key: str, decision_class: str, stage: str,
              route: str, question: str, control: str, *, options: list[dict[str, Any]] | None = None,
              allow_custom: bool = False, dependency: dict[str, Any] | None = None,
              disposition: str = "review", why: str = "", input_contract: dict[str, Any] | None = None,
              approval_status: str = "unreviewed") -> dict[str, Any]:
    return {"decisionId": _id(source, key), "decisionKey": key, "sourceMissingId": source,
            "ownerChapter": owner, "ruleTopic": topic, "decisionClass": decision_class,
            "reviewStage": stage, "route": route, "question": question, "options": options or [],
            "recommendedOption": None, "recommendationOnly": True,
            "recommendationBasis": "当前证据不足，不自动推荐；候选项仅用于呈现可选设计分支。",
            "allowCustom": allow_custom, "inputContract": input_contract or {"control": control},
            "uiControl": control, "dependency": dependency, "approvalStatus": approval_status,
            "disposition": disposition, "why": why,
            "isCommonSenseQuestion": False, "isImplementationQuestion": False,
            "observableFactReasked": False}


def _source_id(detail: dict[str, Any], fallback: str) -> str:
    ids = detail.get("sourceMissingIds", [])
    return ids[0] if ids else fallback


def _parameter_decision(source: str, owner: str, topic: str, semantic: str, label: str) -> dict[str, Any] | list[dict[str, Any]]:
    numeric_contract = {"control": "number_with_unit", "valueType": "number", "unitRequired": True,
                        "unitOptions": [], "allowCustomUnit": True}
    specs = {
        "movement_speed": ("移动速度是多少？", "移动速度", None),
        "weapon_slot_capacity": ("武器栏最多可以容纳多少个武器或技能？", "武器栏容量",
                                 {"control": "number", "valueType": "integer", "minimum": 1, "unit": "个"}),
        "attack_range": ("武器的攻击范围是多少？", "攻击范围", numeric_contract),
        "attack_interval": ("武器每次攻击之间间隔多长时间？", "攻击间隔", numeric_contract),
        "time_limit": ("关卡时限是多少？", "关卡时限", numeric_contract),
    }
    if semantic in specs:
        question, display, contract = specs[semantic]
        return _decision(source, owner, topic, semantic, "numeric_parameter", "P6", "P6", question,
                         "number", why=f"{display}已确认影响玩法，但具体值未知。",
                         input_contract=contract or numeric_contract)
    return []


def map_missing_items_to_review_controls(expansion_plans: list[dict[str, Any]],
                                          parameter_placements: list[dict[str, Any]],
                                          scope_corrections: list[dict[str, Any]],
                                          approved_rules: list[dict[str, Any]],
                                          evidence_index: Mapping[str, Any],
                                          corpora: Mapping[str, Any]) -> list[dict[str, Any]]:
    decisions: list[dict[str, Any]] = []
    for plan in expansion_plans:
        owner, topic = plan["ownerChapter"], plan["ruleTopic"]
        for detail in plan.get("missingExecutionDetails", []):
            semantic = detail.get("semantic")
            source = _source_id(detail, f"MISSING:{owner}:{semantic}")
            if semantic == "candidate_eligibility":
                decisions.append(_decision(source, owner, topic, semantic, "multi_select_rule", "P4", "P4",
                    "三选一中，哪些词条可以出现？", "checkbox_group",
                    options=[
                        _option("owned_weapon_affix", "当前已拥有武器的普通词条",
                                "当前项目已确认词条可以改变已选武器的攻击方式或参数。"),
                        _option("owned_weapon_ultimate", "当前已拥有武器的终极词条",
                                "当前项目已确认存在终极词条及其攻击方向变化效果。")],
                    allow_custom=True, why="候选资格会直接改变随机结果与成长策略。"))
            elif semantic == "resume_combat":
                decisions.append(_decision(source, owner, topic, semantic, "rule_choice", "none", "Suppress",
                    "选择完成后如何恢复战斗？", "none", disposition="natural_default",
                    why="当前没有证据表明存在倒计时或手动确认等玩家可感知分支；关闭选择界面后继续战斗属于自然闭环。",
                    approval_status="not_applicable"))
            elif semantic == "contact_damage_mode":
                choice = _decision(source, owner, topic, semantic, "rule_choice", "P4", "P4",
                    "怪物接触载具后，伤害如何结算？", "radio",
                    options=[_option("single", "接触时结算1次", "会形成单次受伤结果。"),
                             _option("continuous", "持续接触期间周期结算", "会形成持续伤害状态与不同数值结果。")],
                    allow_custom=True, why="两种答案会改变伤害结果、脱离接触后的状态和玩家规避策略。")
                decisions.append(choice)
                decisions.append(_decision(f"{source}:interval", owner, topic, "contact_damage_interval",
                    "numeric_parameter", "P6", "P6", "持续接触伤害的结算间隔是多少？", "number",
                    dependency={"decisionId": choice["decisionId"], "whenOption": "continuous"},
                    why="仅在持续伤害被用户确认后激活。",
                    input_contract={"control": "number_with_unit", "valueType": "number",
                                    "unitRequired": True, "allowCustomUnit": True}))
            elif semantic == "growth_accumulation":
                # Scope only proves that in-level progression exists. It does not prove a
                # particular source or threshold model, so corpus examples must not become
                # selectable project options. Split the decision into two compact rule fields.
                source_choice = _decision(source, owner, topic, "growth_source", "complex_rule", "P4", "P4",
                    "关卡内通过什么方式积累成长进度？", "structured_rule",
                    allow_custom=True, why="成长来源会改变玩家战斗目标和成长节奏；当前 Scope 未支持具体候选形式。",
                    input_contract={"control": "structured_rule", "fields": [
                        {"fieldId": "growth_source", "label": "成长来源", "valueType": "text", "required": True}
                    ]})
                basis_choice = _decision(f"{source}:basis", owner, topic, "upgrade_basis", "complex_rule", "P4", "P4",
                    "成长进度满足什么规则时提升战斗等级？", "structured_rule",
                    allow_custom=True, why="升级依据会改变三选一触发频率和成长节奏；当前 Scope 未支持具体候选形式。",
                    input_contract={"control": "structured_rule", "fields": [
                        {"fieldId": "upgrade_basis", "label": "升级依据", "valueType": "text", "required": True}
                    ]})
                decisions += [source_choice, basis_choice]
            elif semantic == "failure_result":
                decision = _decision(source, owner, topic, semantic, "evidence_conflict", "Evidence",
                    "Evidence Recheck", "失败后显示什么状态，并如何结束当前关卡？", "evidence_recheck",
                    disposition="evidence_recheck", why="素材已确认失败事件，应先复核失败画面或后续流程证据，避免让策划重复选择可观察事实。",
                    approval_status="pending_evidence")
                decisions.append(decision)
            elif semantic == "displayed_data":
                decision = _decision(source, owner, topic, semantic, "evidence_conflict", "Evidence",
                    "Evidence Recheck", "结算页面实际展示了哪些战斗结果？", "evidence_recheck",
                    disposition="evidence_recheck", why="当前已有结算页面表现证据，应先从截图补充 Fact / Rule。",
                    approval_status="pending_evidence")
                decisions.append(decision)

    # Consume ParameterPlacementPlan; fall back to expansion parameters for isolated tests or older artifacts.
    unresolved = [item for item in parameter_placements if item.get("parameterClass") == "unresolved_gameplay_parameter"]
    seen = {(item.get("ownerChapter"), item.get("semantic")) for item in unresolved}
    for plan in expansion_plans:
        for item in plan.get("gameplayParameters", []):
            key = (plan["ownerChapter"], item.get("semantic"))
            if key not in seen:
                unresolved.append({"parameterId": f"PARAM:{plan['ownerChapter']}:{item.get('semantic')}",
                                   "ownerChapter": plan["ownerChapter"], "ownerLayout": None,
                                   "semantic": item.get("semantic"), "displayLabel": item.get("label"),
                                   "parameterClass": "unresolved_gameplay_parameter", "ruleTopic": plan["ruleTopic"]})
                seen.add(key)

    for item in unresolved:
        semantic = item.get("semantic")
        source = item.get("parameterId", f"PARAM:{semantic}")
        owner = item.get("ownerChapter")
        topic = item.get("ruleTopic") or next((plan["ruleTopic"] for plan in expansion_plans
                                               if plan.get("ownerChapter") == owner and
                                               any(p.get("semantic") == semantic for p in plan.get("gameplayParameters", []))), "参数")
        basic = _parameter_decision(source, owner, topic, semantic, item.get("displayLabel", semantic))
        if basic:
            decisions.append(basic)
        elif semantic == "damage":
            model = _decision(source, owner, topic, "damage_model", "complex_rule", "P4", "P4",
                "武器伤害采用哪种计算方式？", "radio",
                options=[_option("fixed", "使用固定伤害值", "固定值与公式模型会产生不同数值规则。"),
                         _option("multiplier", "基础属性乘以倍率", "倍率模型会随基础属性变化。"),
                         _option("custom_formula", "使用其他公式", "允许策划提供当前项目的真实公式。")],
                allow_custom=True, why="伤害模型属于玩法规则形式，不能与具体数值放在同一个参数控件。")
            decisions.append(model)
            decisions.append(_decision(f"{source}:fixed", owner, topic, "damage_fixed_value", "numeric_parameter", "P6", "P6",
                "固定伤害值是多少？", "number", dependency={"decisionId": model["decisionId"], "whenOption": "fixed"},
                why="仅在用户确认固定伤害模型后填写。", input_contract={"control": "number", "valueType": "number"}))
            decisions.append(_decision(f"{source}:multiplier", owner, topic, "damage_multiplier", "numeric_parameter", "P6", "P6",
                "伤害倍率是多少？", "number", dependency={"decisionId": model["decisionId"], "whenOption": "multiplier"},
                why="仅在用户确认倍率模型后填写。", input_contract={"control": "number", "valueType": "number"}))
        elif semantic == "refresh_cost":
            refresh = _decision(source, owner, topic, "refresh_rule", "rule_choice", "P4", "P4",
                "刷新候选时采用什么消耗规则？", "radio",
                options=[_option("resource", "消耗资源", "当前 Rule 已确认刷新存在消耗或替代条件。"),
                         _option("alternative", "满足替代条件后刷新", "当前 Rule 已确认存在替代条件的可能。"),
                         _option("combined", "资源与替代条件组合使用", "两类条件可以形成玩家可感知的组合规则。")],
                allow_custom=True, why="消耗形式会改变资源流转和玩家刷新策略。")
            decisions.append(refresh)
            dependency = {"decisionId": refresh["decisionId"], "whenOptionIn": ["resource", "combined"]}
            decisions.append(_decision(f"{source}:resource", owner, topic, "refresh_resource_type", "enum_parameter", "P6", "P6",
                "刷新消耗哪一种资源？", "text_or_select", dependency=dependency,
                why="仅在用户确认消耗资源后激活；当前没有证据支持预置资源名称。",
                input_contract={"control": "text_or_select", "options": [], "allowCustom": True}))
            decisions.append(_decision(f"{source}:amount", owner, topic, "refresh_cost_amount", "numeric_parameter", "P6", "P6",
                "每次刷新消耗多少？", "number", dependency=dependency,
                why="仅在用户确认消耗资源后激活。", input_contract={"control": "number", "valueType": "number"}))

    for correction in scope_corrections:
        if correction.get("scopeItem") == "recorded_data" and correction.get("correctedStatus") == "unsupported":
            decisions.append(_decision(f"SCOPE:{correction['chapterId']}:recorded_data", correction["chapterId"], "数据记录",
                "recorded_data", "complex_rule", "none", "Suppress", "结算后是否保存跨局记录？", "none",
                disposition="scope_unsupported", why="当前只有结算展示证据，不能建立跨局保存规则。",
                approval_status="not_applicable"))
    return decisions


def evaluate_review_control_quality(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    active = [item for item in decisions if item.get("route") in {"P4", "P6"}]
    common = [item["decisionId"] for item in active if item.get("isCommonSenseQuestion")]
    implementation = [item["decisionId"] for item in active if item.get("isImplementationQuestion")]
    observable = [item["decisionId"] for item in active if item.get("observableFactReasked")]
    numeric_as_rule = [item["decisionId"] for item in decisions
                       if item.get("reviewStage") == "P4" and item.get("decisionClass") in PARAMETER_CLASSES]
    rule_as_numeric = [item["decisionId"] for item in decisions
                       if item.get("reviewStage") == "P6" and item.get("decisionClass") in RULE_CLASSES]
    unsupported_options = [f"{item['decisionId']}:{option.get('optionId')}" for item in decisions
                           for option in item.get("options", []) if not option.get("basis")]
    internal = []
    id_pattern = re.compile(r"\b(?:PMECH|RGAP|SCOPE|RULE|V2CH|ENT)-[A-Z0-9:-]+\b")
    for item in decisions:
        visible = " ".join([item.get("question", ""), *(option.get("label", "") for option in item.get("options", []))])
        if id_pattern.search(visible) or any(term in visible for term in INTERNAL_TERMS):
            internal.append(item["decisionId"])
    auto_approved = [item["decisionId"] for item in decisions if item.get("recommendedOption") and
                     (not item.get("recommendationOnly") or item.get("approvalStatus") == "approved")]
    option_worthiness = [item["decisionId"] for item in active if item.get("decisionClass") in
                         {"rule_choice", "boolean_rule", "multi_select_rule"} and len(item.get("options", [])) < 2]
    findings = common + implementation + observable + numeric_as_rule + rule_as_numeric + unsupported_options + internal + auto_approved + option_worthiness
    return {"qualityGate": "pass" if not findings else "fail", "decisionCount": len(decisions),
            "p4DecisionCount": sum(item.get("route") == "P4" for item in decisions),
            "p6DecisionCount": sum(item.get("route") == "P6" for item in decisions),
            "evidenceRecheckCount": sum(item.get("route") == "Evidence Recheck" for item in decisions),
            "suppressedCount": sum(item.get("route") == "Suppress" for item in decisions),
            "commonSenseQuestionCount": len(common), "implementationQuestionCount": len(implementation),
            "observableFactReaskedCount": len(observable), "numericAsRuleChoiceCount": len(numeric_as_rule),
            "ruleChoiceAsNumericCount": len(rule_as_numeric), "unsupportedOptionCount": len(unsupported_options),
            "internalSemanticLeakCount": len(internal),
            "autoApprovedAiRecommendationCount": len(auto_approved),
            "optionWorthinessFailureCount": len(option_worthiness), "findings": findings}
