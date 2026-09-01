"""Master Planner execution layer.

Evidence reconstruction remains authoritative for what the source proves. This
layer owns a different responsibility: closing implementation gaps with explicit,
traceable planning decisions so evidence insufficiency does not stall delivery.

The model is asked for decisive business rules. Provenance is carried separately:
- inferred: likely reconstruction of the source mechanic
- proposed: planner decision selected to close an implementation gap
No provenance label is inserted into user-visible rule copy.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from .ai_provider import ProviderConfig, Transport, chat_json_object
from .planner_quality_judge import evaluate_execution_readiness


_ALLOWED_STATES = {"inferred", "proposed"}
_FORBIDDEN_VISIBLE_META = (
    "待确认", "未知待确认", "根据素材推测", "根据画面推测", "合理推断", "可能", "或许", "建议可以",
    "【黄色：推断】", "【推断】", "【建议】",
)


class MasterPlannerError(ValueError):
    pass


def _normalized(value: Any) -> str:
    return re.sub(r"[\s，。；：、,.!?！？()（）]+", "", str(value or "").casefold())


def _open_gap(gap: dict[str, Any]) -> bool:
    return (
        gap.get("gapDomain", "planning") == "planning"
        and gap.get("applicabilityStatus", "applicable") == "applicable"
        and gap.get("status") not in {"resolved", "not_applicable", "planner_resolved"}
    )


def _gap_id(gap: dict[str, Any], index: int) -> str:
    existing = str(gap.get("gapId") or "").strip()
    if existing:
        return existing
    seed = "|".join(str(gap.get(key) or "") for key in ("chapterId", "schemaSlot", "intent", "question", "gapKind"))
    return "MP-GAP-" + hashlib.sha1(f"{index}|{seed}".encode("utf-8")).hexdigest()[:12].upper()


def _compact_context(projection: dict[str, Any], understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    """Keep the dynamic gameplay structure; never collapse it to a sample schema."""
    publication = projection.get("publication") if isinstance(projection.get("publication"), dict) else projection
    chapters = []
    for chapter in publication.get("chapters") or []:
        chapters.append({
            "chapterId": chapter.get("chapterId"),
            "system": chapter.get("system"),
            "subsystem": chapter.get("subsystem"),
            "mechanism": chapter.get("mechanism") or chapter.get("mechanic"),
            "object": chapter.get("object"),
            "title": chapter.get("title"),
            "schemaResponsibilities": chapter.get("schemaResponsibilities") or [],
        })
    rules = []
    for rule in publication.get("rules") or []:
        rules.append({
            "ruleId": rule.get("ruleId"),
            "ownerChapterId": rule.get("canonicalOwner") or rule.get("ownerChapterId"),
            "ownerMechanicId": rule.get("ownerMechanicId"),
            "intent": rule.get("intent"),
            "schemaSlot": rule.get("schemaSlot"),
            "behavior": rule.get("behavior"),
            "trigger": rule.get("trigger"),
            "conditions": rule.get("conditions") or [],
            "result": rule.get("result"),
            "stateChange": rule.get("stateChange") or rule.get("resultState"),
            "dependencies": rule.get("dependencies") or [],
            "persistence": rule.get("persistence"),
            "reset": rule.get("reset"),
        })
    understood = understanding or {}
    dynamic_graph = (
        understood.get("SystemGraph")
        or understood.get("systemGraph")
        or publication.get("systemGraph")
        or publication.get("dynamicSystemGraph")
        or {}
    )
    mechanisms = (
        understood.get("Mechanisms")
        or understood.get("mechanisms")
        or publication.get("mechanisms")
        or []
    )
    rule_groups = publication.get("ruleGroups") or understood.get("RuleGroups") or understood.get("ruleGroups") or []
    return {
        "gameplaySummary": understood.get("Summary") or understood.get("summary") or "",
        "coreLoop": understood.get("CoreLoop") or understood.get("coreLoop") or [],
        "systems": understood.get("Systems") or understood.get("systems") or [],
        "systemGraph": dynamic_graph,
        "mechanisms": mechanisms,
        "ruleGroups": rule_groups,
        "chapters": chapters,
        "existingRules": rules,
    }


def _prompt(context: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    gap_payload = [{
        "gapId": gap["gapId"],
        "chapterId": gap.get("chapterId"),
        "intent": gap.get("intent"),
        "schemaSlot": gap.get("schemaSlot"),
        "gapKind": gap.get("gapKind"),
        "question": gap.get("question"),
        "knownContext": gap.get("knownContext") or gap.get("evidenceSummary") or "",
    } for gap in gaps]
    return """你是商业游戏项目的主策划。上游已经完成玩法理解与证据还原，你现在只负责把剩余执行缺口闭合成程序、数值、UI和QA都能直接使用的明确规则。

