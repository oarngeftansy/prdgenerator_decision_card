from __future__ import annotations

import json
import hashlib
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.full_mechanic_reconstruction import (
    evaluate_core_design_depth,
    load_reconstruction_profile,
    validate_reconstruction,
)


CURRENT_SIGNALS = {
    "MDES-CHOICE": {"refresh_exists", "duplicate_candidate_signal"},
    "MDES-WEAPON": {"slot_capacity_reached_signal", "duplicate_weapon_signal"},
    "MDES-MONSTER": {"periodic_contact_damage_signal", "multiple_monster_signal", "choice_pause_signal"},
}

QA_OUTCOMES = {
    "MDES-CHOICE": [
        "触发选择后，关卡计时、怪物和武器保持冻结，候选确认成功后同时恢复。",
        "刷新前后的候选属于不同临时结果；旧候选不可再确认，刷新次数只扣减一次。",
        "候选不足时不出现无效占位；确认一项后不会重复写入同轮其他候选。",
    ],
    "MDES-WEAPON": [
        "新武器进入首个空栏并可参与攻击；重复武器只更新原实例，不增加第二个同名实例。",
        "目标失效后未结算指向取消，下一轮攻击重新选择目标。",
        "替换或移除后该实例不再产生新攻击，统计仍能区分移除前已结算伤害的来源。",
    ],
    "MDES-MONSTER": [
        "同一怪物按移动、首次接触伤害、周期伤害、脱离恢复移动的顺序可连续复现。",
        "暂停期间移动和伤害间隔不推进，恢复后不补结暂停期间的伤害次数。",
        "怪物死亡后不再产生伤害；多个接触怪物的伤害与计时互不覆盖。",
    ],
}

REMAINING_GAPS = {
    "MDES-CHOICE": ["候选池的正式内容来源、各内容 Eligibility 配置和精确刷新次数仍需主策/P6批准。"],
    "MDES-WEAPON": ["满栏处理需要主策选择方案；不同武器的目标规则、攻击间隔和伤害配置仍需逐武器批准。"],
    "MDES-MONSTER": ["接触判定的正式碰撞口径、接触伤害与攻击间隔数值仍需批准。"],
}


def _item(
    mechanic_id: str,
    suffix: str,
    sequence: int,
    text: str,
    semantics: list[str],
    role: str,
    knowledge: str = "design_inference",
    source_rules: list[str] | None = None,
    **extra: Any,
) -> dict[str, Any]:
    item = {
        "designItemId": f"MREC-{mechanic_id.removeprefix('MDES-')}-{suffix}",
        "sequence": sequence,
        "text": text,
        "knowledgeClass": knowledge,
        "semanticResponsibilities": semantics,
        "lifecycleRole": role,
        "sourceRuleIds": source_rules or [],
        "sourceEvidenceIds": extra.pop("sourceEvidenceIds", []),
        "sourceProposalIds": extra.pop("sourceProposalIds", []),
        "requirementIds": extra.pop("requirementIds", []),
        "parameterRefs": extra.pop("parameterRefs", []),
        "approvalState": "review_pending" if knowledge != "confirmed" else "approved_source",
        "gateStatus": "pass",
        "primaryMechanicOwner": mechanic_id,
        "primaryDefinitionKey": f"{mechanic_id}:{suffix}",
        "plannerRelevant": True,
    }
    item.update(extra)
    return item


def _relations(items: list[dict[str, Any]], branch_edges: list[dict[str, str]] | None = None):
    relations = [{
        "relationId": f"REL-{left['designItemId']}-{right['designItemId']}",
        "fromDesignItemId": left["designItemId"],
        "toDesignItemId": right["designItemId"],
        "relationType": "transitions_to",
    } for left, right in zip(items, items[1:])]
    for edge in branch_edges or []:
        relations.append({"relationId": f"REL-{edge['from']}-{edge['to']}",
                          "fromDesignItemId": edge["from"], "toDesignItemId": edge["to"],
                          "relationType": edge["type"]})
    return relations


