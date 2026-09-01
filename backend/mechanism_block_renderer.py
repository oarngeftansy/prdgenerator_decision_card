"""Render MechanismBlocks using abstract organization rules only."""

from __future__ import annotations

from typing import Any


ROLE_ORDER = (
    "definition", "input_constraint", "trigger", "condition", "target_selection",
    "processing", "effect", "state_change", "result", "exit_boundary",
)


def _finish(text: str) -> str:
    text = text.strip().rstrip("。；")
    return text + "。" if text else ""


def _stitch(entries: list[dict[str, Any]], omit_subject: bool) -> tuple[str, list[str]]:
    slots = [entry.get("schemaSlot") for entry in entries]
    raw_texts = [str(entry.get("text") or "").strip().rstrip("。；") for entry in entries]
    if len(entries) >= 2 and slots[:2] == ["selection_pause", "random_trigger"] and raw_texts[:2] == ["系统升级触发时暂停游戏", "三选一升级触发时生成三张候选卡"]:
        first_ids = [entries[0]["ruleId"], entries[1]["ruleId"]]
        prefix = "升级触发后，暂停战斗并生成三张候选卡"
        rest, rest_ids = _stitch(entries[2:], omit_subject)
        text = prefix + ("；" + rest.rstrip("。") if rest else "")
        return _finish(text), list(dict.fromkeys(first_ids + rest_ids))
    if len(entries) == 2 and slots == ["refresh_rule", "refresh_rule"]:
        if entries[0].get("ruleType") == "interaction" and raw_texts == ["玩家点击刷新按钮", "三选一刷新后替换当前三项候选"]:
            return "玩家点击刷新按钮后，替换当前三项候选。", [entries[0]["ruleId"], entries[1]["ruleId"]]
    clauses = []
    rule_ids = []
    context_subject = None
    for entry in entries:
        text = _controlled_clause(entry)
        subject = str(entry.get("subject") or "").strip()
        if omit_subject and context_subject and subject == context_subject and text.startswith(subject):
            text = text[len(subject):]
        if not context_subject and subject:
            context_subject = subject
        if text:
            clauses.append(text)
            if entry.get("ruleId") not in rule_ids:
                rule_ids.append(entry["ruleId"])
    return _finish("；".join(clauses)), rule_ids


def _controlled_clause(entry: dict[str, Any]) -> str:
    """Syntax-only variants selected by SchemaSlot, never by reference prose."""
    text = str(entry.get("text") or "").strip().rstrip("。；")
    slot = entry.get("schemaSlot")
    if slot == "selection_pause" and text == "系统升级触发时暂停游戏":
        return "升级触发后，暂停战斗"
    if slot == "random_trigger" and text == "三选一升级触发时生成三张候选卡":
        return "生成三张候选卡"
    if slot == "candidate_effect" and text == "已选武器选择后改变攻击方式":
        return "选择武器后，改变所选武器的攻击方式"
    if slot == "refresh_rule" and text == "三选一刷新后替换当前三项候选":
        return "刷新后，替换当前三项候选"
    return text


def _confirmed(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in entries if entry.get("resolutionStatus", "executable") != "unresolved_dependency"]


