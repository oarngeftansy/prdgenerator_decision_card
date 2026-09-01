"""Read-only style linting; findings never change or supply planning content."""

from __future__ import annotations

from typing import Any


def lint_document(document: dict[str, Any], style_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    forbidden = (style_profile or {}).get("forbidden_expressions", [])
    findings = []
    sentence_count = 0
    for system in document.get("systems", []):
        for obj in system.get("objects", []):
            for chapter in obj.get("chapters", []):
                if chapter.get("title") == chapter.get("object") and not chapter.get("foldIntoObject"):
                    findings.append({"code": "parent_child_same_title", "chapterId": chapter.get("chapterId")})
                for group in chapter.get("groups", []):
                    for sentence in group.get("sentences", []):
                        sentence_count += 1
                        for phrase in forbidden:
                            if phrase and phrase in sentence.get("text", ""):
                                findings.append({"code": "forbidden_expression", "sentenceId": sentence.get("sentenceId"), "value": phrase})
                        if not sentence.get("sourceRuleIds"):
                            findings.append({"code": "missing_rule_trace", "sentenceId": sentence.get("sentenceId")})
                        types = set(sentence.get("ruleTypes", []))
                        if "presentation" in types and len(types) > 1:
                            findings.append({"code": "mixed_logic_presentation", "sentenceId": sentence.get("sentenceId")})
    return {"sentenceCount": sentence_count, "findingCount": len(findings), "pass": not findings, "findings": findings}