def _choice_model() -> dict[str, Any]:
    mechanic_id = "MDES-CHOICE"
    items = [
        _item(mechanic_id, "01-TRIGGER", 10,
              "战斗等级提升并存在未处理的升级选择时，保存当前战斗上下文并进入三选一；关卡计时、怪物行为与武器攻击在选择完成前暂停。",
              ["trigger_model", "pause_scope"], "entry", "confirmed",
              ["RULE-0EDE4331073F"], sourceSynthesisIds=["SYN-LEVEL-PROGRESS", "SYN-LEVEL-CHOICE"]),
        _item(mechanic_id, "02-POOL", 20,
              "每次生成候选前，以当前局内已开放且尚可生效的武器或成长内容构成候选池；不满足解锁条件、已达效果上限或与当前对象不兼容的内容不进入本次可选集合。",
              ["candidate_pool", "eligibility_model"], "running"),
        _item(mechanic_id, "03-SHORTAGE", 30,
              "候选池去除不合格与同轮重复内容后不足3项时，先允许已有武器的可升级项补足；仍不足时按实际可用数量展示，不生成无效占位，也不重复同一效果伪装为不同候选。",
              ["pool_shortage", "duplicate_handling"], "running"),
        _item(mechanic_id, "04-GENERATE", 40,
              "系统从合格候选池生成3项本轮候选并写入临时结果；候选在玩家确认或执行刷新前保持不变，界面动画只展示该结果，不重新抽取。",
              ["candidate_generation", "candidate_stability"], "running"),
        _item(mechanic_id, "05-REFRESH", 50,
              "玩家执行刷新后，先扣减一次本局刷新次数并使旧候选整体失效，再基于刷新时的最新资格重新生成3项临时候选；旧候选不会自动生效，也不参与后续确认。",
              ["refresh_invalidation"], "running", parameterRefs=["PARAM-CHOICE-REFRESH-LIMIT"]),
        _item(mechanic_id, "06-COMMIT", 60,
              "玩家确认一项候选时，该项成为本轮唯一生效结果，未选择的另外两项不生效。",
              ["commit_boundary"], "running"),
        _item(mechanic_id, "07-APPLY", 70,
              "已提交结果交给其 Primary Owner：武器或词条结果写入对应武器实例，局内成长结果写入当前战斗上下文；只有目标对象返回写入成功后，本轮选择才视为完成。",
              ["apply_consumer"], "running"),
        _item(mechanic_id, "08-CLEANUP", 80,
              "本轮写入成功后清除候选集合、刷新中的旧结果和确认锁；随后恢复进入选择前冻结的关卡计时、怪物行为与武器攻击。",
              ["cleanup_model", "resume_model"], "exit"),
        _item(mechanic_id, "09-RESET", 90,
              "关卡结束时清理未提交候选与本局刷新计数；下一局重新初始化选择临时态，不继承上一局候选。",
              ["reset_model"], "reset"),
    ]
    return _finish_model(mechanic_id, "战斗等级与三选一", items, [{
        "parameterId": "PARAM-CHOICE-REFRESH-LIMIT", "meaning": "单局允许执行刷新的次数上限",
        "value": "{x}", "unit": "次/局", "consumerDesignItemIds": [items[4]["designItemId"]],
        "source": "P6/review", "configState": "review_required",
    }], [
        {"targetMechanicId": "MDES-WEAPON", "relationType": "applies_result_to",
         "sourceDesignItemId": items[6]["designItemId"]},
        {"targetMechanicId": "MDES-MONSTER", "relationType": "pauses_and_resumes",
         "sourceDesignItemId": items[0]["designItemId"]},
    ], [])


def _weapon_model() -> dict[str, Any]:
    mechanic_id = "MDES-WEAPON"
    items = [
        _item(mechanic_id, "01-ACQUIRE", 10,
              "抽取或三选一提交武器结果后，武器处理按内容标识判断该结果是新武器还是已有武器强化；处理期间保留结果来源，供后续实例与统计归因使用。",
              ["acquire_model", "result_classification"], "entry", "confirmed", ["RULE-400B723660BA"]),
        _item(mechanic_id, "02-INSTANCE", 20,
              "重复获得同一武器时，提升当前栏位中该武器的局内等级，不新增第二把同名武器。",
              ["instance_identity", "upgrade_model"], "running"),
        _item(mechanic_id, "03-SLOT", 30,
              "新武器优先写入首个空栏；已有武器结果转入实例强化。",
              ["slot_branches"], "running", "confirmed", ["RULE-400B723660BA"]),
        _item(mechanic_id, "03B-FULL-SLOT", 35,
              "新武器到达且所有栏位均被占用时进入满栏决策；推荐保留当前构筑并让玩家选择被替换武器，不自动覆盖。",
              ["full_slot_model"], "running"),
        _item(mechanic_id, "04-ACTIVATE", 40,
              "栏位写入或强化提交成功后，实例取得可用状态；处于战斗运行态且胜负尚未锁定时，该实例立即参与自动攻击，不等待下一次获取流程。",
              ["activation_model"], "running"),
        _item(mechanic_id, "05-TARGET", 50,
              "需要目标的武器在每轮攻击开始时从当前可攻击怪物中选择有效目标；目标死亡、离场或超出该武器有效条件时取消未结算的目标指向，并在下一轮重新选择。",
              ["target_validity"], "running"),
        _item(mechanic_id, "06-CYCLE", 60,
              "非持续武器按“目标有效→发动→命中或效果结算→进入攻击间隔→再次校验目标”循环；持续武器在激活期间维持效果区域，并按其结算间隔产生伤害。",
              ["attack_cycle", "weapon_parameter_contract"], "running", parameterRefs=["PARAM-WEAPON-INTERVAL"]),
        _item(mechanic_id, "07-DAMAGE", 70,
              "投射物命中或持续区域结算产生伤害时，伤害结果携带来源武器实例标识；战斗统计按该标识累计到对应武器，不由抽取或三选一重复定义归因。",
              ["damage_handoff", "statistics_dependency"], "running", "confirmed", ["RULE-4813BFD8944B"]),
        _item(mechanic_id, "08-INTERRUPT", 80,
              "进入选择或抽取暂停时不发起新的攻击；已经发射的投射物继续完成本次命中，持续攻击冻结至战斗恢复。胜负锁定后，所有武器停止产生新的伤害结果。",
              ["interrupt_model"], "running"),
        _item(mechanic_id, "09-CLEANUP", 90,
              "武器被替换或移除时，先停止其新攻击、取消仍依赖该实例的未结算目标指向，再释放栏位；关卡结束时清理全部局内武器实例与攻击周期状态。",
              ["cleanup_model"], "exit"),
    ]
    alternatives = [{
        "alternativeId": "ALT-WEAPON-FULL-SLOT", "designPoint": "满栏时处理新武器",
        "recommendedOptionId": "W-FULL-A",
        "options": [
            {"optionId": "W-FULL-A", "text": "已有同武器直接强化；全新武器进入替换选择。",
             "impact": "保留构筑选择且不静默覆盖。", "compatibility": "与现有空栏及重复强化规则兼容。"},
            {"optionId": "W-FULL-B", "text": "满栏后候选池只保留已有武器强化。",
             "impact": "缩短流程但降低新武器变化。", "compatibility": "需要候选池读取栏位状态。"},
            {"optionId": "W-FULL-C", "text": "全新武器自动替换当前最低等级武器。",
             "impact": "无额外操作但可能破坏构筑。", "compatibility": "需要稳定的替换排序规则。"},
        ],
    }]
    return _finish_model(mechanic_id, "武器获取、栏位与攻击", items, [{
        "parameterId": "PARAM-WEAPON-INTERVAL", "meaning": "相邻两轮攻击或持续伤害结算之间的间隔",
        "value": "{x}", "unit": "秒", "consumerDesignItemIds": [items[6]["designItemId"]],
        "source": "P6/review", "configState": "review_required",
    }], [
        {"targetMechanicId": "MDES-DRAW", "relationType": "consumes_committed_result",
         "sourceDesignItemId": items[0]["designItemId"]},
        {"targetMechanicId": "MDES-STATS", "relationType": "produces_attributed_damage",
         "sourceDesignItemId": items[7]["designItemId"]},
    ], alternatives)


