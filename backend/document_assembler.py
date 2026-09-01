"""Chapter and final-document assembly over canonical structured planning data."""

from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from .planning_language_renderer import render_rule
from .rule_status import normalize_rule_status, status_visual_tone, strip_status_caveat


_SCHEMA_QUESTION_PATTERNS = (
    "核心规则是什么", "依次执行哪些", "读取哪项配置", "结果传递给哪个对象", "内容清单的核心规则是什么",
)

GROUPS = (
    ("逻辑规则", {"logic", "interaction", "flow"}),
    ("数值与配置", {"numeric", "config"}),
    ("表现规则", {"presentation"}),
)


def _normalized_text(value: Any) -> str:
    text = strip_status_caveat(value)
    return re.sub(r"[\s，。；：、,.!?！？:()（）\-—_]", "", text).casefold()


def _semantic_fingerprint(item: dict[str, Any]) -> str:
    key = str(item.get("semanticKey") or "").strip().casefold()
    if key:
        return f"key:{key}"
    text = _normalized_text(item.get("text"))
    if text:
        return f"text:{text}"
    rule_ids = [str(value) for value in item.get("sourceRuleIds") or [] if value]
    return "rule:" + "|".join(sorted(rule_ids))


def _merge_sentence(target: dict[str, Any], item: dict[str, Any]) -> None:
    for field in ("sourceRuleIds", "sourceFactIds", "evidenceIds", "ruleTypes", "schemaSlots"):
        target[field] = list(dict.fromkeys(list(target.get(field) or []) + list(item.get(field) or [])))
    tones = {str(target.get("visualTone") or "confirmed"), str(item.get("visualTone") or "confirmed")}
    if "conflict" in tones:
        target["visualTone"] = "conflict"
        target["knowledgeStatus"] = "CONFLICT"
    elif "inference" in tones:
        target["visualTone"] = "inference"
        if target.get("knowledgeStatus") == "CONFIRMED":
            target["knowledgeStatus"] = item.get("knowledgeStatus") or "INFERRED"