硬性要求：
1. 每个 gapId 必须且只能返回一个 decision。
2. evidence 不足不是停止条件。必须选择一个确定、可实现的默认方案把规则闭合。
3. 如果答案更像是在还原原玩法，publicationState=inferred；如果是为了闭合实现缺口而做的主策决定，publicationState=proposed。
4. decision 必须直接写最终规则，不得出现“待确认、未知待确认、可能、或许、根据素材推测、根据画面推测、建议可以、【推断】、【建议】”等审核话术。
5. 不要虚构正式配置表名、字段名或ID。没有既有命名时，用“配置项/对应配置”描述。
6. 不套用任何固定玩法模板。先识别当前 gap 属于什么机制，再只闭合该机制实际需要的维度。可用维度包括但不限于：触发/前置条件、玩家或系统动作、状态与生命周期、资源与消耗、选择或随机、空间/目标关系、时序/回合/波次、计算与结算、奖励、持久化/重置、异常/失败/恢复、交互反馈。某维度与当前机制无关时不得为了凑完整而强行生成。
7. 对选择/随机机制，仅在当前玩法确实存在选择或随机时，明确其实际需要的候选来源、资格、数量、重复/互斥、重抽/刷新、空集合、确认与重置等规则；对移动、战斗、经营、建造、解谜、对话、回合、模拟等其他机制，应按其自身状态机和依赖关系闭合，禁止注入“技能/武器/怪物/候选池”等无关概念。
8. 生命周期要明确初始化、生效、变化、继承/重置；状态机制要明确触发、条件、执行、结果和异常边界。只覆盖实际相关项。
9. 保持已有已确认规则，不得用新决定推翻它们。若 gap 与已有规则冲突，选择与已有规则一致的方案。
10. Golden Sample 只用于判断执行深度、规则闭合度和文档质量，不是当前项目的目录、机制清单、对象命名或字段模板。
11. 只返回 JSON 对象，不写解释。

返回格式：
{"decisions":[{"gapId":"...","publicationState":"inferred|proposed","decision":"确定性规则正文","ruleType":"logic|flow|numeric|config|presentation","trigger":"可为空","conditions":[],"result":"可为空","exception":"可为空","persistence":"可为空","reset":"可为空","dependencies":[],"acceptanceCases":[]}]}。

