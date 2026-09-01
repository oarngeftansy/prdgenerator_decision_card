"""Chapter and final-document assembly over approved structured planning data."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .planning_language_renderer import render_rule


_SCHEMA_QUESTION_PATTERNS = (
    "核心规则是什么", "依次执行哪些", "读取哪项配置", "结果传递给哪个对象", "内容清单的核心规则是什么",
)


GROUPS = (
    ("逻辑规则", {"logic", "interaction", "flow"}),
    ("数值与配置", {"numeric", "config"}),
    ("表现规则", {"presentation"}),
)


def assemble_chapter(chapter: dict[str, Any], rules: list[dict[str, Any]], reviewed_gaps: list[dict[str, Any]], style_profile: dict[str, Any] | None = None) -> dict[str, Any]:
    rendered = [render_rule(rule, style_profile) for rule in rules if rule.get("ownerChapterId") == chapter.get("chapterId")]
    rendered = [item for item in rendered if item["status"] == "rendered"]
    groups = []
    seen: dict[str, dict[str, Any]] = {}
    for title, types in GROUPS:
        sentences = []
        for item in rendered:
            if not (set(item["ruleTypes"]) & types):
                continue
            key = item["text"].rstrip("。；")
            if key in seen:
                target = seen[key]
                for field in ("sourceRuleIds", "sourceFactIds", "evidenceIds", "ruleTypes", "schemaSlots"):
                    target[field] = list(dict.fromkeys(target[field] + item[field]))
                continue
            seen[key] = item
            sentences.append(item)
        if sentences:
            groups.append({"title": title, "sentences": sentences})
    gaps = [
        gap for gap in reviewed_gaps
        if gap.get("chapterId") == chapter.get("chapterId")
        and gap.get("status") in {"reviewed_open", "open"}
        and gap.get("gapDomain", "planning") == "planning"
        and gap.get("applicabilityStatus", "applicable") == "applicable"
        and gap.get("specificity") == "concrete_decision"
        and not any(pattern in str(gap.get("question") or "") for pattern in _SCHEMA_QUESTION_PATTERNS)
    ]
    return {**chapter, "groups": groups, "reviewedGaps": gaps}


def build_final_document(approved_data: dict[str, Any], style_profile: dict[str, Any] | None = None, title: str = "执行策划案 B 版") -> dict[str, Any]:
    rules = [dict(rule) for rule in approved_data.get("rules", [])]
    # A condition-only fact is not publishable by itself. If an approved flow rule
    # already contains that exact condition, merge provenance into the complete rule.
    consumed: set[str] = set()
    for condition in rules:
        behavior = str(condition.get("behavior") or "")
        if condition.get("ruleType") != "logic" or not behavior.endswith(("归零", "为0", "为 0")):
            continue
        for complete in rules:
            if complete.get("ruleType") == "flow" and behavior in str(complete.get("behavior") or ""):
                complete.setdefault("mergedSourceRuleIds", []).append(condition["ruleId"])
                complete.setdefault("mergedSourceFactIds", []).extend(condition.get("sourceFactIds") or [])
                consumed.add(condition["ruleId"])
                break
    rules = [rule for rule in rules if rule.get("ruleId") not in consumed]
    flows_by_chapter: dict[str, list[dict[str, Any]]] = defaultdict(list)
    reconstructed_source_chapters: set[str] = set()
    for flow in approved_data.get("mechanicFlows") or []:
        flows_by_chapter[str(flow.get("chapterId") or "")].append(flow)
        reconstructed_source_chapters.update(str(item) for item in (flow.get("sourceChapterIds") or [flow.get("chapterId")]) if item)
    chapters = []
    reconstructed_mode = bool(flows_by_chapter)
    for chapter in approved_data.get("chapters", []):
        chapter_flows = flows_by_chapter.get(str(chapter.get("chapterId") or ""), [])
        if not chapter_flows:
            if reconstructed_mode:
                gaps = [
                    gap for gap in approved_data.get("gaps", [])
                    if str(chapter.get("chapterId") or "") not in reconstructed_source_chapters
                    and gap.get("chapterId") == chapter.get("chapterId")
                    and gap.get("specificity") == "concrete_decision"
                    and gap.get("gapDomain", "planning") == "planning"
                ]
                chapters.append({**chapter, "groups": [], "reviewedGaps": gaps})
            else:
                chapters.append(assemble_chapter(chapter, rules, approved_data.get("gaps", []), style_profile))
            continue
        for flow_index, flow in enumerate(chapter_flows):
            sentences = []
            candidate_summary = None
            if flow.get("candidateTypeSummary"):
                candidate_summary = {
                    "text": flow["candidateTypeSummary"],
                    "sourceRuleIds": [step.get("ruleId") for step in flow.get("steps") or [] if step.get("ruleId")],
                    "sourceFactIds": list(dict.fromkeys(fid for step in flow.get("steps") or [] for fid in step.get("sourceFactIds") or [])),
                    "evidenceIds": list(dict.fromkeys(eid for step in flow.get("steps") or [] for eid in step.get("evidenceIds") or [])),
                    "ruleTypes": ["logic"], "schemaSlots": ["candidate_type"],
                }
            steps = list(flow.get("steps") or [])
            summary_before = next((
                index for index, step in enumerate(steps)
                if step.get("semanticGroup") in {"selection", "effect", "state_exit", "refresh", "numeric_examples", "other"}
            ), len(steps))
            for index, step in enumerate(steps):
                if candidate_summary is not None and index == summary_before:
                    sentences.append(candidate_summary)
                sentences.append({
                    "text": str(step.get("text") or "").rstrip("。") + "。",
                    "sourceRuleIds": list(step.get("sourceRuleIds") or ([step.get("ruleId")] if step.get("ruleId") else [])),
                    "sourceFactIds": list(step.get("sourceFactIds") or []),
                    "evidenceIds": list(step.get("evidenceIds") or []),
                    "ruleTypes": ["logic"], "schemaSlots": [step.get("intent")],
                })
            if candidate_summary is not None and summary_before == len(steps):
                sentences.append(candidate_summary)
            gaps = [
                gap for gap in approved_data.get("gaps", [])
                if flow_index == 0
                and gap.get("chapterId") in (flow.get("sourceChapterIds") or [chapter.get("chapterId")])
                and gap.get("specificity") == "concrete_decision"
                and gap.get("gapDomain", "planning") == "planning"
            ]
            subject = str(flow.get("subject") or chapter.get("object") or "规则")
            reconstructed_title = subject if len(flow.get("sourceChapterIds") or []) > 1 else chapter.get("title")
            chapters.append({
                **chapter,
                "chapterId": f"{chapter.get('chapterId')}::{flow.get('mechanicId')}",
                "object": subject,
                "title": reconstructed_title,
                "groups": [{"title": "机制流程", "sentences": sentences}] if sentences else [],
                "reviewedGaps": gaps,
            })
    chapters = [ch for ch in chapters if ch["groups"] or ch["reviewedGaps"]]
    systems: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for chapter in chapters:
        chapter["foldIntoObject"] = chapter.get("title") == chapter.get("object")
        systems[chapter.get("system") or "未分类"][chapter.get("object") or "通用"].append(chapter)
    return {
        "title": title,
        "status": "reference_preview_with_open_gaps",
        "systems": [{"title": system, "objects": [{"title": obj, "chapters": items} for obj, items in objects.items()]} for system, objects in systems.items()],
    }


def document_to_markdown(document: dict[str, Any]) -> str:
    lines = [f"# {document['title']}", ""]
    for system in document["systems"]:
        lines += [f"## {system['title']}", ""]
        for obj in system["objects"]:
            lines += [f"### {obj['title']}", ""]
            for chapter in obj["chapters"]:
                if not chapter.get("foldIntoObject"):
                    lines += [f"#### {chapter['title']}", ""]
                for group in chapter["groups"]:
                    if len(chapter["groups"]) > 1:
                        lines += [f"**{group['title']}**", ""]
                    lines += [f"- {sentence['text']}" for sentence in group["sentences"]]
                    lines.append("")
                proposals = [gap for gap in chapter["reviewedGaps"] if gap.get("displayMode") == "proposal" and gap.get("proposal")]
                questions = [gap for gap in chapter["reviewedGaps"] if gap not in proposals]
                if proposals:
                    lines += ["**策划建议（待确认）**", ""]
                    lines += [f"- {gap['proposal'].rstrip('。')}。" for gap in proposals]
                    lines.append("")
                if questions:
                    lines += ["**待确认**", ""]
                    lines += [f"- {gap['question']}" for gap in questions]
                    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
