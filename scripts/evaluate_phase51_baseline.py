from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from backend.gve16_alignment_corpus import load_gve16_alignment_corpus
from backend.target_alignment_evaluator import evaluate_target_alignment


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts/planning-content-phase3-2026-08-17/phase-3-gap-result.json"
BLOCKS = ROOT / "artifacts/planning-content-phase4.3-2026-08-17/mechanism-role-blocks.json"
DELIVERY = ROOT / "artifacts/planning-content-phase5.1-2026-08-17/phase51-delivery.json"
VISUALS = ROOT / "artifacts/planning-content-phase5.1-2026-08-17/visual-blocks.json"
CORPUS = ROOT / "data/quality/gve16-alignment-corpus-v1.json"
LEGACY = ROOT / "artifacts/planning-content-baseline-2026-08-14/baseline_metrics.json"
DEFAULT_OUT = ROOT / "artifacts/planning-content-phase5.1-evaluation-2026-08-17"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _approved_rules(source: dict[str, Any]) -> list[dict[str, Any]]:
    rules = json.loads(json.dumps(source["rules"], ensure_ascii=False))
    for rule in rules:
        if rule.get("semanticValidity") == "valid":
            rule["reviewStatus"] = "approved"
    return rules


def _block_for_paragraph(paragraph: dict[str, Any], mechanism_blocks: list[dict[str, Any]]) -> str | None:
    rule_ids = set(paragraph.get("ruleIds", []))
    matches = [
        block["blockId"] for block in mechanism_blocks
        if rule_ids.intersection(block.get("ruleIds", []))
    ]
    return matches[0] if len(set(matches)) == 1 else None


def _paragraph_findings(delivery: dict[str, Any]) -> dict[str, list[str]]:
    annotations: dict[str, list[str]] = {}
    for chapter in delivery.get("chapters", []):
        body = [item for item in chapter.get("paragraphs", []) if item.get("kind") in {"execution_rule", "open_decision"}]
        for item in body:
            flags = annotations.setdefault(item["paragraphId"], [])
            if len(item.get("ruleIds", [])) == 1 and len(str(item.get("text") or "").strip()) < 16:
                flags.extend(["low-information single-body heading", "mechanism grouping issue"])
        for left, right in zip(body, body[1:]):
            if len(str(left.get("text") or "").strip()) < 16 and len(str(right.get("text") or "").strip()) < 16:
                annotations[left["paragraphId"]].append("short fragment")
                annotations[right["paragraphId"]].append("short fragment")
        by_block: dict[str, list[dict[str, Any]]] = {}
        for item in body:
            block = item.get("_mechanismBlockId")
            if block:
                by_block.setdefault(block, []).append(item)
        for items in by_block.values():
            if len({item.get("heading") for item in items}) > 1:
                for item in items:
                    annotations[item["paragraphId"]].extend(["over-split heading", "mechanism grouping issue"])
    return {key: sorted(set(value)) for key, value in annotations.items() if value}


