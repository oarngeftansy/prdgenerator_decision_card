from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Iterable

from backend.feishu_language_quality import language_quality_report, rule_carrier, three_reader_report
from backend.gameplay_generation_quality import quality_report
from backend.gameplay_render import GameplayRenderError, render_gameplay_document_sections


_RULE_FIELDS = ("normalFlow", "keyRules", "specialCases")
_FILLER = re.compile(
    r"(?:本节主要|本部分主要|该设计旨在|为了|从而|帮助玩家|使玩家能够|"
    r"进一步提升|有助于|这样可以|便于玩家|增强体验|提升沉浸感|"
    r"玩家可以通过操作(?:来)?(?:控制|进行|完成)|界面(?:会|将)?显示相关内容|"
    r"系统(?:会|将)?进行相应处理|该功能用于提供相关功能)"
)
_TAG = re.compile(r"<[^>]+>")
_SENTENCE_BREAK = re.compile(r"[。！？!?\n]+")


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(_json_bytes(value))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(text: str) -> str:
    return re.sub(r"[\s，。；：、,.!?！？（）()\-—]", "", text).casefold()


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        text = value.strip()
        if text:
            yield text
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _rule_candidates(model: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        planner = chapter.get("plannerSections") if isinstance(chapter.get("plannerSections"), dict) else {}
        for field in _RULE_FIELDS:
            result.extend(_strings(planner.get(field)))
        result.extend(_strings(chapter.get("rules")))
    return result


def _gap_count(model: dict[str, Any]) -> int:
    count = 0
    for chapter in model.get("chapters") or []:
        if not isinstance(chapter, dict):
            continue
        count += len([item for item in chapter.get("unknowns") or [] if item])
        count += len([
            item for item in chapter.get("decisionCards") or []
            if isinstance(item, dict) and item.get("status") not in {"resolved", "approved", "rejected"}
        ])
    count += len([
        item for item in (model.get("reviewState") or {}).get("findings") or []
        if isinstance(item, dict) and item.get("status") != "resolved"
    ])
    return count


def _plain_text(xml: str) -> str:
    with_breaks = re.sub(r"</(?:p|li|h[1-6])>", "\n", xml, flags=re.IGNORECASE)
    return html.unescape(_TAG.sub("", with_breaks)).strip()


def _render_p7(job: dict[str, Any]) -> tuple[str, str, list[str]]:
    working = copy.deepcopy(job)
    try:
        rendered = render_gameplay_document_sections(working)
        return rendered.body_xml, "current_confirmed_render", []
    except GameplayRenderError as error:
        codes = [str(item) for item in error.args[0]] if error.args and isinstance(error.args[0], list) else [str(error)]
        if "GAMEPLAY_DIRECTORY_NOT_CONFIRMED" not in codes:
            raise
        model = working.get("gameplayReviewModel") or {}
        directory = model.get("directory") if isinstance(model.get("directory"), dict) else {}
        directory["status"] = "confirmed"
        rendered = render_gameplay_document_sections(working)
        return rendered.body_xml, "in_memory_directory_gate_override", codes


def _quality_scores(model: dict[str, Any]) -> dict[str, Any]:
    detail = quality_report(copy.deepcopy(model), "detail")
    language = language_quality_report(copy.deepcopy(model))
    readers = three_reader_report(copy.deepcopy(model))
    return {
        "detailQualityScore": detail.get("score", 0),
        "detailQualityPassed": bool(detail.get("passed")),
        "detailQualityErrorCount": len(detail.get("errors") or []),
        "languageQualityPassed": bool(language.get("passed")),
        "languageFindingCount": len(language.get("findings") or []),
        "threeReaderPassed": bool(readers.get("passed")),
        "threeReaderMissing": readers.get("missing") or [],
    }


def freeze_baseline(job_path: Path, output_dir: Path) -> dict[str, Any]:
    job_path = job_path.resolve()
    output_dir = output_dir.resolve()
    source_before = _sha256(job_path)
    job = json.loads(job_path.read_text(encoding="utf-8"))
    model = copy.deepcopy(job.get("gameplayReviewModel") or {})
    directory = copy.deepcopy(model.get("directory") or {})
    p7_xml, p7_mode, anomalies = _render_p7(job)
    p7_text = _plain_text(p7_xml)
    sentences = [item.strip() for item in _SENTENCE_BREAK.split(p7_text) if item.strip()]
    candidates = _rule_candidates(model)
    normalized = [_normalized(item) for item in candidates if _normalized(item)]
    duplicate_count = len(normalized) - len(set(normalized))
    filler_count = sum(bool(_FILLER.search(sentence)) for sentence in sentences)
    mixed_count = sum(rule_carrier(item) == "mixed" for item in candidates)
    metrics = {
        "jobId": str(job.get("id") or model.get("jobId") or ""),
        "revision": int(model.get("revision") or 0),
        "chapterCount": len([item for item in model.get("chapters") or [] if isinstance(item, dict)]),
        "bodySentenceCount": len(sentences),
        "ruleCandidateCount": len(candidates),
        "duplicateRate": round(duplicate_count / len(normalized), 4) if normalized else 0.0,
        "fillerRate": round(filler_count / len(sentences), 4) if sentences else 0.0,
        "mixedLogicPresentationRate": round(mixed_count / len(candidates), 4) if candidates else 0.0,
        "gapCount": _gap_count(model),
        "qualityScores": _quality_scores(model),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "baseline_metrics.json", metrics)
    _write_json(output_dir / "gameplay_directory.json", directory)
    _write_json(output_dir / "p4_gameplay_review_model.json", model)
    (output_dir / "p7_body.xml").write_text(p7_xml + "\n", encoding="utf-8")
    (output_dir / "p7_body.txt").write_text(p7_text + "\n", encoding="utf-8")

    source_after = _sha256(job_path)
    manifest = {
        "jobId": metrics["jobId"],
        "revision": metrics["revision"],
        "sourceJob": str(job_path),
        "sourceJobSha256Before": source_before,
        "sourceJobSha256After": source_after,
        "sourceUnchanged": source_before == source_after,
        "p7SnapshotMode": p7_mode,
        "anomalies": anomalies,
        "outputs": {},
    }
    for name in (
        "baseline_metrics.json", "gameplay_directory.json", "p4_gameplay_review_model.json",
        "p7_body.xml", "p7_body.txt",
    ):
        manifest["outputs"][name] = {"sha256": _sha256(output_dir / name)}
    _write_json(output_dir / "manifest.json", manifest)
    if source_before != source_after:
        raise RuntimeError("source job changed while freezing baseline")
    return metrics


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze a read-only planning-content A baseline.")
    parser.add_argument("job", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    metrics = freeze_baseline(args.job, args.output)
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