项目动态结构与已确认规则：
""" + json.dumps(context, ensure_ascii=False) + "\n\n待闭合缺口：\n" + json.dumps(gap_payload, ensure_ascii=False)


def _validate_decisions(payload: dict[str, Any], gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw = payload.get("decisions")
    if not isinstance(raw, list):
        raise MasterPlannerError("Master Planner response must contain decisions")
    expected = {gap["gapId"] for gap in gaps}
    seen: set[str] = set()
    result = []
    for item in raw:
        if not isinstance(item, dict):
            raise MasterPlannerError("Master Planner decision must be an object")
        gap_id = str(item.get("gapId") or "")
        if gap_id not in expected or gap_id in seen:
            raise MasterPlannerError("Master Planner returned an unknown or duplicate gapId")
        state = str(item.get("publicationState") or "")
        if state not in _ALLOWED_STATES:
            raise MasterPlannerError("Master Planner publicationState must be inferred or proposed")
        decision = str(item.get("decision") or "").strip()
        if not decision:
            raise MasterPlannerError("Master Planner decision cannot be empty")
        if any(marker in decision for marker in _FORBIDDEN_VISIBLE_META):
            raise MasterPlannerError("Master Planner leaked review/meta language into Final rule copy")
        if decision[-1] not in "。！？；":
            decision += "。"
        result.append({
            **item,
            "gapId": gap_id,
            "publicationState": state,
            "decision": decision,
            "ruleType": item.get("ruleType") if item.get("ruleType") in {"logic", "flow", "numeric", "config", "presentation"} else "logic",
            "conditions": [str(value) for value in (item.get("conditions") or []) if str(value).strip()],
            "dependencies": [str(value) for value in (item.get("dependencies") or []) if str(value).strip()],
            "acceptanceCases": [value for value in (item.get("acceptanceCases") or []) if isinstance(value, (str, dict))],
        })
        seen.add(gap_id)
    missing = expected - seen
    if missing:
        raise MasterPlannerError("Master Planner omitted execution gaps: " + ", ".join(sorted(missing)))
    return result


def _decision_rule(decision: dict[str, Any], gap: dict[str, Any]) -> dict[str, Any]:
    gap_id = decision["gapId"]
    state = decision["publicationState"]
    rule_id = "RULE-MP-" + hashlib.sha1((gap_id + "|" + decision["decision"]).encode("utf-8")).hexdigest()[:12].upper()
    return {
        "ruleId": rule_id,
        "subject": gap.get("subject") or gap.get("object") or "系统",
        "behavior": decision["decision"].rstrip("。；"),
        "trigger": str(decision.get("trigger") or "").strip(),
        "conditions": decision.get("conditions") or [],
        "result": str(decision.get("result") or "").strip(),
        "exception": str(decision.get("exception") or "").strip(),
        "persistence": str(decision.get("persistence") or "").strip(),
        "reset": str(decision.get("reset") or "").strip(),
        "dependencies": decision.get("dependencies") or [],
        "acceptanceCases": decision.get("acceptanceCases") or [],
        "intent": gap.get("intent") or "PlannerCompletion",
        "schemaSlot": gap.get("schemaSlot") or "planner_completion",
        "ruleType": decision["ruleType"],
        "ownerChapterId": gap.get("chapterId"),
        "ownerMechanicId": gap.get("mechanicId") or gap.get("ownerMechanicId"),
        "canonicalOwner": gap.get("chapterId") or gap.get("mechanicId") or gap.get("ownerMechanicId"),
        "definitionMode": "full_definition",
        "semanticValidity": "valid",
        "reviewStatus": state,
        "confirmationStatus": "confirmed",
        "publicationEligibility": "eligible",
        "publicationState": state,
        "inferenceLevel": "master_planner_completion",
        "sourceGapIds": [gap_id],
        "sourceRuleIds": list(gap.get("sourceRuleIds") or []),
        "sourceFactIds": list(gap.get("sourceFactIds") or []),
        "evidenceIds": list(gap.get("evidenceIds") or []),
        "guardReasons": [],
    }


def apply_planner_decisions(projection: dict[str, Any], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge validated Master Planner decisions into the publication projection."""
    output = deepcopy(projection)
    publication = output.setdefault("publication", {}) if "publication" in output else output
    gaps = [deepcopy(gap) for gap in publication.get("gaps") or publication.get("finalPlanningGaps") or []]
    indexed = {}
    for index, gap in enumerate(gaps, 1):
        gap["gapId"] = _gap_id(gap, index)
        indexed[gap["gapId"]] = gap
    new_rules = []
    for decision in decisions:
        gap = indexed.get(decision["gapId"])
        if gap is None:
            raise MasterPlannerError("decision references a gap outside the publication projection")
        rule = _decision_rule(decision, gap)
        new_rules.append(rule)
        gap.update({
            "status": "planner_resolved",
            "resolution": decision["decision"],
            "resolvedByRuleId": rule["ruleId"],
            "publicationState": decision["publicationState"],
        })

    existing = list(publication.get("rules") or [])
    existing_keys = {_normalized(rule.get("behavior")) for rule in existing}
    for rule in new_rules:
        if _normalized(rule.get("behavior")) not in existing_keys:
            existing.append(rule)
            existing_keys.add(_normalized(rule.get("behavior")))
    publication["rules"] = existing
    publication["gaps"] = gaps
    publication["finalPlanningGaps"] = [gap for gap in gaps if _open_gap(gap)]

    chapter_by_id = {str(chapter.get("chapterId") or ""): chapter for chapter in publication.get("chapters") or []}
    for rule in new_rules:
        chapter = chapter_by_id.get(str(rule.get("canonicalOwner") or ""))
        if chapter is not None:
            chapter.setdefault("ruleDefinitions", []).append(deepcopy(rule))
            chapter["gaps"] = [gap for gap in gaps if gap.get("chapterId") == chapter.get("chapterId") and _open_gap(gap)]
            chapter["closureStatus"] = "closed" if not chapter["gaps"] else chapter.get("closureStatus", "open")
            chapter["publicationEligibility"] = "eligible"

    publication["masterPlanner"] = {
        "status": "completed",
        "decisionCount": len(decisions),
        "inferredCount": sum(item["publicationState"] == "inferred" for item in decisions),
        "proposedCount": sum(item["publicationState"] == "proposed" for item in decisions),
    }
    publication["qualityJudge"] = evaluate_execution_readiness(publication)
    return output


def complete_execution_plan(
    projection: dict[str, Any],
    config: ProviderConfig,
    *,
    understanding: dict[str, Any] | None = None,
    transport: Transport | None = None,
) -> dict[str, Any]:
    """Close all applicable planning gaps in one bounded structured model call."""
    source = deepcopy(projection)
    publication = source.get("publication") if isinstance(source.get("publication"), dict) else source
    gaps = []
    for index, raw_gap in enumerate(publication.get("gaps") or publication.get("finalPlanningGaps") or [], 1):
        if not isinstance(raw_gap, dict) or not _open_gap(raw_gap):
            continue
        gap = deepcopy(raw_gap)
        gap["gapId"] = _gap_id(gap, index)
        gaps.append(gap)
    if not gaps:
        publication["masterPlanner"] = {"status": "completed", "decisionCount": 0, "inferredCount": 0, "proposedCount": 0}
        publication["qualityJudge"] = evaluate_execution_readiness(publication)
        return source

    payload = chat_json_object(
        config,
        [{"role": "user", "content": _prompt(_compact_context(source, understanding), gaps)}],
        transport=transport,
        max_attempts=3,
        temperature=0.1,
    )
    decisions = _validate_decisions(payload, gaps)

    # Ensure generated ids are available to the merge even if the upstream gaps
    # did not previously carry a persistent gapId.
    publication["gaps"] = gaps
    publication["finalPlanningGaps"] = deepcopy(gaps)
    return apply_planner_decisions(source, decisions)
