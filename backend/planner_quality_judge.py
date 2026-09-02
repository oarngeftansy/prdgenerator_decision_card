"""Deterministic quality judge for Master Planner output.

Quality is measured by mechanic closure and implementation readiness. Document
length, heading count and raw rule count are intentionally not scoring dimensions.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


DIMENSIONS = (
    "mechanicClosure",
    "stateTransition",
    "lifecycle",
    "conditionBranch",
    "dataDependency",
    "calculationAttribution",
    "resetPersistence",
    "ownerStructure",
    "ruleRelationDensity",
    "qaReadiness",
)


def _text(value: Any) -> str:
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {_text(item)}" for key, item in value.items())
    return str(value or "")


def _presence(rule: dict[str, Any], *fields: str) -> bool:
    return any(rule.get(field) not in (None, "", [], {}) for field in fields)


def _rule_dimension_hits(rule: dict[str, Any]) -> set[str]:
    text = _text(rule)
    hits: set[str] = set()
    if _presence(rule, "trigger", "conditions", "result", "exitCondition"):
        hits.add("mechanicClosure")
    if _presence(rule, "stateChange", "beforeState", "afterState", "resultState") or any(k in text for k in ("状态", "进入", "退出", "死亡", "锁定", "解锁")):
        hits.add("stateTransition")
    if _presence(rule, "lifecycle", "initialize", "expire", "remove") or any(k in text for k in ("创建", "初始化", "生效", "结束", "清空")):
        hits.add("lifecycle")
    if _presence(rule, "trigger", "conditions", "branches", "exception") or any(k in text for k in ("当", "若", "否则", "例外", "不足", "上限")):
        hits.add("conditionBranch")
    if _presence(rule, "dependencies", "inputs", "outputs", "sourceRuleIds"):
        hits.add("dataDependency")
    if _presence(rule, "formulaExpression", "formula", "attribution", "parameters") or any(k in text for k in ("计算", "公式", "取整", "归因", "权重")):
        hits.add("calculationAttribution")
    if _presence(rule, "reset", "persistence", "scope", "lifetime") or any(k in text for k in ("重置", "保留", "继承", "跨局", "本局", "持久")):
        hits.add("resetPersistence")
    if _presence(rule, "canonicalOwner", "ownerChapterId", "ownerMechanicId"):
        hits.add("ownerStructure")
    if _presence(rule, "sourceRuleIds", "dependencies", "relatedRuleIds", "inputs", "outputs"):
        hits.add("ruleRelationDensity")
    if _presence(rule, "acceptanceCases", "exception", "failure", "validation") or any(k in text for k in ("失败", "无效", "重复", "不足", "上限", "重连", "并发")):
        hits.add("qaReadiness")
    return hits


def evaluate_execution_readiness(publication: dict[str, Any]) -> dict[str, Any]:
    rules = [rule for rule in publication.get("rules") or [] if isinstance(rule, dict)]
    chapters = [chapter for chapter in publication.get("chapters") or [] if isinstance(chapter, dict)]
    gaps = [gap for gap in publication.get("gaps") or [] if isinstance(gap, dict)]
    unresolved = [gap for gap in gaps if gap.get("status") not in {"resolved", "not_applicable", "planner_resolved"}]

    hits_by_dimension: dict[str, int] = defaultdict(int)
    rules_by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rule in rules:
        owner = str(rule.get("canonicalOwner") or rule.get("ownerChapterId") or "")
        if owner:
            rules_by_owner[owner].append(rule)
        for dimension in _rule_dimension_hits(rule):
            hits_by_dimension[dimension] += 1

    applicable_chapters = [chapter for chapter in chapters if chapter.get("publicationEligibility", "eligible") == "eligible"]
    closed_chapters = [
        chapter for chapter in applicable_chapters
        if rules_by_owner.get(str(chapter.get("chapterId") or ""))
        and not any(str(gap.get("chapterId") or "") == str(chapter.get("chapterId") or "") for gap in unresolved)
    ]
    chapter_denominator = max(1, len(applicable_chapters))
    rule_denominator = max(1, len(rules))

    scores: dict[str, int] = {}
    for dimension in DIMENSIONS:
        if dimension == "mechanicClosure":
            ratio = len(closed_chapters) / chapter_denominator
        elif dimension == "ownerStructure":
            ratio = sum(1 for rule in rules if rule.get("canonicalOwner") or rule.get("ownerChapterId")) / rule_denominator
        else:
            ratio = min(1.0, hits_by_dimension[dimension] / rule_denominator)
        scores[dimension] = round(ratio * 100)

    overall = round(sum(scores.values()) / len(DIMENSIONS)) if DIMENSIONS else 0
    critical = []
    if unresolved:
        critical.append("unresolved_execution_gaps")
    if applicable_chapters and len(closed_chapters) < len(applicable_chapters):
        critical.append("mechanic_closure_incomplete")
    if scores["ownerStructure"] < 100:
        critical.append("owner_structure_incomplete")
    return {
        "overall": overall,
        "dimensions": scores,
        "criticalIssues": critical,
        "unresolvedGapCount": len(unresolved),
        "closedChapterCount": len(closed_chapters),
        "applicableChapterCount": len(applicable_chapters),
        "ready": not critical and overall >= 70,
        "scoringPolicy": "execution_readiness_v1",
    }