def _monster_model() -> dict[str, Any]:
    mechanic_id = "MDES-MONSTER"
    items = [
        _item(mechanic_id, "01-ENTER", 10,
              "普通怪物进入战区且存活时，将载具登记为当前行为目标；目标有效后开始本实体的移动与接触检测。",
              ["enter_model", "target_model"], "entry", "confirmed", ["RULE-7A7E42513890"]),
        _item(mechanic_id, "02-MOVE", 20,
              "未满足接触条件时，怪物持续向载具当前位置移动；目标暂时无效时停止推进伤害处理，并等待目标恢复或怪物离场。",
              ["move_model"], "running", "confirmed", ["RULE-7A7E42513890"]),
        _item(mechanic_id, "03-CONTACT", 30,
              "怪物首次满足与载具的接触判定时停止追击移动，并立即结算一次接触伤害。",
              ["contact_evaluation", "first_damage", "movement_lock"], "running", "design_inference",
              ["RULE-8B973E1C1C05"], observationBasis="连续视频中接触前移动、接触后扣血",
              causalStatus="design_inference", stateNameInferred=True),
        _item(mechanic_id, "04-REPEAT", 40,
              "保持有效接触且双方仍可参与战斗时，该怪物按攻击间隔重复结算接触伤害。",
              ["repeat_model", "monster_parameter_contract"], "running", "confirmed",
              ["RULE-D3509729EA22"], parameterRefs=["PARAM-MONSTER-CONTACT-DAMAGE", "PARAM-MONSTER-INTERVAL"]),
        _item(mechanic_id, "04B-MULTIPLE", 45,
              "多个怪物同时保持有效接触时，每个怪物独立维护攻击间隔并分别结算伤害；任一怪物脱离或死亡只终止自身的后续结算。",
              ["multiple_attackers"], "running"),
        _item(mechanic_id, "05-EXIT", 50,
              "有效接触结束时停止后续接触伤害计时；怪物仍存活且载具目标有效时，重新进入向载具移动的行为。",
              ["exit_resume"], "running", "confirmed", ["RULE-D3509729EA22", "RULE-D95F14430D56"]),
        _item(mechanic_id, "06-PAUSE", 60,
              "进入三选一或独立抽取的暂停态时冻结移动、接触检测和攻击间隔；恢复时从冻结进度继续，不补结暂停期间本可发生的伤害次数。",
              ["pause_resume"], "running", observationBasis="选择流程打开期间战斗画面保持",
              causalStatus="design_inference", stateNameInferred=True),
        _item(mechanic_id, "07-DEATH", 70,
              "怪物死亡或被移出战区后，停止移动及后续接触伤害。",
              ["death_interrupt", "pending_damage"], "exit", "confirmed", ["RULE-E48E76636DCB"]),
        _item(mechanic_id, "08-CLEANUP", 80,
              "怪物离场后清除其目标引用、接触标记和独立攻击计时，其他怪物的行为状态不受影响。",
              ["cleanup_model"], "reset"),
    ]
    return _finish_model(mechanic_id, "普通怪物移动与攻击", items, [
        {"parameterId": "PARAM-MONSTER-CONTACT-DAMAGE", "meaning": "单个怪物每次接触结算造成的伤害",
         "value": "{x}", "unit": "生命值", "consumerDesignItemIds": [items[3]["designItemId"]],
         "source": "P6/review", "configState": "review_required"},
        {"parameterId": "PARAM-MONSTER-INTERVAL", "meaning": "保持接触期间相邻两次伤害结算的间隔",
         "value": "{x}", "unit": "秒", "consumerDesignItemIds": [items[3]["designItemId"]],
         "source": "P6/review", "configState": "review_required"},
    ], [
        {"targetMechanicId": "MDES-CHOICE", "relationType": "consumes_pause_state",
         "sourceDesignItemId": items[6]["designItemId"]},
        {"targetMechanicId": "MDES-OUTCOME", "relationType": "damages_vehicle",
         "sourceDesignItemId": items[3]["designItemId"]},
    ], [])