def _annotated_chapters(delivery: dict[str, Any], mechanism_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    working = json.loads(json.dumps(delivery.get("chapters", []), ensure_ascii=False))
    for chapter in working:
        for paragraph in chapter.get("paragraphs", []):
            paragraph["_mechanismBlockId"] = _block_for_paragraph(paragraph, mechanism_blocks)
    annotations = _paragraph_findings({"chapters": working})
    result = []
    for chapter in working:
        result.append({
            "chapterId": chapter["chapterId"],
            "title": chapter["title"],
            "paragraphs": [{
                "paragraphId": item["paragraphId"],
                "text": item["text"],
                "supportingRuleIds": item.get("ruleIds", []),
                "mechanismBlockId": item.pop("_mechanismBlockId"),
                "carrierType": item.get("format"),
                "containsVisualBlockReference": bool(item.get("relatedVisualBlockIds")),
                "relatedVisualBlockIds": item.get("relatedVisualBlockIds", []),
                "evaluatorFindings": annotations.get(item["paragraphId"], []),
            } for item in chapter.get("paragraphs", [])],
        })
    return result


def _snapshot_markdown(delivery: dict[str, Any], annotated: list[dict[str, Any]], artifact_hash: str) -> str:
    lines = [
        "# Evaluated ExecutionDelivery Snapshot", "",
        f"- evaluatedArtifactHash: `{artifact_hash}`", "",
        delivery["markdown"].rstrip(), "", "---", "", "## Paragraph provenance and evaluator annotations", "",
    ]
    for chapter in annotated:
        lines += [f"### {chapter['title']}", ""]
        for item in chapter["paragraphs"]:
            lines += [
                f"#### {item['paragraphId']}", "",
                f"- supportingRuleIds: `{json.dumps(item['supportingRuleIds'], ensure_ascii=False)}`",
                f"- mechanismBlockId: `{item['mechanismBlockId']}`",
                f"- carrier type: `{item['carrierType']}`",
                f"- contains VisualBlock reference: `{str(item['containsVisualBlockReference']).lower()}`",
                f"- evaluator findings: `{json.dumps(item['evaluatorFindings'], ensure_ascii=False)}`", "",
                item["text"], "",
            ]
    return "\n".join(lines)


def _summary(report: dict[str, Any], legacy: dict[str, Any]) -> str:
    paradigm = report["paradigmAlignment"]
    completeness = report["executionCompleteness"]
    granularity = report["granularityReport"]["metrics"]
    lines = [
        "# Phase 5.1 Target Alignment Baseline", "",
        f"- Paradigm Alignment: **{paradigm['total']} / 100**",
        f"- Execution Completeness: **{completeness['total']} / 100**",
        f"- 80 分目标差值: **{report['targetDelta']}**",
        f"- minimum next-fix module: **{report['minimumNextFixModule']}**",
        f"- qualificationStatus: **{report['qualificationStatus']}**", "",
        "## Paradigm Alignment", "",
    ]
    for name, score in paradigm["dimensions"].items():
        lines.append(f"- {name}: {score}")
    lines += ["", "## Execution Completeness", ""]
    for name, score in completeness["dimensions"].items():
        lines.append(f"- {name}: {score}")
    lines += ["", "## Granularity Report", ""]
    for name, value in granularity.items():
        lines.append(f"- {name}: `{json.dumps(value, ensure_ascii=False)}`")
    lines += ["", "## Hard Gates", ""]
    for name, gate in report["hardGates"].items():
        lines.append(f"- {name}: {'PASS' if gate['passed'] else 'FAIL'}（observed={gate['observed']} expected={gate['expected']}）")
    lines += ["", "## Attributed Findings", ""]
    if report["attributedFindings"]:
        for item in report["attributedFindings"]:
            lines += [
                f"### {item['metric']}", "",
                f"- observed: `{json.dumps(item['observed'], ensure_ascii=False)}`",
                f"- reference: `{json.dumps(item['reference'], ensure_ascii=False)}`",
                f"- impact: {item['impact']}",
                f"- ownerLayer: {item['ownerLayer']}",
                f"- minimalFix: {item['minimalFix']}", "",
            ]
    else:
        lines.append("- 无扣分 finding。")
    lines += [
        "", "## Legacy evaluator 对照（不进入新评分）", "",
        f"- duplicateRate: {legacy['duplicateRate']}",
        f"- fillerRate: {legacy['fillerRate']}",
        f"- mixedLogicPresentationRate: {legacy['mixedLogicPresentationRate']}",
        f"- qualityScore: {legacy['qualityScore']}",
        "- classification: legacy false-negative baseline metrics",
        "- includedInNewScore: false", "",
    ]
    return "\n".join(lines)


def evaluate_baseline(output_dir: Path = DEFAULT_OUT) -> dict[str, Any]:
    new_score_sources = (SOURCE, BLOCKS, DELIVERY, VISUALS, CORPUS)
    before = {path: _sha(path) for path in (*new_score_sources, LEGACY)}
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    block_data = json.loads(BLOCKS.read_text(encoding="utf-8"))
    delivery = json.loads(DELIVERY.read_text(encoding="utf-8"))
    visual_blocks = json.loads(VISUALS.read_text(encoding="utf-8"))
    mechanism_blocks = [block for chapter in block_data["chapters"].values() for block in chapter["blocks"]]
    corpus = load_gve16_alignment_corpus(CORPUS)
    report = evaluate_target_alignment(
        delivery, mechanism_blocks, visual_blocks, _approved_rules(source), source["facts"], source["gaps"], [], corpus,
        qualification_evidence={"completeRuns": [], "blindRuns": []},
    )
    legacy_source = json.loads(LEGACY.read_text(encoding="utf-8"))
    legacy = {
        "classification": "legacy false-negative baseline metrics",
        "includedInNewScore": False,
        "duplicateRate": legacy_source["duplicateRate"],
        "fillerRate": legacy_source["fillerRate"],
        "mixedLogicPresentationRate": legacy_source["mixedLogicPresentationRate"],
        "qualityScore": legacy_source["qualityScores"]["detailQualityScore"],
        "newScoreInput": False,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    annotated = _annotated_chapters(delivery, mechanism_blocks)
    evaluated_snapshot = {
        "evaluatedArtifactHash": report["evaluatedArtifactHash"],
        "executionDelivery": delivery,
        "annotatedChapters": annotated,
    }
    (output_dir / "evaluated_delivery_snapshot.json").write_text(
        json.dumps(evaluated_snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "evaluated_delivery_snapshot.md").write_text(
        _snapshot_markdown(delivery, annotated, report["evaluatedArtifactHash"]), encoding="utf-8"
    )
    (output_dir / "target-alignment-report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "granularity-report.json").write_text(json.dumps(report["granularityReport"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "legacy-comparison.json").write_text(json.dumps(legacy, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "baseline-summary.md").write_text(_summary(report, legacy), encoding="utf-8")
    snapshot = {
        "paradigmAlignmentTotal": report["paradigmAlignment"]["total"],
        "paradigmDimensions": report["paradigmAlignment"]["dimensions"],
        "leadingFinding": report["attributedFindings"][0] if report["attributedFindings"] else None,
        "minimumNextFixModule": report["minimumNextFixModule"],
        "qualificationStatus": report["qualificationStatus"],
    }
    (output_dir / "explainability-snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    after = {path: _sha(path) for path in before}
    provenance = {
        "evaluatorVersion": report["evaluatorVersion"], "corpusVersion": report["corpusVersion"],
        "newScoreInputs": [str(path.relative_to(ROOT)) for path in new_score_sources],
        "legacyComparisonInput": str(LEGACY.relative_to(ROOT)),
        "legacyEvaluatorInputsUsedInNewScore": False,
        "sourceHashes": {str(path.relative_to(ROOT)): digest for path, digest in before.items()},
        "sourceFilesUnchanged": before == after,
        "modifiedBodyCount": 0, "modifiedP7Count": 0, "modifiedUiCount": 0,
        "modifiedRuleCount": 0, "modifiedGapCount": 0, "modifiedEntityGraphCount": 0,
        "parameterResolverInvoked": False,
    }
    (output_dir / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    result = evaluate_baseline()
    print(json.dumps({
        "paradigmAlignment": result["paradigmAlignment"],
        "executionCompleteness": result["executionCompleteness"],
        "targetDelta": result["targetDelta"],
        "minimumNextFixModule": result["minimumNextFixModule"],
        "qualificationStatus": result["qualificationStatus"],
    }, ensure_ascii=False, indent=2))
