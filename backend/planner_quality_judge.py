from __future__ import annotations

from collections import Counter
import re
from typing import Any

from .rule_status import normalize_rule_status


DIMENSIONS = (
    "gameplayCoverage", "mechanismDepth", "ruleClosure", "systemHierarchy",
    "stateLifecycle", "randomCompleteness", "dependency", "edgeCase",
    "parameterSemantics", "logicPresentationSeparation", "implementationReadiness",
    "qaReadiness", "statusProvenanceIntegrity", "hiddenInference", "compressionLoss",
)

_REQUIRED_CLOSURE_FIELDS = ("behavior", "subject")
_META_PHRASES = (
    "【推断】", "【黄色：推断】", "AI推断", "素材未确认", "根据现有素材推测",
    "尚未确认", "建议确认", "素材只证明", "仍由决策卡确认",
)
_HEDGES = ("可能", "或许", "大概率", "推测")


def _rule_score(rule: dict[str, Any]) -> int:
    fields = (
        "trigger", "conditions", "behavior", "result", "stateChange",
        "exitCondition", "exception", "parameterRefs",
    )
    return sum(bool(rule.get(field)) for field in fields)


def _text(rule: dict[str, Any]) -> str:
    values = [rule.get("behavior"), rule.get("trigger"), rule.get("result"), rule.get("exception")]
    return " ".join(str(value or "") for value in values)


def evaluate_planner_quality(model: dict[str, Any]) -> dict[str, Any]:
    """Independent deterministic pre-judge.

    This does not replace model-based golden-sample judging. It provides hard invariants so
    writer output cannot grade itself into publication when provenance, hierarchy or closure
    is structurally broken.
    """
    rules = [item for item in model.get("rules") or [] if isinstance(item, dict)]
    chapters = [item for item in model.get("chapters") or [] if isinstance(item, dict)]
    findings: list[dict[str, Any]] = []

    for rule in rules:
        rid = str(rule.get("ruleId") or "UNKNOWN")
        missing = [field for field in _REQUIRED_CLOSURE_FIELDS if not rule.get(field)]
        if missing:
            findings.append({"dimension": "ruleClosure", "severity": "error", "ruleId": rid, "message": "缺少执行结论字段：" + ", ".join(missing)})
        status = normalize_rule_status(rule.get("knowledgeStatus"), inference_level=rule.get("inferenceLevel"), source_type=rule.get("sourceType"))
        if not rule.get("knowledgeStatus") and str(rule.get("inferenceLevel") or "observed").casefold() not in {"observed", "confirmed", ""}:
            findings.append({"dimension": "hiddenInference", "severity": "error", "ruleId": rid, "message": "推断规则没有显式 knowledgeStatus。"})
        text = _text(rule)
        if any(phrase in text for phrase in _META_PHRASES):
            findings.append({"dimension": "statusProvenanceIntegrity", "severity": "error", "ruleId": rid, "message": "正文包含来源/审核元话语，应仅由视觉状态表达。"})
        if status in {"INFERRED", "PROPOSED"} and any(hedge in text for hedge in _HEDGES):
            findings.append({"dimension": "implementationReadiness", "severity": "warning", "ruleId": rid, "message": "推断/方案正文仍使用模糊措辞，应给出具体执行结论。"})
        if _rule_score(rule) <= 1:
            findings.append({"dimension": "mechanismDepth", "severity": "warning", "ruleId": rid, "message": "规则只有单句行为，缺少触发、结果、生命周期或边界。"})

    chapter_ids = [str(item.get("chapterId") or "") for item in chapters]
    duplicates = [key for key, count in Counter(chapter_ids).items() if key and count > 1]
    for key in duplicates:
        findings.append({"dimension": "systemHierarchy", "severity": "error", "chapterId": key, "message": "重复 chapterId。"})

    semantic_keys = [str(item.get("semanticKey") or "").strip().casefold() for item in rules]
    for key, count in Counter(key for key in semantic_keys if key).items():
        if count > 1:
            findings.append({"dimension": "compressionLoss", "severity": "warning", "semanticKey": key, "message": "相同 semanticKey 出现多次，Final 必须去重并保留唯一 Owner。"})

    # Hierarchy is dynamic; absence of hard-coded chapter-count expectations is deliberate.
    scores = {dimension: 100 for dimension in DIMENSIONS}
    for item in findings:
        dim = item["dimension"]
        scores[dim] = max(0, scores.get(dim, 100) - (25 if item["severity"] == "error" else 10))
    overall = round(sum(scores.values()) / len(scores)) if scores else 0
    errors = sum(item["severity"] == "error" for item in findings)
    return {
        "score": overall,
        "pass": errors == 0 and overall >= 90,
        "dimensions": scores,
        "findings": findings,
        "errorCount": errors,
        "warningCount": sum(item["severity"] == "warning" for item in findings),
        "policy": "no_hidden_inference",
    }
