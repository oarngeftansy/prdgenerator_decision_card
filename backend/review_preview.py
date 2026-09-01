from __future__ import annotations

from pathlib import Path
import re
from typing import Any
from xml.etree import ElementTree as ET

from .planning_model import compile_confirmed_planning_model
from .review_model import review_gate
from .gameplay_review_model import gameplay_gate
from .gameplay_render import GameplayRenderError
from .granularity_audit import granularity_audit_report
from .feishu_language_quality import language_quality_report
from .sample_alignment import sample_alignment_report
from .delivery_alignment import delivery_alignment_report
from .stage3_quality_gate import stage3_quality_gate_report


def repair_utf8_mojibake(value: str) -> str:
    """Repair UTF-8 bytes decoded as Latin-1 while preserving valid Unicode."""
    def repair_run(match: re.Match[str]) -> str:
        run = match.group(0)
        try:
            return run.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            return run
    previous = str(value or "")
    for _ in range(2):
        repaired = re.sub(r"[\x80-\xff]{2,}", repair_run, previous)
        if repaired == previous:
            break
        previous = repaired
    return previous


def build_completion_snapshot(job: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    """Return the sole completion source consumed by every P7 indicator."""
    interaction = job.get("reviewModel") or {}
    gameplay = job.get("gameplayReviewModel") or {}
    chapters = [item for item in gameplay.get("chapters") or [] if isinstance(item, dict)]
    stages = [item for item in interaction.get("stages") or [] if isinstance(item, dict)]
    active_tables = [item for item in gameplay.get("tables") or [] if isinstance(item, dict) and item.get("status") != "deleted"]
    active_diagrams = [item for item in gameplay.get("diagrams") or [] if isinstance(item, dict) and item.get("status") != "deleted"]
    parameter_count = sum(len(item.get("parameterSchema") or []) for item in chapters)
    no_diagram_ids = set((gameplay.get("diagramReview") or {}).get("noDiagramChapterIds") or [])
    cards = [card for chapter in chapters for card in chapter.get("decisionCards") or [] if isinstance(card, dict)]
    pending_cards = [card for card in cards if card.get("status", "pending") not in {"resolved", "skipped"}]
    interaction_revision = interaction.get("revision")
    gameplay_revision = gameplay.get("revision")
    interaction_preview_current = interaction.get("reviewState", {}).get("previewRevision") == interaction_revision
    planning_board_ready = bool(stages) and interaction_preview_current and bool(preview.get("planningBoardPreviewSvg"))
    tables_done = all(item.get("status") == "reviewed" for item in active_tables) and (bool(active_tables) or parameter_count == 0)
    diagrams_done = all(item.get("status") == "reviewed" for item in active_diagrams) if active_diagrams else bool(chapters) and all(item.get("id") in no_diagram_ids for item in chapters)
    checks = [
        {"id": "language", "label": "语言与表述", "detail": "已通过" if (preview.get("languageAudit") or {}).get("passed") is True else "未通过", "done": (preview.get("languageAudit") or {}).get("passed") is True},
        {"id": "granularity", "label": "内容颗粒度", "detail": "已通过" if (preview.get("granularityAudit") or {}).get("passed") is True else "未通过", "done": (preview.get("granularityAudit") or {}).get("passed") is True},
        {"id": "directory", "label": "玩法目录", "detail": f"{len(chapters)} 节", "done": bool(chapters)},
        {"id": "interaction", "label": "交互审核", "detail": f"{sum(bool(item.get('confirmation', {}).get('confirmed')) for item in stages)}/{len(stages)} 环节", "done": bool(stages) and all(item.get("confirmation", {}).get("confirmed") for item in stages)},
        {"id": "planning_board", "label": "策划草图", "detail": "当前版本" if planning_board_ready else "缺失或版本过期", "done": planning_board_ready},
        {"id": "rules", "label": "规则审核", "detail": f"{sum(bool(item.get('confirmation', {}).get('confirmed')) for item in chapters)}/{len(chapters)}", "done": bool(chapters) and all(item.get("confirmation", {}).get("confirmed") for item in chapters)},
        {"id": "diagrams", "label": "图解审核", "detail": f"{len(active_diagrams)} 张" if active_diagrams else "无需图解", "done": diagrams_done},
        {"id": "tables", "label": "参数审核", "detail": f"{len(active_tables)} 张表" if active_tables else "无适用参数", "done": tables_done},
        {"id": "decisions", "label": "策划决策", "detail": f"{len(pending_cards)} 项未处理" if pending_cards else "已处理", "done": not pending_cards},
        {"id": "delivery", "label": "交付一致性", "detail": "已通过" if (preview.get("deliveryAlignment") or {}).get("passed") is True else "未通过", "done": (preview.get("deliveryAlignment") or {}).get("passed") is True},
    ]
    completed = sum(item["done"] for item in checks)
    percent = round(completed * 100 / len(checks)) if checks else 0
    ready = not preview.get("blockerIds") and all(item["done"] for item in checks)
    if ready:
        percent = 100
    elif percent >= 100:
        percent = 99
    steps = [
        {"id": "understanding", "label": "AI理解", "done": bool((gameplay.get("directory") or {}).get("understanding"))},
        {"id": "directory", "label": "玩法目录", "done": next(item["done"] for item in checks if item["id"] == "directory")},
        {"id": "interaction", "label": "交互审核", "done": next(item["done"] for item in checks if item["id"] == "interaction")},
        {"id": "rules", "label": "规则审核", "done": next(item["done"] for item in checks if item["id"] == "rules")},
        {"id": "diagrams", "label": "图解审核", "done": diagrams_done},
        {"id": "tables", "label": "参数审核", "done": tables_done},
        {"id": "export", "label": "文档导出", "done": ready},
    ]
    return {
        "ready": ready,
        "percent": percent,
        "completed": completed,
        "total": len(checks),
        "checks": checks,
        "steps": steps,
        "blockerIds": list(preview.get("blockerIds") or []),
        "interactionRevision": interaction_revision,
        "gameplayRevision": gameplay_revision,
    }


def build_review_preview(job: dict[str, Any], job_dir: Path | None = None) -> dict[str, Any]:
    model = job["reviewModel"]
    gate = review_gate(model)
    planning = compile_confirmed_planning_model(job)
    frame_ids: list[str] = []
    for stage in sorted(model.get("stages") or [], key=lambda item: item.get("order", 0)):
        if not stage.get("confirmation", {}).get("confirmed"):
            continue
        for item in stage.get("representativeFrames") or []:
            if item.get("frameId") and item["frameId"] not in frame_ids:
                frame_ids.append(item["frameId"])
    job["planningModel"] = planning
    board_svg = ""
    media_blockers: list[str] = []
    if job_dir is not None:
        from .feishu_render import render_ue_board_svg
        frame_map = {item.get("id"): item for item in job.get("frames") or []}
        for frame_id in frame_ids:
            frame = frame_map.get(frame_id) or {}
            relative = Path(str(frame.get("imagePath") or f"frames/{frame_id}.jpg"))
            if relative.is_absolute() or ".." in relative.parts or not (job_dir / relative).is_file() or not (job_dir / relative).read_bytes():
                media_blockers.append(f"MEDIA_{frame_id}")
        if not media_blockers:
            board_svg, _ = render_ue_board_svg(job, job_dir)
            board_svg = repair_utf8_mojibake(board_svg)
    boards = model.get("referenceBoards") if isinstance(model.get("referenceBoards"), dict) else {}
    def board_summary(key: str, asset_count: int = 0) -> dict[str, Any]:
        board = boards.get(key) if isinstance(boards.get(key), dict) else {}
        assets = board.get("assets") if isinstance(board.get("assets"), list) else []
        missing_count = sum(isinstance(asset, dict) and asset.get("status") == "missing" for asset in assets)
        return {"key": key, "assetCount": asset_count if key == "planning" else len(assets), "missingCount": missing_count, "status": "missing" if missing_count else board.get("status", "generated" if key == "planning" else "pending")}
    preview = {
        "revision": model["revision"], "exportReady": gate["exportReady"] and not media_blockers, "blockerIds": [*gate["blockers"], *media_blockers],
        "warningIds": gate["warnings"], "representativeFrameIds": frame_ids, "planningModel": planning,
        "boardPreviewSvg": board_svg,
        "referenceBoardSummary": [board_summary("planning", len(frame_ids))],
    }
    if preview["exportReady"]:
        model["reviewState"]["previewRevision"] = model["revision"]
    else:
        model["reviewState"]["previewRevision"] = None
    return preview


def build_final_review_preview(job: dict[str, Any], job_dir: Path | None = None) -> dict[str, Any]:
    interaction = job.get("reviewModel") or {}
    gameplay = job.get("gameplayReviewModel") or {}
    interaction_revision = interaction.get("revision")
    gameplay_revision = gameplay.get("revision")
    interaction_gate = review_gate(interaction)
    gameplay_result = gameplay_gate(gameplay, interaction)
    blockers = [*interaction_gate["blockers"], *gameplay_result["blockers"]]
    projection = gameplay.get("ruleIntelligenceProjection")
    if isinstance(projection, dict) and projection.get("authorityMode") == "structured_rules":
        guard = projection.get("guard") or {}
        publication = projection.get("publication") or {}
        if not guard.get("passed"):
            blockers.append("STRUCTURED_RULE_GUARD_FAILED")
        if any(
            chapter.get("publicationEligibility") == "blocked"
            for chapter in publication.get("chapters") or []
            if isinstance(chapter, dict)
        ):
            blockers.append("STRUCTURED_SCHEMA_CLOSURE_INCOMPLETE")
    stage3_quality = stage3_quality_gate_report(gameplay)
    granularity = stage3_quality["granularityAudit"]
    language = stage3_quality["languageAudit"]
    alignment = stage3_quality["sampleAlignment"]
    blockers.extend(stage3_quality["blockers"])
    depth_blockers = [
        item for item in gameplay_result["blockers"]
        if any(marker in str(item) for marker in (
            "GAMEPLAY_DEPTH_INSUFFICIENT", "RULES_MISSING", "VERIFICATION_MISSING",
            "BOUNDARY_OR_CONFIGURATION_MISSING", "FORMULA_DEFINITION_MISSING", "DRAW_RULE_MISSING",
        ))
    ]
    if depth_blockers:
        granularity = dict(granularity)
        granularity["passed"] = False
        findings = list(granularity.get("findings") or [])
        findings.append({
            "chapterId": "all",
            "axis": "implementation-depth",
            "message": "部分章节尚未达到可制作、可配置、可验证的样例颗粒度。",
            "blockerIds": depth_blockers,
        })
        granularity["findings"] = findings
    delivery_alignment = delivery_alignment_report(job)
    if not delivery_alignment["passed"]:
        blockers.append("P7_FEISHU_CONTENT_MISMATCH")
    if interaction.get("reviewState", {}).get("previewRevision") != interaction_revision:
        blockers.append("INTERACTION_PREVIEW_STALE")
    rendered = None
    planning_board_svg = ""
    try:
        if job_dir is None:
            raise ValueError("job directory is required")
        from .feishu_render import render_feishu_document

        rendered = render_feishu_document(job, job_dir)
        shared_board_svgs = dict(rendered.preview_board_svgs)
        planning_board_svg = repair_utf8_mojibake(shared_board_svgs.get("planning", ""))
        if not planning_board_svg:
            blockers.append("PLANNING_BOARD_MISSING")
        if [board.key for board in rendered.native_boards] != ["planning"]:
            raise ValueError("combined delivery requires the planning board only")
        expected = 1 + rendered.embedded_whiteboard_count
        if rendered.xml.count('<whiteboard type="blank"></whiteboard>') != expected:
            raise ValueError("combined delivery requires blank placeholders for every whiteboard")
        if len(re.findall(r"<whiteboard\b", rendered.xml)) != expected:
            raise ValueError("combined whiteboard count mismatch")
        if re.search(r"<!DOCTYPE|<!ENTITY", rendered.xml, re.I):
            raise ValueError("document XML declarations are not allowed")
        ET.fromstring(f"<document>{rendered.xml}</document>")
    except GameplayRenderError as exc:
        blockers.extend(exc.blocker_ids)
    except (ET.ParseError, OSError, TypeError, ValueError):
        blockers.append("COMBINED_DOCUMENT_INVALID")
    preview = {
        "interactionRevision": interaction_revision,
        "gameplayRevision": gameplay_revision,
        "directoryRevision": (gameplay.get("directory") or {}).get("revision"),
        "exportReady": not blockers,
        "blockerIds": list(dict.fromkeys(blockers)),
        "warningIds": list(dict.fromkeys([*interaction_gate["warnings"], *gameplay_result["warnings"]])),
        "granularityAudit": granularity,
        "languageAudit": language,
        "sampleAlignment": alignment,
        "deliveryAlignment": delivery_alignment,
        "planningBoardPreviewSvg": planning_board_svg,
        "documentOrder": [dict(item) for item in rendered.preview_order] if rendered is not None and "COMBINED_DOCUMENT_INVALID" not in blockers else [],
        "deliveryPreviewHtml": _delivery_preview_html(rendered) if rendered is not None and "COMBINED_DOCUMENT_INVALID" not in blockers else "",
    }
    preview["completionSnapshot"] = build_completion_snapshot(job, preview)
    preview["exportReady"] = preview["completionSnapshot"]["ready"]
    gameplay.setdefault("reviewState", {})["previewRevision"] = gameplay_revision if preview["exportReady"] else None
    return preview


def _delivery_preview_html(rendered: Any) -> str:
    """Render the exact Feishu payload locally, replacing board slots with the same SVG payloads."""
    html = re.sub(r"<title>.*?</title>", "", rendered.xml, count=1, flags=re.S)
    board_svgs = [svg for _, svg in rendered.preview_board_svgs]
    board_svgs.extend(svg for _, svg in rendered.embedded_whiteboards)
    iterator = iter(board_svgs)

    def replace_board(_: re.Match[str]) -> str:
        svg = next(iterator, "")
        return f'<div class="final-document-gameplay-diagram final-document-shared-board">{svg}</div>'

    html = re.sub(r"<whiteboard\b[^>]*>\s*</whiteboard>", replace_board, html)
    evidence = {item.frame_id: item for item in getattr(rendered, "evidence_images", ())}

    def replace_inline_image(match: re.Match[str]) -> str:
        frame_id, caption = match.group(1), match.group(2)
        item = evidence.get(frame_id)
        if item is None:
            return ""
        # Evidence paths live below the current job directory.  The public
        # artifact URL is already carried by the frame id in this application.
        job_id = item.path.parent.parent.name
        relative = item.path.relative_to(item.path.parent.parent).as_posix()
        return (
            '<figure class="final-document-inline-figure">'
            f'<img class="final-document-inline-image" src="/artifacts/{job_id}/{relative}" alt="{caption}" loading="lazy">'
            f'<figcaption class="final-document-inline-caption">{caption}</figcaption></figure>'
        )

    html = re.sub(
        r'<img\s+name="inline-figure-([^"]+)"\s+caption="([^"]*)"(?:\s+path="[^"]*")?\s*/>',
        replace_inline_image, html,
    )
    html = re.sub(r"<li\s+seq=\"auto\">", "<li>", html)
    # Feishu understands native table tags, while the local browser preview
    # needs explicit classes and an overflow wrapper. This decorates the exact
    # same cells without changing the published XML payload or its order.
    html = re.sub(r"<table>", '<div class="final-document-table-scroll"><table class="final-document-table final-document-delivery-table">', html)
    html = re.sub(r"</table>", "</table></div>", html)
    return html
