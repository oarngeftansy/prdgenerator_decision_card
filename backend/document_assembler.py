"""Chapter and final-document assembly over canonical structured planning data."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from .planning_language_renderer import render_rule
from .publication_state import decorate_publication_item, normalize_publication_state


_SCHEMA_QUESTION_PATTERNS = (
    "核心规则是什么", "依次执行哪些", "读取哪项配置", "结果传递给哪个对象", "内容清单的核心规则是什么",
)

GROUPS = (
    ("逻辑规则", {"logic", "interaction", "flow"}),
    ("数值与配置", {"numeric", "config"}),
    ("表现规则", {"presentation"}),
)


def _sentence(text: str, *, state: str = "confirmed", source_rule_ids: list[str] | None = None,
              source_fact_ids: list[str] | None = None, evidence_ids: list[str] | None = None,
              rule_types: list[str] | None = None, schema_slots: list[str] | None = None) -> dict[str, Any]:
    text = str(text or "").strip()
    if text and text[-1] not in "。！？；":
        text += "。"
    return decorate_publication_item({
        "text": text,
        "sourceRuleIds": list(dict.fromkeys(source_rule_ids or [])),
        "sourceFactIds": list(dict.fromkeys(source_fact_ids or [])),
        "evidenceIds": list(dict.fromkeys(evidence_ids or [])),
        "ruleTypes": list(dict.fromkeys(rule_types or [])),
        "schemaSlots": list(dict.fromkeys(schema_slots or [])),
        "publicationState": state,
    })


def _publishable_gap(gap: dict[str, Any]) -> bool:
    return (
        gap.get("chapterId")
        and gap.get("gapDomain", "planning") == "planning"
        and gap.get("applicabilityStatus", "applicable") == "applicable"
        and gap.get("specificity") == "concrete_decision"
        and not any(pattern in str(gap.get("question") or "") for pattern in _SCHEMA_QUESTION_PATTERNS)
    )


def _gap_sentence(gap: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a resolved planner decision into normal Final copy.

    Proposal/inference provenance is structural. We intentionally do not prefix the
    sentence with labels such as “策划建议/推断/待确认”. Unresolved questions are not
    Final content; they belong to diagnostics/review telemetry.
    """
    text = str(gap.get("proposal") or gap.get("resolvedValue") or gap.get("decision") or "").strip()
    if not text:
        return None
    state = normalize_publication_state(gap, default="proposed")
    if state == "confirmed" and gap.get("displayMode") == "proposal":
        state = "proposed"
    return _sentence(
        text,
        state=state,
        source_rule_ids=list(gap.get("sourceRuleIds") or []),
        source_fact_ids=list(gap.get("sourceFactIds") or []),
        evidence_ids=list(gap.get("evidenceIds") or []),
        rule_types=[str(gap.get("ruleType") or "logic")],
        schema_slots=[str(gap.get("schemaSlot") or "planner_completion")],
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
                states = {target.get("publicationState"), item.get("publicationState")}
                if "conflict" in states:
                    target.update(decorate_publication_item(target | {"publicationState": "conflict"}))
                elif states & {"inferred", "proposed"}:
                    merged_state = "proposed" if "proposed" in states else "inferred"
                    target.update(decorate_publication_item(target | {"publicationState": merged_state}))
                continue
            seen[key] = item
            sentences.append(item)
        if sentences:
            groups.append({"title": title, "sentences": sentences})

    completions = []
    unresolved = []
    for gap in reviewed_gaps:
        if gap.get("chapterId") != chapter.get("chapterId") or not _publishable_gap(gap):
            continue
        item = _gap_sentence(gap)
        if item:
            key = item["text"].rstrip("。；")
            if key not in seen:
                seen[key] = item
                completions.append(item)
        else:
            unresolved.append(gap)
    if completions:
        groups.append({"title": "补全规则", "sentences": completions})
    return {**chapter, "groups": groups, "reviewedGaps": [], "unresolvedDiagnostics": unresolved}


def _flow_summary(flow: dict[str, Any]) -> str:
    """Read only generic summaries; never privilege one sample mechanic family."""
    for key in ("flowSummary", "mechanicSummary", "summary"):
        value = str(flow.get(key) or "").strip()
        if value:
            return value
    return ""


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
    unresolved_diagnostics: list[dict[str, Any]] = []
    reconstructed_mode = bool(flows_by_chapter)
    for chapter in approved_data.get("chapters", []):
        chapter_flows = flows_by_chapter.get(str(chapter.get("chapterId") or ""), [])
        if not chapter_flows:
            if reconstructed_mode:
                completions = []
                for gap in approved_data.get("gaps", []):
                    if str(chapter.get("chapterId") or "") in reconstructed_source_chapters:
                        continue
                    if gap.get("chapterId") != chapter.get("chapterId") or not _publishable_gap(gap):
                        continue
                    item = _gap_sentence(gap)
                    if item:
                        completions.append(item)
                    else:
                        unresolved_diagnostics.append(gap)
                if completions:
                    chapters.append({**chapter, "groups": [{"title": "补全规则", "sentences": completions}], "reviewedGaps": []})
            else:
                assembled = assemble_chapter(chapter, rules, approved_data.get("gaps", []), style_profile)
                unresolved_diagnostics.extend(assembled.pop("unresolvedDiagnostics", []))
                chapters.append(assembled)
            continue

        for flow_index, flow in enumerate(chapter_flows):
            flow_state = normalize_publication_state(flow)
            sentences = []
            summary = _flow_summary(flow)
            if summary:
                sentences.append(_sentence(
                    summary,
                    state=flow_state,
                    source_rule_ids=[step.get("ruleId") for step in flow.get("steps") or [] if step.get("ruleId")],
                    source_fact_ids=[fid for step in flow.get("steps") or [] for fid in step.get("sourceFactIds") or []],
                    evidence_ids=[eid for step in flow.get("steps") or [] for eid in step.get("evidenceIds") or []],
                    rule_types=["logic"],
                    schema_slots=["mechanic_summary"],
                ))
            for step in flow.get("steps") or []:
                text = str(step.get("text") or "").strip()
                if not text:
                    continue
                sentences.append(_sentence(
                    text,
                    state=normalize_publication_state(step, default=flow_state),
                    source_rule_ids=list(step.get("sourceRuleIds") or ([step.get("ruleId")] if step.get("ruleId") else [])),
                    source_fact_ids=list(step.get("sourceFactIds") or []),
                    evidence_ids=list(step.get("evidenceIds") or []),
                    rule_types=[str(step.get("ruleType") or "logic")],
                    schema_slots=[str(step.get("intent") or step.get("schemaSlot") or "mechanic_step")],
                ))

            completions = []
            if flow_index == 0:
                for gap in approved_data.get("gaps", []):
                    if gap.get("chapterId") not in (flow.get("sourceChapterIds") or [chapter.get("chapterId")]) or not _publishable_gap(gap):
                        continue
                    item = _gap_sentence(gap)
                    if item:
                        completions.append(item)
                    else:
                        unresolved_diagnostics.append(gap)
            subject = str(flow.get("subject") or flow.get("mechanism") or chapter.get("object") or "规则")
            reconstructed_title = subject if len(flow.get("sourceChapterIds") or []) > 1 else chapter.get("title")
            groups = [{"title": "机制流程", "sentences": sentences}] if sentences else []
            if completions:
                groups.append({"title": "补全规则", "sentences": completions})
            chapters.append({
                **chapter,
                "chapterId": f"{chapter.get('chapterId')}::{flow.get('mechanicId') or flow_index + 1}",
                "object": subject,
                "title": reconstructed_title,
                "groups": groups,
                "reviewedGaps": [],
            })

    chapters = [ch for ch in chapters if ch["groups"]]
    systems: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for chapter in chapters:
        chapter["foldIntoObject"] = chapter.get("title") == chapter.get("object")
        systems[chapter.get("system") or "未分类"][chapter.get("object") or "通用"].append(chapter)
    return {
        "title": title,
        "status": "publication_ready" if not unresolved_diagnostics else "publication_ready_with_diagnostics",
        "systems": [{"title": system, "objects": [{"title": obj, "chapters": items} for obj, items in objects.items()]} for system, objects in systems.items()],
        "unresolvedDiagnostics": unresolved_diagnostics,
    }


def document_to_markdown(document: dict[str, Any]) -> str:
    """Plain markdown fallback; rich renderers preserve publication-state highlight."""
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
                    lines += [f"- {sentence['text']}" for sentence in group["sentences"] if sentence.get("text")]
                    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