def _proposal_sentences(gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    seen: set[str] = set()
    for gap in gaps:
        proposal = strip_status_caveat(gap.get("proposal"))
        if not proposal:
            continue
        text = proposal.rstrip("。") + "。"
        fingerprint = _normalized_text(text)
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        result.append({
            "text": text,
            "sourceRuleIds": [],
            "sourceFactIds": list(gap.get("sourceFactIds") or []),
            "evidenceIds": list(gap.get("evidenceIds") or []),
            "ruleTypes": ["logic"],
            "schemaSlots": [gap.get("schemaSlot")],
            "semanticKey": str(gap.get("semanticKey") or f"proposal:{gap.get('gapId') or fingerprint}"),
            "knowledgeStatus": "PROPOSED",
            "visualTone": "inference",
        })
    return result


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
            fingerprint = _semantic_fingerprint(item)
            if fingerprint in seen:
                _merge_sentence(seen[fingerprint], item)
                continue
            seen[fingerprint] = item
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
    proposals = _proposal_sentences(gaps)
    if proposals:
        groups.append({"title": "策划补全", "sentences": proposals})
    return {**chapter, "groups": groups, "reviewedGaps": gaps}


def _flow_sentence(step: dict[str, Any]) -> dict[str, Any]:
    status = normalize_rule_status(step.get("knowledgeStatus"), inference_level=step.get("inferenceLevel"), source_type=step.get("sourceType"))
    return {
        "text": strip_status_caveat(step.get("text")).rstrip("。") + "。",
        "sourceRuleIds": list(step.get("sourceRuleIds") or ([step.get("ruleId")] if step.get("ruleId") else [])),
        "sourceFactIds": list(step.get("sourceFactIds") or []),
        "evidenceIds": list(step.get("evidenceIds") or []),
        "ruleTypes": ["logic"],
        "schemaSlots": [step.get("intent")],
        "semanticKey": str(step.get("semanticKey") or ""),
        "knowledgeStatus": status,
        "visualTone": status_visual_tone(status),
    }


def _candidate_summary_sentence(flow: dict[str, Any]) -> dict[str, Any] | None:
    text = strip_status_caveat(flow.get("candidateTypeSummary"))
    if not text:
        return None
    steps = list(flow.get("steps") or [])
    statuses = [normalize_rule_status(step.get("knowledgeStatus"), inference_level=step.get("inferenceLevel"), source_type=step.get("sourceType")) for step in steps]
    status = "CONFLICT" if "CONFLICT" in statuses else ("PROPOSED" if "PROPOSED" in statuses else ("INFERRED" if "INFERRED" in statuses else "CONFIRMED"))
    return {
        "text": text.rstrip("。") + "。",
        "sourceRuleIds": [step.get("ruleId") for step in steps if step.get("ruleId")],
        "sourceFactIds": list(dict.fromkeys(fid for step in steps for fid in step.get("sourceFactIds") or [])),
        "evidenceIds": list(dict.fromkeys(eid for step in steps for eid in step.get("evidenceIds") or [])),
        "ruleTypes": ["logic"],
        "schemaSlots": ["candidate_type"],
        "semanticKey": str(flow.get("candidateTypeSemanticKey") or ""),
        "knowledgeStatus": status,
        "visualTone": status_visual_tone(status),
    }


def build_final_document(approved_data: dict[str, Any], style_profile: dict[str, Any] | None = None, title: str = "执行策划案 B 版") -> dict[str, Any]:
    rules = [dict(rule) for rule in approved_data.get("rules", [])]
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
                proposals = _proposal_sentences(gaps)
                chapters.append({**chapter, "groups": ([{"title": "策划补全", "sentences": proposals}] if proposals else []), "reviewedGaps": gaps})
            else:
                chapters.append(assemble_chapter(chapter, rules, approved_data.get("gaps", []), style_profile))
            continue
        for flow_index, flow in enumerate(chapter_flows):
            sentences: list[dict[str, Any]] = []
            seen_flow: dict[str, dict[str, Any]] = {}
            summary = _candidate_summary_sentence(flow)
            steps = list(flow.get("steps") or [])
            summary_before = next((
                index for index, step in enumerate(steps)
                if step.get("semanticGroup") in {"selection", "effect", "state_exit", "refresh", "numeric_examples", "other"}
            ), len(steps))
            for index, step in enumerate(steps):
                if summary is not None and index == summary_before:
                    fingerprint = _semantic_fingerprint(summary)
                    if fingerprint not in seen_flow:
                        seen_flow[fingerprint] = summary
                        sentences.append(summary)
                sentence = _flow_sentence(step)
                fingerprint = _semantic_fingerprint(sentence)
                if fingerprint in seen_flow:
                    _merge_sentence(seen_flow[fingerprint], sentence)
                    continue
                seen_flow[fingerprint] = sentence
                sentences.append(sentence)
            if summary is not None and summary_before == len(steps):
                fingerprint = _semantic_fingerprint(summary)
                if fingerprint not in seen_flow:
                    sentences.append(summary)
            gaps = [
                gap for gap in approved_data.get("gaps", [])
                if flow_index == 0
                and gap.get("chapterId") in (flow.get("sourceChapterIds") or [chapter.get("chapterId")])
                and gap.get("specificity") == "concrete_decision"
                and gap.get("gapDomain", "planning") == "planning"
            ]
            proposals = _proposal_sentences(gaps)
            groups = []
            if sentences:
                groups.append({"title": "机制流程", "sentences": sentences})
            if proposals:
                groups.append({"title": "策划补全", "sentences": proposals})
            subject = str(flow.get("subject") or chapter.get("object") or "规则")
            reconstructed_title = subject if len(flow.get("sourceChapterIds") or []) > 1 else chapter.get("title")
            chapters.append({
                **chapter,
                "chapterId": f"{chapter.get('chapterId')}::{flow.get('mechanicId')}",
                "object": subject,
                "title": reconstructed_title,
                "groups": groups,
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
        "knowledgePolicy": "no_hidden_inference",
        "systems": [
            {"title": system, "objects": [{"title": obj, "chapters": items} for obj, items in objects.items()]}
            for system, objects in systems.items()
        ],
    }


def document_to_markdown(document: dict[str, Any]) -> str:
    """Plain Markdown fallback. Web/Feishu renderers should use visualTone for color."""
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
                questions = [gap for gap in chapter["reviewedGaps"] if not gap.get("proposal")]
                if questions:
                    lines += ["**待人工处理的冲突/缺口**", ""]
                    lines += [f"- {gap['question']}" for gap in questions]
                    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
