from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .gameplay_generation_quality import quality_report


def _match_score(chapter: dict[str, Any], target: dict[str, Any]) -> int:
    score = 0
    if chapter.get("systemName") and chapter.get("systemName") == target.get("systemName"):
        score += 3
    if chapter.get("subsystemName") and chapter.get("subsystemName") == target.get("subsystemName"):
        score += 4
    left, right = str(chapter.get("scope") or ""), str(target.get("scope") or "")
    score += sum(1 for char in set(left) if char.strip() and char in right)
    return score


def _contract(chapter: dict[str, Any]) -> dict[str, Any]:
    planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
    return {
        "normalFlowItems": len(planner.get("normalFlow") or []),
        "keyRuleItems": len(planner.get("keyRules") or []),
        "specialCaseItems": len(planner.get("specialCases") or []),
        "acceptanceItems": len(planner.get("acceptanceExamples") or chapter.get("acceptanceCases") or []),
        "usesParameters": bool(chapter.get("parameters") or chapter.get("parameterSchema")),
        "usesFormulae": bool(chapter.get("formulae")),
        "usesConfigurationSources": bool(chapter.get("configurationSources")),
    }


def find_quality_reference(jobs_root: Path, target: dict[str, Any]) -> dict[str, Any]:
    best: tuple[int, dict[str, Any]] | None = None
    for path in jobs_root.glob("*/job.json"):
        try:
            model = json.loads(path.read_text(encoding="utf-8")).get("gameplayReviewModel") or {}
        except (OSError, ValueError, TypeError):
            continue
        for chapter in model.get("chapters") or []:
            if not isinstance(chapter, dict) or not (chapter.get("confirmation") or {}).get("confirmed"):
                continue
            probe = dict(model)
            probe["chapters"] = [chapter]
            if not quality_report(probe, "details")["passed"]:
                continue
            candidate = (_match_score(chapter, target), _contract(chapter))
            if candidate[0] > 0 and (best is None or candidate[0] > best[0]):
                best = candidate
    return best[1] if best else {}
