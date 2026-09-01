"""Recover structured rule candidates from explicitly approved project information."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any


_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "planner_knowledge" / "approved-narrative-recovery-policies-v1.json"


def _policy() -> dict[str, Any]:
    return json.loads(_POLICY_PATH.read_text(encoding="utf-8"))


def _confirmed(item: dict[str, Any], *, allow_container_status: bool = False) -> bool:
    authority = _policy()["authority"]
    if str(item.get("reviewStatus") or item.get("status") or "") in set(authority["reviewStatuses"]):
        return True
    confirmation = item.get("confirmation") if isinstance(item.get("confirmation"), dict) else {}
    if confirmation.get("confirmed") is True:
        return True
    return allow_container_status and str(item.get("status") or "") in set(authority["directoryStatuses"])


def _text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [text for item in value for text in _text_values(item)]
    if isinstance(value, dict):
        return [text for item in value.values() for text in _text_values(item)]
    return []


def collect_approved_narratives(approved_data: dict[str, Any], chapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = [deepcopy(item) for item in approved_data.get("approvedNarratives") or [] if isinstance(item, dict)]
    directory = approved_data.get("directory") if isinstance(approved_data.get("directory"), dict) else {}
    if directory and _confirmed(directory, allow_container_status=True):
        understanding = directory.get("understanding") if isinstance(directory.get("understanding"), dict) else {}
        for field, value in understanding.items():
            if field in {"uncertainties", "unknowns"}:
                continue
            for index, text in enumerate(_text_values(value)):
                result.append({
                    "narrativeId": f"DIRECTORY-{field}-{index}", "sourceType": "confirmed_gameplay_overview",
                    "sourceField": f"directory.understanding.{field}", "text": text,
                    "reviewStatus": "confirmed", "confirmationRevision": directory.get("revision"),
                })
    for chapter in chapters:
        if not _confirmed(chapter):
            continue
        chapter_sources = {field: chapter.get(field) for field in ("plannerSummary", "summary", "basicFlow", "confirmedSummary")}
        planner_sections = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        for field in ("summary", "normalFlow", "keyRules"):
            chapter_sources[f"plannerSections.{field}"] = planner_sections.get(field)
        for field, value in chapter_sources.items():
            for index, text in enumerate(_text_values(value)):
                result.append({
                    "narrativeId": f"CHAPTER-{chapter.get('chapterId')}-{field}-{index}",
                    "sourceType": "confirmed_chapter_narrative", "sourceField": field,
                    "sourceChapterId": chapter.get("chapterId"), "text": text,
                    "reviewStatus": "confirmed", "confirmationRevision": (chapter.get("confirmation") or {}).get("revision"),
                })
    for fact in approved_data.get("facts") or []:
        if not isinstance(fact, dict) or not _confirmed(fact):
            continue
        text = str(fact.get("sourceText") or fact.get("object") or "").strip()
        if text:
            result.append({
                "narrativeId": str(fact.get("factId") or ""), "sourceType": "approved_atomic_fact",
                "sourceFactId": fact.get("factId"), "text": text, "reviewStatus": "confirmed",
                "confirmationRevision": fact.get("approvalRevision"),
            })
    return result


def recover_approved_information(
    approved_data: dict[str, Any], chapters: list[dict[str, Any]], *, lesson_registry=None,
) -> dict[str, Any]:
    if lesson_registry is None:
        from .system_lesson_registry import load_system_lesson_registry
        lesson_registry = load_system_lesson_registry()
    if not lesson_registry.is_policy_enabled(
        "recovery.approved_narrative", "approved_information_recovery"
    ):
        return {
            "rules": [], "rejectedUnreviewedSourceIds": [], "sourceCount": 0,
            "policyStatus": "disabled",
        }
    recovered: list[dict[str, Any]] = []
    rejected: list[str] = []
    semantic_rules = _policy().get("semanticRules") or []
    existing = {re.sub(r"[\s，。；：、,.!?！？()（）]", "", str(rule.get("behavior") or "")).casefold() for rule in approved_data.get("rules") or []}
    narratives = collect_approved_narratives(approved_data, chapters)
    for narrative in narratives:
        source_id = str(narrative.get("narrativeId") or "")
        if not _confirmed(narrative):
            rejected.append(source_id)
            continue
        for sentence in re.split(r"(?<=[。！？!?；;])|\n+", str(narrative.get("text") or "")):
            sentence = sentence.strip(" \t\r\n-•")
            sentence = re.sub(r"^\s*(?:\d+[.、]|[（(]?\d+[）)])\s*", "", sentence)
            if not sentence:
                continue
            normalized = re.sub(r"[\s，。；：、,.!?！？()（）]", "", sentence).casefold()
            if normalized in existing:
                continue
            semantic = next((item for item in semantic_rules if any(re.search(pattern, sentence) for pattern in item.get("patterns") or [])), None)
            if not semantic:
                continue
            responsibility = semantic["schemaSlot"]
            semantic_owner = next((
                chapter for chapter in chapters
                if responsibility in set(chapter.get("schemaResponsibilities") or [])
                or any(str(gap.get("schemaSlot") or "") == responsibility for gap in chapter.get("gaps") or [])
            ), None)
            owner_scope = list((semantic_owner or {}).get("entityScope") or [])
            subject = str(owner_scope[0] if owner_scope else (semantic_owner or {}).get("object") or semantic.get("subject") or "系统")
            digest = hashlib.sha1(f"{source_id}|{semantic['intent']}|{sentence}".encode("utf-8")).hexdigest()[:12].upper()
            recovered.append({
                "ruleId": f"RULE-REC-{digest}", "subject": subject,
                "behavior": sentence.rstrip("。") , "intent": semantic["intent"],
                "schemaSlot": semantic["schemaSlot"], "ruleType": "flow",
                "ownerChapterId": narrative.get("sourceChapterId") or (semantic_owner or {}).get("chapterId"), "reviewStatus": "approved",
                "semanticValidity": "valid", "authorityStatus": "planner_confirmed",
                "inferenceLevel": "approved_information_recovery", "recoverySourceId": source_id,
                "recoverySourceType": narrative.get("sourceType"), "recoverySourceField": narrative.get("sourceField"),
                "recoveryRevision": narrative.get("confirmationRevision"),
                "sourceFactIds": [narrative["sourceFactId"]] if narrative.get("sourceFactId") else [],
                "evidenceLineage": {"sourceNarrativeId": source_id, "sourceField": narrative.get("sourceField"), "revision": narrative.get("confirmationRevision")},
            })
            existing.add(normalized)
    return {
        "rules": recovered, "rejectedUnreviewedSourceIds": rejected,
        "sourceCount": len(narratives), "policyStatus": "enabled",
    }