def _section(entries: list[dict[str, Any]], carrier: str, heading: str, omit_subject: bool) -> dict[str, Any] | None:
    entries = _confirmed(entries)
    if not entries:
        return None
    rule_ids = list(dict.fromkeys(entry["ruleId"] for entry in entries))
    roles = [entry.get("semanticRole") or carrier for entry in entries]
    slots = [entry.get("schemaSlot") for entry in entries]
    tight_chain = heading in {"自动索敌", "候选流程", "刷新处理"}
    if heading == "自动索敌" and len(entries) == 3 and roles == ["input_constraint", "target_selection", "processing"]:
        clauses = []
        subject = None
        for entry in entries:
            text = _controlled_clause(entry)
            current = entry.get("subject")
            if subject and current == subject and text.startswith(str(current)):
                text = text[len(str(current)):]
            subject = subject or current
            clauses.append(text)
        text = f"{clauses[0]}，{clauses[1]}，并{clauses[2]}。"
        return {"carrier": carrier, "format": "sentence", "text": text, "items": [], "ruleIds": rule_ids}
    if heading == "候选流程" and slots[:2] == ["random_trigger", "selection_pause"]:
        tail = entries[2:]
        tail_text, tail_ids = _stitch(tail, omit_subject)
        text = "升级触发后，暂停战斗并生成三张候选卡" + ("；" + tail_text.rstrip("。") if tail_text else "")
        return {"carrier": carrier, "format": "sentence", "text": _finish(text), "items": [], "ruleIds": list(dict.fromkeys(rule_ids[:2] + tail_ids))}
    raw_texts = [str(entry.get("text") or "").strip().rstrip("。；") for entry in entries]
    if slots[:2] == ["selection_pause", "random_trigger"] and raw_texts[:2] == ["系统升级触发时暂停游戏", "三选一升级触发时生成三张候选卡"]:
        text, ids = _stitch(entries, omit_subject)
        return {"carrier": carrier, "format": "sentence", "text": text, "items": [], "ruleIds": ids}
    if tight_chain and slots[:2] == ["refresh_rule", "refresh_rule"]:
        text, ids = _stitch(entries, omit_subject)
        return {"carrier": carrier, "format": "sentence", "text": text, "items": [], "ruleIds": ids}
    if len(entries) == 1:
        return {"carrier": carrier, "format": "sentence", "text": _finish(_controlled_clause(entries[0])), "items": [], "ruleIds": rule_ids}
    items = [{"text": _finish(_controlled_clause(entry)), "ruleIds": [entry["ruleId"]]} for entry in entries]
    return {"carrier": carrier, "format": "bullets", "text": "", "items": items, "ruleIds": rule_ids}


def render_mechanism_block(block: dict[str, Any], style_profile: dict[str, Any]) -> dict[str, Any]:
    """Render a block; raw reference content is intentionally outside the read contract."""
    if block.get("status") == "evidence_insufficient":
        return {
            "blockId": block.get("blockId"), "heading": block.get("mechanismSemantic"),
            "status": "evidence_insufficient", "paragraphs": [],
            "openDecisionSummary": [],
            "unabsorbedGapIds": list(block.get("unabsorbedGapIds") or []),
            "unsupportedSemanticAdditionCount": 0,
        }

    organization = style_profile.get("organization_rules") or {}
    omit_subject = organization.get("contextual_subject_omission", True)
    paragraphs = []
    role_order = ROLE_ORDER
    if block.get("mechanismSemantic") == "候选流程":
        role_order = ("definition", "trigger", "condition", "state_change", "input_constraint", "target_selection", "processing", "effect", "result", "exit_boundary")
    elif block.get("mechanismSemantic") == "移动方式":
        role_order = ("definition", "trigger", "condition", "processing", "input_constraint", "target_selection", "effect", "state_change", "result", "exit_boundary")
    mechanism_entries = [entry for role in role_order for entry in block.get(role, [])]
    for section in (
        _section(mechanism_entries, "mechanism", block.get("mechanismSemantic", ""), omit_subject),
        _section(list(block.get("config_reference") or []), "config_reference", block.get("mechanismSemantic", ""), omit_subject),
        _section(list(block.get("presentation") or []), "presentation", block.get("mechanismSemantic", ""), omit_subject),
    ):
        if section:
            paragraphs.append(section)
    unresolved_entries = [entry for role in ROLE_ORDER + ("config_reference", "presentation") for entry in block.get(role, []) if entry.get("resolutionStatus") == "unresolved_dependency"]
    open_decisions = [{"text": entry["text"], "ruleIds": [entry["ruleId"]], "semanticRole": entry.get("semanticRole")} for entry in unresolved_entries]
    unsupported = sum(1 for paragraph in paragraphs if not paragraph["ruleIds"])
    return {
        "blockId": block.get("blockId"), "heading": block.get("mechanismSemantic"),
        "status": block.get("status"), "paragraphs": paragraphs,
        "openDecisionSummary": open_decisions,
        "unabsorbedGapIds": list(block.get("unabsorbedGapIds") or []),
        "unsupportedSemanticAdditionCount": unsupported,
        "usedOrganizationRules": [
            "chapter_internal_grouping", "heading_granularity", "bullet_density", "rule_stitching",
            "contextual_subject_omission", "mechanism_semantic_subheading", "definition_before_detail",
            "lifecycle_after_main_behavior",
        ],
    }
