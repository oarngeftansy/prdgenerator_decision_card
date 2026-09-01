from __future__ import annotations

import hashlib
from typing import Any


_P4 = {
    "acquisition_to_slot_relation": ("获得新武器后，武器栏如何处理？", "structured_rule"),
    "damage_model": ("武器伤害按什么规则计算？", "rule_choice"),
    "candidate_eligibility": ("三选一中，哪些武器强化或词条可以出现？", "structured_rule"),
    "refresh_reset_scope": ("广告刷新次数按什么周期重置？", "rule_choice"),
    "boss_stage_trigger": ("满足什么条件后进入首领战？", "structured_rule"),
    "growth_source": ("关卡内通过什么方式获得成长进度？", "structured_rule"),
    "upgrade_rule": ("成长进度满足什么规则时提升战斗等级？", "structured_rule"),
    "success_condition": ("满足什么条件时本关挑战成功？", "structured_rule"),
}

_P6 = {
    "attack_range": ("武器攻击范围", "number_with_unit"),
    "attack_interval": ("武器攻击间隔", "number_with_unit"),
    "refresh_max_count": ("单周期广告刷新次数上限", "integer"),
}

_OPTIONS = {
    "damage_model": [
        {"optionId": "fixed_value", "label": "固定伤害值"},
        {"optionId": "base_plus_modifier", "label": "基础伤害与修正共同计算"},
        {"optionId": "custom_formula", "label": "自定义计算规则"},
    ],
    "refresh_reset_scope": [
        {"optionId": "per_selection", "label": "每次三选一重置"},
        {"optionId": "per_run", "label": "每局重置"},
        {"optionId": "daily", "label": "每日重置"},
        {"optionId": "custom", "label": "自定义周期"},
    ],
}


def _id(prefix: str, dimension: str) -> str:
    digest = hashlib.sha1(dimension.encode("utf-8")).hexdigest()[:12].upper()
    return f"{prefix}-{digest}"


def build_hidden_rule_review_package(review_required_gaps: list[dict[str, Any]]) -> dict[str, Any]:
    """Adapt authoritative Closure gaps to the existing P4/P6 product stages."""
    p4: list[dict[str, Any]] = []
    p6: list[dict[str, Any]] = []
    for gap in review_required_gaps:
        dimension = str(gap.get("dimensionId", ""))
        stage = gap.get("reviewStage")
        common = {
            "dimensionId": dimension,
            "sourceRuleSemanticId": gap.get("ruleSemanticId"),
            "approvalStatus": "unreviewed",
            "recommendationOnly": True,
            "diagnosticOverride": False,
        }
        if stage == "P4" and dimension in _P4:
            question, control_type = _P4[dimension]
            p4.append({
                **common,
                "decisionId": _id("HDR", dimension),
                "question": question,
                "decisionClass": "rule_choice" if control_type == "rule_choice" else "complex_rule",
                "control": {"type": control_type, "allowCustom": True,
                            "options": _OPTIONS.get(dimension, [])},
                "promotionTarget": "Approved Rule",
            })
        elif stage == "P6" and dimension in _P6:
            label, control_type = _P6[dimension]
            p6.append({
                **common,
                "parameterReviewId": _id("HPR", dimension),
                "label": label,
                "question": f"{label}是多少？",
                "decisionClass": "numeric_parameter",
                "control": {"type": control_type, "unitRequired": control_type == "number_with_unit"},
                "promotionTarget": "Approved Parameter",
            })

    visible = " ".join(
        [item["question"] for item in p4] + [item["question"] for item in p6]
        + [option["label"] for item in p4 for option in item["control"].get("options", [])]
    )
    internal_terms = ("candidate_filter", "contract", "breakpoint", "pipeline", "node", "edge")
    diagnostic_answers = ("优先填入空武器栏", "每日最多", "击败怪物后获得", "击败首领后")
    gate = {
        "autoApproved": sum(item["approvalStatus"] != "unreviewed" for item in p4 + p6),
        "diagnosticOverrideLeak": sum(term in visible for term in diagnostic_answers),
        "internalSemanticLeak": sum(term in visible for term in internal_terms),
        "unknownDimensionPromoted": len(review_required_gaps) - len(p4) - len(p6),
    }
    gate["pass"] = all(value == 0 for value in gate.values())
    return {"p4Decisions": p4, "p6Parameters": p6, "qualityGate": gate}