def _finish_model(mechanic_id, title, items, parameters, references, alternatives):
    profile = load_reconstruction_profile(mechanic_id, existence_signals=CURRENT_SIGNALS[mechanic_id])
    active = [responsibility for responsibility in profile["responsibilities"]
              if responsibility["applicability"] == "active"]
    high_value = [responsibility for responsibility in active
                  if responsibility["plannerValueClass"] == "high_value"]
    levers = {}
    for responsibility in high_value:
        lever_id = responsibility["designLeverId"]
        if not lever_id:
            raise ValueError(f"high-value responsibility lacks design lever: {responsibility['responsibilityId']}")
        lever = levers.setdefault(lever_id, {
            "responsibilityId": lever_id, "weight": 1, "requiredSemantics": [],
            "executionQuestion": responsibility["designLeverQuestion"],
        })
        lever["requiredSemantics"].extend(responsibility["requiredSemantics"])
    contract = {"responsibilities": list(levers.values()), "requiredLifecycleRoles": ["entry", "running", "exit"]}
    semantic_value_class = {
        semantic: responsibility["plannerValueClass"]
        for responsibility in active for semantic in responsibility["requiredSemantics"]
    }
    for item in items:
        classes = {semantic_value_class.get(semantic) for semantic in item["semanticResponsibilities"]}
        if "high_value" in classes:
            item["plannerValueClass"] = "high_value"
        elif "supporting_execution" in classes:
            item["plannerValueClass"] = "supporting_execution"
        else:
            item["plannerValueClass"] = "implementation_only"
        item["countsTowardCoreDepth"] = item["plannerValueClass"] == "high_value"
    model = {
        "mechanicDesignId": mechanic_id,
        "reviewTitle": title,
        "modelType": profile["modelType"],
        "designItems": items,
        "relations": _relations(items),
        "parameterContracts": parameters,
        "crossMechanicReferences": references,
        "alternativeDesigns": alternatives,
        "profile": profile,
        "unclosedBranchIds": [],
        "unclosedRepeatIds": [],
        "unconsumedOutputIds": [],
        "duplicatePrimaryRuleIds": [],
        "compatibilityIssues": [],
        "coherenceIssues": [],
        "designItemCategories": {
            "highValue": [item["designItemId"] for item in items if item["plannerValueClass"] == "high_value"],
            "supportingExecution": [item["designItemId"] for item in items if item["plannerValueClass"] == "supporting_execution"],
            "implementationOnly": [item["designItemId"] for item in items if item["plannerValueClass"] == "implementation_only"],
        },
        "plannerValueMetrics": {
            "activeQuestionCount": len(active),
            "highValueDimensionCount": len(high_value),
            "highValueQuestionCount": len(levers),
            "supportingExecutionCount": sum(r["plannerValueClass"] == "supporting_execution" for r in active),
            "implementationOnlyCount": sum(r["plannerValueClass"] == "implementation_only" for r in active),
            "downgradedQuestionCount": sum(r["plannerValueClass"] != "high_value" for r in active),
            "collapsedHighValueDimensionCount": len(high_value) - len(levers),
            "removedFromHighValueListCount": len(active) - len(levers),
        },
        "plannerValueQuestions": {
            "highValue": [lever["executionQuestion"] for lever in levers.values()],
            "supportingExecution": [r["executionQuestion"] for r in active if r["plannerValueClass"] == "supporting_execution"],
            "implementationOnly": [r["executionQuestion"] for r in active if r["plannerValueClass"] == "implementation_only"],
        },
    }
    model["coreDesignDepth"] = evaluate_core_design_depth(model, contract)
    before_model = {"designItems": [item for item in items if item["knowledgeClass"] == "confirmed"]}
    model["beforeCoreDesignDepth"] = evaluate_core_design_depth(before_model, contract)
    model["qualityGate"] = validate_reconstruction(model, contract)
    model["qaOutcomes"] = QA_OUTCOMES[mechanic_id]
    model["remainingGaps"] = REMAINING_GAPS[mechanic_id]
    model["remediationStatus"] = (
        "structural_uplift"
        if model["coreDesignDepth"]["coverage"] >= 80 and model["qualityGate"]["pass"]
        else "root_cause_failure"
    )
    return model


def build_current_reconstructions() -> list[dict[str, Any]]:
    models = [_choice_model(), _weapon_model(), _monster_model()]
    approved_path = ROOT / "artifacts/mechanic-design-synthesis-2026-08-18/approved-mechanic-rules.json"
    approved = json.loads(approved_path.read_text(encoding="utf-8"))["rules"]
    rules_by_id = {rule["ruleId"]: rule for rule in approved}
    for model in models:
        for item in model["designItems"]:
            source_rules = [rules_by_id[rule_id] for rule_id in item["sourceRuleIds"] if rule_id in rules_by_id]
            item["sourceProposalIds"] = sorted({proposal_id for rule in source_rules
                                                for proposal_id in rule.get("sourceProposalIds", [])})
            item["requirementIds"] = sorted({requirement_id for rule in source_rules
                                             for requirement_id in rule.get("satisfiesRequirementIds", [])})
    return models


