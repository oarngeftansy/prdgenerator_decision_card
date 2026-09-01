"""Close mechanics referenced by recovered rules against approved information."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .approved_information_recovery import collect_approved_narratives


_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "planner_knowledge" / "recovered-rule-dependency-policies-v1.json"


def _policy() -> dict[str, Any]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def _norm(value: Any) -> str:
    return re.sub(r"[\s，。；：、,.!?！？()（）]", "", str(value or "")).casefold()


def _sentences(text: Any) -> list[str]:
    result = []
    for sentence in re.split(r"(?<=[。！？!?；;])|\n+", str(text or "")):
        sentence = re.sub(r"^\s*(?:[-•]|\d+[.、]|[（(]?\d+[）)])\s*", "", sentence.strip())
        if sentence:
            result.append(sentence.rstrip("。；;"))
    return result


def _references(rule: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    for item in rule.get("referencedEntities") or []:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        kind = str(item.get("requiredState") or "entity_definition")
        found.append({"referenceKind": kind, "name": str(item["name"]), "entityId": item.get("entityId")})
    behavior = str(rule.get("behavior") or "")
    for kind, contract in (policy.get("dependencies") or {}).items():
        for pattern in contract.get("referencePatterns") or []:
            for match in re.finditer(pattern, behavior):
                name = str(match.groupdict().get("name") or "").strip(" 当若如果只要")
                if name:
                    found.append({"referenceKind": kind, "name": name})
    result = []
    seen = set()
    for item in found:
        key = (item["referenceKind"], _norm(item["name"]))
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _chapter_for(reference: dict[str, Any], chapters: list[dict[str, Any]], contract: dict[str, Any]) -> dict[str, Any] | None:
    name = _norm(reference["name"])
    scored = []
    for chapter in chapters:
        aliases = [chapter.get("object"), chapter.get("title"), *(chapter.get("entityScope") or [])]
        entity_score = max((2 if _norm(alias) == name else 1 if name in _norm(alias) or _norm(alias) in name else 0 for alias in aliases if alias), default=0)
        if reference["referenceKind"] == "settlement" and chapter.get("chapterType") == "settlement":
            entity_score = max(entity_score, 2)
        if not entity_score:
            continue
        title = str(chapter.get("title") or "")
        role_score = sum(term in title for term in contract.get("ownerTitleTerms") or [])
        scored.append((entity_score, role_score, chapter))
    return max(scored, key=lambda item: (item[0], item[1]))[2] if scored else None


def _support(reference: dict[str, Any], narratives: list[dict[str, Any]], contract: dict[str, Any], source_id: str, chapter: dict[str, Any] | None) -> tuple[dict[str, Any], str] | None:
    name = str(reference["name"])
    aliases = [name]
    if reference["referenceKind"] != "settlement":
        for alias in [*(chapter or {}).get("entityScope", []), (chapter or {}).get("object")]:
            alias = str(alias or "")
            if alias and (_norm(alias) in _norm(name) or _norm(name) in _norm(alias)):
                aliases.append(alias)
    if reference["referenceKind"] == "settlement" and name.endswith("结算"):
        aliases.append(name.removesuffix("结算") + "页")
    aliases = list(dict.fromkeys(aliases))
    candidates = []
    for narrative in narratives:
        if str(narrative.get("narrativeId") or "") == source_id:
            continue
        for sentence in _sentences(narrative.get("text")):
            if not any(alias in sentence for alias in aliases):
                continue
            state = name.removesuffix("结算")
            if any(template.format(name=name, state=state) in sentence for template in contract.get("excludedSupportTemplates") or []):
                continue
            template_score = max((sum(
                template.format(name=alias, state=state) in sentence
                for template in contract.get("supportTemplates") or []
            ) for alias in aliases), default=0)
            strong_score = max((sum(
                template.format(name=alias, state=state) in sentence
                for template in contract.get("strongSupportTemplates") or []
            ) for alias in aliases), default=0)
            if contract.get("strongSupportTemplates") and not strong_score:
                continue
            if contract.get("supportTemplates") and not template_score and not strong_score:
                continue
            score = sum(pattern in sentence for pattern in contract.get("supportPatterns") or [])
            if score:
                candidates.append((strong_score * 100 + template_score * 10 + score, len(sentence), narrative, sentence))
    if not candidates:
        return None
    _, _, narrative, sentence = max(candidates, key=lambda item: (item[0], -item[1]))
    return narrative, sentence


def _existing_definition(reference: dict[str, Any], rules: list[dict[str, Any]], contract: dict[str, Any], source_rule_id: str) -> dict[str, Any] | None:
    name = _norm(reference["name"])
    return next((
        rule for rule in rules
        if str(rule.get("ruleId") or "") != source_rule_id
        if rule.get("reviewStatus") in {"approved", "confirmed"}
        and name in _norm(rule.get("subject"))
        and (
            rule.get("intent") == contract.get("intent")
            or rule.get("schemaSlot") == contract.get("schemaSlot")
            or any(term in str(rule.get("behavior") or "") for term in contract.get("supportPatterns") or [])
        )
    ), None)


def close_recovered_rule_dependencies(
    *, approved_data: dict[str, Any], chapters: list[dict[str, Any]], rules: list[dict[str, Any]],
    lesson_registry=None,
) -> dict[str, Any]:
    if lesson_registry is None:
        from .system_lesson_registry import load_system_lesson_registry
        lesson_registry = load_system_lesson_registry()
    if not lesson_registry.is_policy_enabled(
        "closure.recovered_dependencies", "dependency_closure"
    ):
        return {
            "chapters": deepcopy(chapters), "rules": [], "gaps": [], "references": [],
            "unresolvedMechanicReferences": [], "undefinedReferencedEntities": [],
            "policyStatus": "disabled",
        }
    policy = _policy()
    chapters = deepcopy(chapters)
    rules = deepcopy(rules)
    narratives = collect_approved_narratives(approved_data, chapters)
    references = []
    added_rules = []
    gaps = []
    recovered_sources = [rule for rule in rules if rule.get("inferenceLevel") == "approved_information_recovery"]
    recovered_sources.sort(key=lambda rule: ({"VictoryCondition": 0, "FailureCondition": 1}.get(str(rule.get("intent")), 2), str(rule.get("ruleId"))))
    for source_rule in recovered_sources:
        for reference in _references(source_rule, policy):
            contract = (policy.get("dependencies") or {}).get(reference["referenceKind"])
            if not contract:
                continue
            reference.update({"sourceRuleId": source_rule.get("ruleId"), "status": "unresolved"})
            chapter = _chapter_for(reference, chapters, contract)
            existing = _existing_definition(reference, rules + added_rules, contract, str(source_rule.get("ruleId") or ""))
            support = None if existing else _support(reference, narratives, contract, str(source_rule.get("recoverySourceId") or ""), chapter)
            if not chapter and (existing or support):
                chapter_id = "RECOVERED-" + hashlib.sha1(f"{reference['referenceKind']}|{reference['name']}".encode("utf-8")).hexdigest()[:10].upper()
                chapter = {
                    "chapterId": chapter_id, "system": next((item.get("system") for item in chapters if item.get("chapterId") == source_rule.get("ownerChapterId")), "规则闭环"),
                    "object": reference["name"], "title": reference["name"], "entityScope": [reference["name"]],
                    "chapterType": "settlement" if reference["referenceKind"] == "settlement" else "entity_mechanic",
                    "status": "approved", "confirmation": {"confirmed": True}, "recoveredMechanismChapter": True,
                }
                owner_index = next((index for index, item in enumerate(chapters) if item.get("chapterId") == source_rule.get("ownerChapterId")), len(chapters))
                chapters.insert(owner_index, chapter)
            if existing:
                reference.update({"status": "resolved", "targetChapterId": existing.get("ownerChapterId"), "definitionRuleId": existing.get("ruleId"), "resolution": "existing_approved_rule"})
            elif support and chapter:
                narrative, sentence = support
                digest = hashlib.sha1(f"{source_rule.get('ruleId')}|{reference['referenceKind']}|{sentence}".encode("utf-8")).hexdigest()[:12].upper()
                dependency_rule = {
                    "ruleId": f"RULE-DEP-{digest}", "subject": reference["name"], "behavior": sentence,
                    "intent": contract["intent"], "schemaSlot": contract["schemaSlot"], "ruleType": "flow",
                    "ownerChapterId": chapter.get("chapterId"), "reviewStatus": "approved", "semanticValidity": "valid",
                    "authorityStatus": "planner_confirmed", "inferenceLevel": "approved_dependency_recovery",
                    "recoverySourceId": narrative.get("narrativeId"), "dependencyOfRuleId": source_rule.get("ruleId"),
                    "evidenceLineage": {"sourceNarrativeId": narrative.get("narrativeId"), "sourceRuleId": source_rule.get("ruleId")},
                    "valueAuthority": narrative.get("valueAuthority"),
                }
                added_rules.append(dependency_rule)
                reference.update({"status": "resolved", "targetChapterId": chapter.get("chapterId"), "definitionRuleId": dependency_rule["ruleId"], "resolution": "approved_information_recovery"})
            else:
                reference["targetChapterId"] = chapter.get("chapterId") if chapter else None
                gap_id = "GAP-DEP-" + hashlib.sha1(f"{source_rule.get('ruleId')}|{reference['referenceKind']}|{reference['name']}".encode("utf-8")).hexdigest()[:12].upper()
                gaps.append({
                    "gapId": gap_id, "chapterId": reference.get("targetChapterId") or source_rule.get("ownerChapterId"),
                    "gapKind": "unresolved_mechanic_reference", "status": "reviewed_open", "gapDomain": "planning",
                    "applicabilityStatus": "applicable", "specificity": "concrete_decision",
                    "referencedByRuleId": source_rule.get("ruleId"), "referenceKind": reference["referenceKind"],
                    "referenceName": reference["name"],
                    "question": str(contract.get("gapQuestionTemplate") or "{name}在该条件成立时需要处于什么可验证状态？").format(name=reference["name"]),
                })
                if chapter:
                    reference["status"] = "gap_registered"
            references.append(reference)
    deduplicated = {}
    for reference in references:
        key = (reference["referenceKind"], _norm(reference["name"]))
        if key not in deduplicated or (deduplicated[key].get("status") == "unresolved" and reference.get("status") != "unresolved"):
            deduplicated[key] = reference
    references = list(deduplicated.values())
    gap_by_reference = {}
    for gap in gaps:
        key = (str(gap.get("referenceKind") or ""), _norm(gap.get("referenceName")))
        gap_by_reference.setdefault(key, gap)
    gaps = list(gap_by_reference.values())
    unresolved = [deepcopy(item) for item in references if item["status"] == "unresolved"]
    undefined = [deepcopy(item) for item in unresolved if not item.get("targetChapterId")]
    return {
        "chapters": chapters, "rules": added_rules, "gaps": gaps, "references": references,
        "unresolvedMechanicReferences": unresolved, "undefinedReferencedEntities": undefined,
        "policyStatus": "enabled",
    }
