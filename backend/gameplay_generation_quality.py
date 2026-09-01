from __future__ import annotations

import copy
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

from .lead_planner_gate import lead_planner_output_audit
from .granularity_audit import granularity_audit_report, mechanism_closure_report
from .gameplay_flow_semantics import flow_chain_report


class GameplayGenerationQualityError(ValueError):
    pass


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_fingerprint(job: dict[str, Any], job_dir: Path, *, model: str, prompt_version: str, structure: Any = None) -> str:
    evidence = []
    for index, frame in enumerate(job.get("frames") or []):
        if not isinstance(frame, dict):
            continue
        frame_id = str(frame.get("id") or f"frame-{index + 1}")
        candidates = [job_dir / "frames" / f"{frame_id}.jpg", job_dir / "frames" / Path(str(frame.get("imageUrl") or "")).name]
        path = next((item for item in candidates if item.is_file()), None)
        evidence.append({
            "order": index,
            "sha256": _file_digest(path) if path else None,
            "source": None if path else str(frame.get("imageUrl") or frame_id),
        })
    videos = []
    for key in ("videoPath", "primaryVideoPath", "auxiliaryVideoPath"):
        raw = job.get(key)
        if not raw:
            continue
        path = Path(str(raw))
        if not path.is_absolute():
            path = job_dir / path
        videos.append({"key": key, "sha256": _file_digest(path) if path.is_file() else None})
    payload = {
        "jobIdentity": str(job.get("id") or ""),
        "interactionRevision": (
            (job.get("interactionModel") or {}).get("revision")
            or (job.get("reviewModel") or {}).get("revision")
        ),
        "approvedGameplayRevision": (job.get("gameplayReviewModel") or {}).get("revision"),
        "evidence": evidence,
        "videos": videos,
        "model": model,
        "promptVersion": prompt_version,
        "structure": structure,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_cached_response(cache_root: Path, fingerprint: str) -> Any | None:
    path = cache_root / f"{fingerprint}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))["response"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


def save_cached_response(cache_root: Path, fingerprint: str, response: Any) -> None:
    cache_root.mkdir(parents=True, exist_ok=True)
    target = cache_root / f"{fingerprint}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps({"response": response}, ensure_ascii=False), encoding="utf-8")
    temporary.replace(target)


def remove_cached_response(cache_root: Path, fingerprint: str) -> None:
    """Remove one reproducible response after semantic validation rejects its batch."""
    try:
        (cache_root / f"{fingerprint}.json").unlink(missing_ok=True)
    except OSError:
        pass


def prune_cached_responses(cache_root: Path, *, max_age_seconds: int = 7 * 24 * 60 * 60, now: float | None = None) -> list[Path]:
    """Delete only expired, reproducible generation responses."""
    if not cache_root.is_dir():
        return []
    cutoff = (time.time() if now is None else now) - max_age_seconds
    removed: list[Path] = []
    for path in cache_root.glob("*.json"):
        try:
            if path.stat().st_mtime >= cutoff:
                continue
            path.unlink()
            removed.append(path)
        except OSError:
            continue
    return removed


def preserve_planner_decisions(
    existing: dict[str, Any],
    candidate: dict[str, Any],
    *,
    refresh_confirmed_content: bool = False,
) -> dict[str, Any]:
    result = copy.deepcopy(candidate)
    if (existing.get("directory") or {}).get("status") == "confirmed":
        result["directory"] = copy.deepcopy(existing["directory"])
    existing_chapters = {item.get("id"): item for item in existing.get("chapters") or [] if isinstance(item, dict) and item.get("id")}
    for index, chapter in enumerate(result.get("chapters") or []):
        previous = existing_chapters.get(chapter.get("id"))
        if not previous:
            continue
        is_confirmed = bool((previous.get("confirmation") or {}).get("confirmed"))
        if is_confirmed and not refresh_confirmed_content:
            result["chapters"][index] = copy.deepcopy(previous)
            continue
        for field in previous.get("humanEditedFields") or []:
            if field in previous:
                chapter[field] = copy.deepcopy(previous[field])
        if previous.get("summarySource") == "planner":
            chapter["plannerSummary"] = copy.deepcopy(previous.get("plannerSummary"))
            chapter["summarySource"] = "planner"
        if is_confirmed:
            chapter["status"] = copy.deepcopy(previous.get("status") or "approved")
            chapter["confirmation"] = copy.deepcopy(previous["confirmation"])
    if refresh_confirmed_content and (existing.get("directory") or {}).get("status") == "confirmed":
        refreshed = {item.get("id"): item for item in result.get("chapters") or [] if isinstance(item, dict)}
        previous_chapters = {item.get("id"): item for item in existing.get("chapters") or [] if isinstance(item, dict)}
        for entry in (result.get("directory") or {}).get("entries") or []:
            chapter_id = entry.get("chapterId")
            chapter = refreshed.get(chapter_id)
            previous = previous_chapters.get(chapter_id) or {}
            planner_owned = previous.get("summarySource") == "planner" or "plannerSummary" in (previous.get("humanEditedFields") or [])
            if not chapter or planner_owned:
                continue
            summary = ((chapter.get("plannerSections") or {}).get("summary") or chapter.get("plannerSummary") or "").strip()
            if summary:
                entry["summary"] = summary
    return result


def quality_report(
    model: dict[str, Any],
    phase: str,
    references: list[dict[str, Any]] | None = None,
    *,
    allow_pending_decisions: bool = False,
) -> dict[str, Any]:
    errors = lead_planner_output_audit(
        model,
        phase,
        allow_pending_decisions=allow_pending_decisions,
    )
    if phase == "structure":
        score = max(0, 100 - 20 * len(errors))
        return {"score": score, "threshold": 90, "passed": not errors and score >= 90, "errors": errors}

    granularity = granularity_audit_report(model)
    closure = mechanism_closure_report(model)
    for finding in granularity.get("findings") or []:
        if not isinstance(finding, dict):
            continue
        chapter_id = str(finding.get("chapterId") or "model")
        code = str(finding.get("code") or "GRANULARITY_FAILED")
        errors.append(f"{chapter_id}:{code}")
    chapters = [item for item in model.get("chapters") or [] if isinstance(item, dict)]
    chapter_scores = []
    parameterized = {
        "formula", "progression", "random_pool", "economy_reward",
        "level_wave", "buff_chain", "statistics_feedback",
    }
    required_parameter_fields = {
        "name", "plannerMeaning", "type", "unit", "defaultValue", "range",
        "configurationSource", "rounding", "evidenceLevel",
    }
    required_formula_fields = {"name", "expression", "calculationOrder", "rounding", "evidenceLevel"}
    density_fields = {
        "normalFlowItems": "normalFlow", "keyRuleItems": "keyRules",
        "specialCaseItems": "specialCases", "acceptanceItems": "acceptanceExamples",
    }

    def pending_decision_covers(chapter: dict[str, Any], kind: str) -> bool:
        markers = ("参数", "数值", "配置") if kind == "parameter" else ("公式", "计算关系", "计算公式")
        for card in chapter.get("decisionCards") or []:
            if not isinstance(card, dict) or card.get("status") != "pending":
                continue
            text = " ".join([
                str(card.get("question") or ""),
                *[str(item) for item in card.get("impacts") or []],
            ])
            if any(marker in text for marker in markers):
                return True
        return False

    def reviewable_pending_cards(chapter: dict[str, Any]) -> list[dict[str, Any]]:
        if not allow_pending_decisions:
            return []
        return [
            card for card in chapter.get("decisionCards") or []
            if isinstance(card, dict)
            and card.get("status") == "pending"
            and str(card.get("question") or "").strip()
            and len([
                option for option in card.get("options") or []
                if isinstance(option, dict)
                and str(option.get("id") or "").strip()
                and str(option.get("label") or "").strip()
            ]) >= 2
        ]

    for chapter_index, chapter in enumerate(chapters):
        mechanism = chapter.get("mechanism") if isinstance(chapter.get("mechanism"), dict) else {}
        planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        mechanism_rules = [value for key, value in mechanism.items() if key not in {"type", "name", "description"} and value not in (None, "", [], {})]
        normal = planner.get("normalFlow") or planner.get("keyRules") or mechanism_rules
        special = planner.get("specialCases") or chapter.get("unknowns")
        acceptance = planner.get("acceptanceExamples") or chapter.get("acceptanceCases")
        pending_cards = reviewable_pending_cards(chapter)
        pending_gap = bool(pending_cards)
        pending_parameter_decision = allow_pending_decisions and pending_decision_covers(chapter, "parameter")
        pending_formula_decision = allow_pending_decisions and pending_decision_covers(chapter, "formula")
        parameters = (
            chapter.get("parameters") or chapter.get("parameterSchema") or chapter.get("formulae")
            or chapter.get("configurationSources") or pending_parameter_decision or pending_formula_decision
        )
        evidence = chapter.get("sourceFrameIds") or chapter.get("evidenceClaims") or chapter.get("inlineEvidence")
        score = 0
        score += 10 if chapter.get("scope") else 0
        score += 20 if normal else 0
        score += 15 if normal and (special or acceptance or pending_gap) else (8 if normal else 0)
        score += 15 if parameters or mechanism.get("type") not in parameterized else 0
        score += 10 if chapter.get("dependencies") or len(chapters) == 1 else 5
        score += 10 if acceptance or pending_gap else 0
        score += 10 if evidence else 0
        chapter_errors = [item for item in errors if str(item).startswith(str(chapter.get("id") or "") + ":")]
        flow_report = flow_chain_report(chapter)
        for flow_error in flow_report["errors"]:
            error = f"{chapter.get('id') or 'chapter'}:FLOW_CHAIN_{flow_error}"
            errors.append(error)
            chapter_errors.append(error)
        reference = references[chapter_index] if references and chapter_index < len(references) else {}
        for reference_field, planner_field in density_fields.items():
            expected = int(reference.get(reference_field) or 0)
            actual = len(planner.get(planner_field) or [])
            minimum = math.ceil(expected * 0.75)
            # A quality reference describes the density of a previously approved
            # chapter, not facts that exist in the current evidence.  At review
            # entry an explicit decision card is the correct carrier for the
            # missing rule; forcing the reference density here would either make
            # the model invent prose or reject the whole project for being honest.
            if minimum and actual < minimum and not pending_gap:
                error = f"{chapter.get('id') or 'chapter'}:REFERENCE_DENSITY_{planner_field}_{actual}_OF_{minimum}"
                errors.append(error)
                chapter_errors.append(error)
        mechanism_type = str(mechanism.get("type") or "custom")
        if mechanism_type in parameterized:
            schema = chapter.get("parameterSchema") if isinstance(chapter.get("parameterSchema"), list) else []
            if not schema and not pending_parameter_decision:
                error = f"{chapter.get('id') or 'chapter'}:PARAMETER_SCHEMA_MISSING"
                errors.append(error)
                chapter_errors.append(error)
            for row_index, row in enumerate(schema, 1):
                missing = sorted(required_parameter_fields - set(row)) if isinstance(row, dict) else sorted(required_parameter_fields)
                has_evidence = isinstance(row, dict) and bool(row.get("sourceFrameIds") or row.get("referenceSource"))
                if missing or not has_evidence:
                    suffix = ",".join(missing + ([] if has_evidence else ["evidenceSource"]))
                    error = f"{chapter.get('id') or 'chapter'}:PARAMETER_ROW_{row_index}_MISSING_{suffix}"
                    errors.append(error)
                    chapter_errors.append(error)
        formulae = chapter.get("formulae") if isinstance(chapter.get("formulae"), list) else []
        if mechanism_type == "formula" and not formulae and not pending_formula_decision:
            error = f"{chapter.get('id') or 'chapter'}:FORMULA_MODULE_MISSING"
            errors.append(error)
            chapter_errors.append(error)
        for row_index, row in enumerate(formulae, 1):
            missing = sorted(required_formula_fields - set(row)) if isinstance(row, dict) else sorted(required_formula_fields)
            has_evidence = isinstance(row, dict) and bool(row.get("sourceFrameIds") or row.get("referenceSource"))
            if missing or not has_evidence:
                suffix = ",".join(missing + ([] if has_evidence else ["evidenceSource"]))
                error = f"{chapter.get('id') or 'chapter'}:FORMULA_ROW_{row_index}_MISSING_{suffix}"
                errors.append(error)
                chapter_errors.append(error)
        schema = chapter.get("parameterSchema") if isinstance(chapter.get("parameterSchema"), list) else []
        all_values_known = bool(schema) and all(
            isinstance(row, dict) and row.get("defaultValue") not in (None, "")
            and not any(word in str(row.get("defaultValue")).casefold() for word in ("待", "unknown", "pending"))
            for row in schema
        )
        if formulae and all_values_known and not chapter.get("workedExamples"):
            error = f"{chapter.get('id') or 'chapter'}:WORKED_EXAMPLE_MISSING"
            errors.append(error)
            chapter_errors.append(error)
        score += 10 if not chapter_errors else 0
        chapter_scores.append({"chapterId": chapter.get("id"), "score": score})
        if score < 90:
            errors.append(f"{chapter.get('id') or 'chapter'}:QUALITY_SCORE_{score}")
    total = round(sum(item["score"] for item in chapter_scores) / len(chapter_scores)) if chapter_scores else 0
    report = {"score": total, "threshold": 90, "passed": bool(chapters) and not errors and total >= 90, "errors": list(dict.fromkeys(errors)), "chapters": chapter_scores, "granularity": granularity, "mechanismClosure": closure}
    if allow_pending_decisions:
        report["mode"] = "review_entry"
    return report


def require_quality_floor(
    model: dict[str, Any],
    phase: str,
    references: list[dict[str, Any]] | None = None,
    *,
    allow_pending_decisions: bool = False,
) -> dict[str, Any]:
    report = quality_report(model, phase, references=references, allow_pending_decisions=allow_pending_decisions)
    model["structureQuality" if phase == "structure" else "detailQuality"] = copy.deepcopy(report)
    model["generationQuality"] = report
    if not report["passed"]:
        raise GameplayGenerationQualityError("generation quality floor failed: " + "; ".join(report["errors"][:20]))
    return model