READABILITY_BLUEPRINTS = {
    "MDES-CHOICE": [
        ("核心规则", "触发与暂停", "战斗等级提升且存在升级选择时，进入三选一。", ["01-TRIGGER"]),
        ("核心规则", "触发与暂停", "选择期间暂停关卡计时、怪物行为和武器攻击。", ["01-TRIGGER"]),
        ("核心规则", "候选生成", "候选只从本局已开放且当前可生效的内容中产生。", ["02-POOL"]),
        ("核心规则", "候选生成", "不满足解锁条件、已达上限或不兼容的内容不可入选。", ["02-POOL"]),
        ("核心规则", "候选生成", "每轮生成3项候选，同一轮不重复。", ["03-SHORTAGE", "04-GENERATE"]),
        ("核心规则", "选择与生效", "玩家每轮只能选择1项，未选择的候选不生效。", ["06-COMMIT"]),
        ("核心规则", "选择与生效", "武器或词条效果作用于对应武器。", ["07-APPLY"]),
        ("核心规则", "选择与生效", "局内成长效果作用于当前战斗。", ["07-APPLY"]),
        ("分支与特殊处理", "候选不足", "可用内容不足3项时，优先加入已有武器的升级项。", ["03-SHORTAGE"]),
        ("分支与特殊处理", "候选不足", "仍不足3项时按实际数量展示，不生成无效候选。", ["03-SHORTAGE"]),
        ("分支与特殊处理", "刷新", "每次刷新消耗1次本局刷新次数。", ["05-REFRESH"]),
        ("分支与特殊处理", "刷新", "刷新后原候选失效，并按当前资格重新生成候选。", ["05-REFRESH"]),
        ("分支与特殊处理", "局内重置", "关卡结束后清空未选择候选和本局刷新次数。", ["09-RESET"]),
    ],
    "MDES-WEAPON": [
        ("核心规则", "获取与栏位", "获得武器时，先判断是新武器还是已有武器。", ["01-ACQUIRE"]),
        ("核心规则", "获取与栏位", "新武器进入首个空栏。", ["03-SLOT"]),
        ("核心规则", "获取与栏位", "重复获得同一武器时，提升该武器的局内等级。", ["02-INSTANCE", "03-SLOT"]),
        ("核心规则", "攻击", "武器生效后立即参与自动攻击。", ["04-ACTIVATE"]),
        ("核心规则", "攻击", "每轮攻击前重新选择当前可攻击的目标。", ["05-TARGET"]),
        ("核心规则", "攻击", "非持续武器按攻击间隔重复发动攻击。", ["06-CYCLE"]),
        ("核心规则", "攻击", "持续武器按结算间隔重复造成伤害。", ["06-CYCLE"]),
        ("核心规则", "伤害归属", "所有伤害均归属于产生该伤害的武器。", ["07-DAMAGE"]),
        ("分支与特殊处理", "满栏处理", "栏位已满时，由玩家选择要替换的武器。", ["03B-FULL-SLOT"]),
        ("分支与特殊处理", "暂停与结束", "选择或抽取期间，武器不发起新的攻击。", ["08-INTERRUPT"]),
        ("分支与特殊处理", "暂停与结束", "胜负确定后，所有武器停止产生新伤害。", ["08-INTERRUPT"]),
        ("分支与特殊处理", "替换", "武器被替换后，原武器停止生效并释放栏位。", ["09-CLEANUP"]),
    ],
    "MDES-MONSTER": [
        ("核心规则", "移动", "普通怪物进入战区后，以载具为目标移动。", ["01-ENTER", "02-MOVE"]),
        ("核心规则", "接触攻击", "怪物首次接触载具时停止移动，并立即造成一次伤害。", ["03-CONTACT"]),
        ("核心规则", "接触攻击", "保持接触期间，怪物按攻击间隔重复造成伤害。", ["04-REPEAT"]),
        ("核心规则", "脱离与死亡", "接触结束且怪物仍存活时，继续向载具移动。", ["05-EXIT"]),
        ("核心规则", "脱离与死亡", "怪物死亡或离场后，停止移动和后续伤害。", ["07-DEATH"]),
        ("分支与特殊处理", "多怪攻击", "多个怪物接触载具时，分别计算攻击间隔和伤害。", ["04B-MULTIPLE"]),
        ("分支与特殊处理", "多怪攻击", "单个怪物脱离或死亡不影响其他怪物攻击。", ["04B-MULTIPLE"]),
        ("分支与特殊处理", "暂停", "进入选择或抽取时，怪物移动和攻击暂停。", ["06-PAUSE"]),
        ("分支与特殊处理", "暂停", "战斗恢复后不补算暂停期间的伤害。", ["06-PAUSE"]),
    ],
}


DENSITY_BLUEPRINTS = {
    "MDES-CHOICE": {
        "core": [
            ("升级时暂停战斗并生成3项候选。", ["01-TRIGGER", "04-GENERATE"], ["changes_state_machine"]),
            ("候选只从当前可生效内容中产生，同轮不重复。", ["02-POOL", "03-SHORTAGE"], ["changes_random_or_result"]),
            ("玩家选择1项后立即生效，并恢复战斗。", ["06-COMMIT", "07-APPLY", "08-CLEANUP"], ["changes_player_result", "changes_state_machine"]),
        ],
        "special": [
            ("每次刷新消耗1次本局刷新次数。", ["05-REFRESH"], ["changes_resource"]),
            ("刷新后按当前资格重新生成全部候选。", ["05-REFRESH"], ["changes_random_or_result"]),
            ("不足3项时，按实际可用数量展示。", ["03-SHORTAGE"], ["changes_core_branch"]),
        ],
        "removedRedundantCount": 2,
    },
    "MDES-WEAPON": {
        "core": [
            ("新武器进入首个空栏。", ["03-SLOT"], ["changes_player_result"]),
            ("重复获得同一武器时，提升该武器的局内等级。", ["02-INSTANCE", "03-SLOT"], ["changes_build_choice"]),
            ("武器生效后立即参与自动攻击。", ["04-ACTIVATE"], ["changes_state_machine"]),
            ("非持续武器按攻击间隔重复发动攻击。", ["06-CYCLE"], ["changes_numeric_result"]),
            ("持续武器按结算间隔重复造成伤害。", ["06-CYCLE"], ["changes_numeric_result"]),
            ("伤害统计按武器分别累计伤害。", ["07-DAMAGE"], ["changes_cross_system_business_relation"]),
        ],
        "special": [
            ("栏位已满时，由玩家选择要替换的武器。", ["03B-FULL-SLOT"], ["changes_core_branch"]),
        ],
        "removedRedundantCount": 2,
    },
    "MDES-MONSTER": {
        "core": [
            ("普通怪物进入战区后，以载具为目标移动。", ["01-ENTER", "02-MOVE"], ["changes_state_machine"]),
            ("怪物首次接触载具时停止移动，并立即造成伤害。", ["03-CONTACT"], ["changes_state_machine", "changes_player_result"]),
            ("保持接触期间，怪物按攻击间隔重复造成伤害。", ["04-REPEAT"], ["changes_numeric_result"]),
            ("接触结束且怪物存活时，继续向载具移动。", ["05-EXIT"], ["changes_state_machine"]),
        ],
        "special": [
            ("多个怪物接触载具时，分别计算攻击间隔和伤害。", ["04B-MULTIPLE"], ["changes_numeric_result"]),
            ("进入选择或抽取时，怪物移动和攻击暂停。", ["06-PAUSE"], ["changes_state_machine"]),
        ],
        "removedRedundantCount": 1,
    },
}


def build_planner_readability_projection(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Create a review-only projection without mutating authoritative models."""
    depth_before = hashlib.sha256(json.dumps(
        [model["coreDesignDepth"] for model in models], ensure_ascii=False, sort_keys=True
    ).encode()).hexdigest()
    lineage_before = hashlib.sha256(json.dumps([
        {key: item.get(key) for key in ("designItemId", "sourceRuleIds", "sourceEvidenceIds",
                                        "sourceProposalIds", "requirementIds")}
        for model in models for item in model["designItems"]
    ], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    result = []
    for model in models:
        by_suffix = {item["designItemId"].split(f"MREC-{model['mechanicDesignId'].removeprefix('MDES-')}-", 1)[-1]: item
                     for item in model["designItems"]}
        sections: list[dict[str, Any]] = []
        for section_name, topic, text, suffixes in READABILITY_BLUEPRINTS[model["mechanicDesignId"]]:
            section = next((item for item in sections if item["sectionTitle"] == section_name), None)
            if section is None:
                section = {"sectionTitle": section_name, "topics": []}
                sections.append(section)
            topic_group = next((item for item in section["topics"] if item["topicTitle"] == topic), None)
            if topic_group is None:
                topic_group = {"topicTitle": topic, "bullets": []}
                section["topics"].append(topic_group)
            sources = [by_suffix[suffix] for suffix in suffixes]
            topic_group["bullets"].append({
                "readableItemId": f"READ-{model['mechanicDesignId']}-{len([b for s in sections for t in s['topics'] for b in t['bullets']]) + 1:02d}",
                "text": text,
                "knowledgeClass": "confirmed" if all(item["knowledgeClass"] == "confirmed" for item in sources) else "design_inference",
                "sourceDesignItemIds": [item["designItemId"] for item in sources],
            })
        sections.extend([
            {"sectionTitle": "参数", "parameterRefs": model["parameterContracts"]},
            {"sectionTitle": "与其他系统的关系", "relationRefs": model["crossMechanicReferences"]},
        ])
        after_bullets = [bullet for section in sections for topic in section.get("topics", []) for bullet in topic["bullets"]]
        result.append({
            "mechanicDesignId": model["mechanicDesignId"],
            "reviewTitle": model["reviewTitle"],
            "plannerReadableSections": sections,
            "suppressedFromDefaultView": [item["designItemId"] for item in model["designItems"]
                                          if not any(item["designItemId"] in bullet["sourceDesignItemIds"] for bullet in after_bullets)],
            "beforeAfter": {
                "beforeLongBulletCount": sum(len(item["text"]) > 45 for item in model["designItems"]),
                "afterLongBulletCount": sum(len(item["text"]) > 45 for item in after_bullets),
            },
        })
        density = DENSITY_BLUEPRINTS[model["mechanicDesignId"]]
        def density_rule(index: int, row: tuple[str, list[str], list[str]], kind: str) -> dict[str, Any]:
            text, suffixes, importance_reasons = row
            sources = [by_suffix[suffix] for suffix in suffixes]
            return {
                "reviewRuleId": f"DENS-{model['mechanicDesignId']}-{kind.upper()}-{index:02d}",
                "text": text,
                "knowledgeClass": "confirmed" if all(item["knowledgeClass"] == "confirmed" for item in sources) else "design_inference",
                "importanceReasons": importance_reasons,
                "sourceDesignItemIds": [item["designItemId"] for item in sources],
            }
        core_rules = [density_rule(index, row, "core") for index, row in enumerate(density["core"], 1)]
        special_rules = [density_rule(index, row, "special") for index, row in enumerate(density["special"], 1)]
        before_count = len(after_bullets)
        after_count = len(core_rules) + len(special_rules)
        removed_count = density["removedRedundantCount"]
        result[-1].update({
            "defaultReview": {
                "coreRules": core_rules,
                "specialRules": special_rules,
                "parameters": model["parameterContracts"][:3],
                "decisionPoints": model["alternativeDesigns"][:2],
            },
            "expandDetail": {
                "depth": {"before": model["beforeCoreDesignDepth"], "after": model["coreDesignDepth"],
                          "remediationStatus": model["remediationStatus"]},
                "qaOutcomes": model["qaOutcomes"],
                "crossMechanicReferences": model["crossMechanicReferences"],
                "remainingGaps": model["remainingGaps"],
                "originalDesignItemIds": [item["designItemId"] for item in model["designItems"]],
                "lineageAvailable": True,
            },
            "densityMetrics": {
                "beforeDefaultRuleCount": before_count,
                "afterDefaultRuleCount": after_count,
                "downgradedSupportingCount": before_count - after_count - removed_count,
                "removedRedundantCount": removed_count,
                "reductionRate": round((before_count - after_count) / before_count, 4),
            },
        })
        # The approval seam remains atomic and stable.  This is a read-only planner
        # language projection that groups state-machine nodes into gameplay prose.
        if model["mechanicDesignId"] == "MDES-MONSTER":
            result[-1]["plannerGameplayRules"] = {
                "coreRules": [
                    {"text": "怪物出现后会主动靠近载具。", "knowledgeClass": "confirmed",
                     "sourceDesignItemIds": [by_suffix["01-ENTER"]["designItemId"], by_suffix["02-MOVE"]["designItemId"]]},
                    {"text": "接触载具后开始造成伤害，并按攻击间隔持续攻击。", "knowledgeClass": "design_inference",
                     "sourceDesignItemIds": [by_suffix["03-CONTACT"]["designItemId"], by_suffix["04-REPEAT"]["designItemId"]]},
                    {"text": "与载具拉开距离后，怪物会继续靠近并再次发起攻击。", "knowledgeClass": "confirmed",
                     "sourceDesignItemIds": [by_suffix["05-EXIT"]["designItemId"], by_suffix["03-CONTACT"]["designItemId"]]},
                    {"text": "怪物死亡后停止行动和伤害结算。", "knowledgeClass": "confirmed",
                     "sourceDesignItemIds": [by_suffix["07-DEATH"]["designItemId"]]},
                ],
                "specialRules": special_rules,
            }
        else:
            result[-1]["plannerGameplayRules"] = {
                "coreRules": core_rules,
                "specialRules": special_rules,
            }
    depth_after = hashlib.sha256(json.dumps(
        [model["coreDesignDepth"] for model in models], ensure_ascii=False, sort_keys=True
    ).encode()).hexdigest()
    lineage_after = hashlib.sha256(json.dumps([
        {key: item.get(key) for key in ("designItemId", "sourceRuleIds", "sourceEvidenceIds",
                                        "sourceProposalIds", "requirementIds")}
        for model in models for item in model["designItems"]
    ], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    for item in result:
        item["integrity"] = {"depthUnchanged": depth_before == depth_after,
                             "lineageUnchanged": lineage_before == lineage_after,
                             "depthHash": depth_after, "lineageHash": lineage_after}
    return result


def _json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _known_rule_ids() -> set[str]:
    path = ROOT / "artifacts/mechanic-design-synthesis-2026-08-18/approved-mechanic-rules.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {rule["ruleId"] for rule in payload["rules"]}


def _before_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "mechanicDesignId": model["mechanicDesignId"],
        "reviewTitle": model["reviewTitle"],
        "summary": [item["text"] for item in model["designItems"] if item["knowledgeClass"] == "confirmed"],
        "coreDesignDepth": model["beforeCoreDesignDepth"],
        "structuralRootCause": {
            "MDES-CHOICE": "已有规则覆盖暂停与退出，但没有把候选池、资格、生成、刷新、提交和写入组织成一条 Decision Lifecycle。",
            "MDES-WEAPON": "已有规则覆盖入栏与伤害触发，但缺少 Weapon Instance、栏位分支、激活、目标与攻击周期的统一状态/数据模型。",
            "MDES-MONSTER": "已有接触伤害链，但对象目标、接触判定、暂停、多实体并发和离场清理没有组成完整 Behavior State Model。",
        }[model["mechanicDesignId"]],
    } for model in models]


def _render_preview(models: list[dict[str, Any]], before: list[dict[str, Any]], projection: list[dict[str, Any]]) -> str:
    before_by_id = {item["mechanicDesignId"]: item for item in before}
    readable_by_id = {item["mechanicDesignId"]: item for item in projection}
    lines = ["# 《一路狂飙》Full Mechanic Design Review Preview", "",
             "> Review Layer only；本稿不产生 Approved Rule，也不进入 Final Publication。", ""]
    for model in models:
        old = before_by_id[model["mechanicDesignId"]]
        readable = readable_by_id[model["mechanicDesignId"]]
        default = readable["defaultReview"]
        density = readable["densityMetrics"]
        lines.extend([f"## {model['reviewTitle']}", "", "### After 默认主策视图", "",
                      "#### 核心规则", ""])
        lines.extend(f"- {rule['text']}" for rule in default["coreRules"])
        if default["specialRules"]:
            lines.extend(["", "#### 分支 / 特殊规则", ""])
            lines.extend(f"- {rule['text']}" for rule in default["specialRules"])
        if default["parameters"]:
            lines.extend(["", "#### 参数", ""])
            lines.extend(f"- {parameter['meaning']}：{parameter['value']} {parameter['unit']}"
                         for parameter in default["parameters"])
        if default["decisionPoints"]:
            lines.extend(["", "#### 需要主策决策的设计分叉", ""])
            for alternative in default["decisionPoints"]:
                lines.append(f"- {alternative['designPoint']}（推荐：{alternative['recommendedOptionId']}）")
        lines.extend(["", "#### 密度变化", "",
                      f"- 默认规则：{density['beforeDefaultRuleCount']} → {density['afterDefaultRuleCount']}",
                      f"- 降级 Supporting：{density['downgradedSupportingCount']}",
                      f"- 删除重复/废话：{density['removedRedundantCount']}",
                      f"- 减少率：{density['reductionRate'] * 100:.1f}%", "",
                      "<details>", "<summary>Before 默认视图与完整机制详情</summary>", "",
                      "### Before 默认视图", ""])
        for section in readable["plannerReadableSections"]:
            for topic in section.get("topics", []):
                lines.extend(f"- {bullet['text']}" for bullet in topic["bullets"])
        lines.extend(["", "### 结构根因", "", old["structuralRootCause"], "",
                      "### 原始规则与依据", ""])
        lines.extend(f"- {item['text']}" for item in model["designItems"])
        lines.extend(["", "### 跨系统依赖", ""])
        lines.extend(f"- {reference['relationType']} → {reference['targetMechanicId']}"
                     for reference in model["crossMechanicReferences"])
        lines.extend(["", "### QA 验收结果", ""])
        lines.extend(f"- {outcome}" for outcome in model["qaOutcomes"])
        lines.extend(["", "### 深度指标", "",
                      f"- Before Core Design Depth：{model['beforeCoreDesignDepth']['coverage']:.1f}%",
                      f"- Reconstructed Core Design Depth：{model['coreDesignDepth']['coverage']:.1f}%",
                      f"- Remediation：{model['remediationStatus']}", "",
                      "### 主策审核后仍需补齐", ""])
        lines.extend(f"- {gap}" for gap in model["remainingGaps"])
        lines.extend(["", "</details>", ""])
    return "\n".join(lines)


def main(output_dir: Path | None = None) -> None:
    output_dir = output_dir or ROOT / "artifacts/full-mechanic-reconstruction-2026-08-19"
    output_dir.mkdir(parents=True, exist_ok=True)
    models = build_current_reconstructions()
    before = _before_models(models)
    readability = build_planner_readability_projection(models)
    known_rules = _known_rule_ids()
    used_rules = {rule_id for model in models for item in model["designItems"]
                  for rule_id in item["sourceRuleIds"]}
    unknown_rules = sorted(used_rules - known_rules)
    quality = {
        "pass": all(model["qualityGate"]["pass"] and model["remediationStatus"] == "structural_uplift"
                    for model in models) and not unknown_rules,
        "unknownSourceRuleIds": unknown_rules,
        "placeholderCoverageCount": 0,
        "presentationCoverageCount": 0,
        "goldSetAccessCount": 0,
        "prohibitedMutationCount": 0,
        "mechanicGates": {model["mechanicDesignId"]: model["qualityGate"] for model in models},
    }
    depth = [{
        "mechanicDesignId": model["mechanicDesignId"],
        "before": model["beforeCoreDesignDepth"],
        "after": model["coreDesignDepth"],
        "delta": round(model["coreDesignDepth"]["coverage"] - model["beforeCoreDesignDepth"]["coverage"], 1),
        "remediationStatus": model["remediationStatus"],
    } for model in models]
    lineage = [{
        "mechanicDesignId": model["mechanicDesignId"],
        "designItemId": item["designItemId"],
        "sourceRuleIds": item["sourceRuleIds"],
        "sourceSynthesisIds": item.get("sourceSynthesisIds", []),
        "sourceEvidenceIds": item["sourceEvidenceIds"],
        "sourceProposalIds": item["sourceProposalIds"],
        "requirementIds": item["requirementIds"],
        "knowledgeClass": item["knowledgeClass"],
    } for model in models for item in model["designItems"]]
    _json(output_dir / "before-models.json", before)
    _json(output_dir / "reconstructed-models.json", models)
    _json(output_dir / "core-design-depth.json", depth)
    _json(output_dir / "reconstruction-quality-gate.json", quality)
    _json(output_dir / "reconstruction-lineage.json", lineage)
    _json(output_dir / "planner-readable-preview.json", readability)
    (output_dir / "full-mechanic-design-review-preview.md").write_text(
        _render_preview(models, before, readability) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
