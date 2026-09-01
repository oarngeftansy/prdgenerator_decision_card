"""Export a language-only Final Delivery Candidate v3 from frozen v2 artifacts."""

from __future__ import annotations

from copy import deepcopy
import difflib
import hashlib
import json
from pathlib import Path
from typing import Any

from backend.document_assembler import document_to_markdown
from backend.planning_language_polish import polish_final_document


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "artifacts" / "yilu-kuangbiao-final-delivery-candidate-v2-2026-08-24"
OUTPUT = ROOT / "artifacts" / "yilu-kuangbiao-final-delivery-candidate-v3-2026-08-24"
DELIVERY_TITLE = "《一路狂飙》玩法策划执行案｜Final Delivery Candidate v3 / Planner Review Ready"
_VISIBLE_TEXT_FIELDS = {"text", "proposal", "question"}


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _clean_markdown(value: str) -> str:
    return "\n".join(line.rstrip() for line in value.splitlines()) + "\n"


def _without_visible_text(value: Any, field: str = "") -> Any:
    if field in _VISIBLE_TEXT_FIELDS:
        return "<VISIBLE_TEXT>"
    if isinstance(value, dict):
        return {key: _without_visible_text(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [_without_visible_text(item) for item in value]
    return value


def build_v3_artifacts(source: Path, output: Path, *, delivery_title: str = DELIVERY_TITLE) -> dict[str, Any]:
    document = json.loads((source / "result-a-final.json").read_text(encoding="utf-8"))
    polished = polish_final_document(document)
    structure_unchanged = _without_visible_text(document) == _without_visible_text(polished)
    if not structure_unchanged:
        raise RuntimeError("planning polish changed Final Document structure or non-text fields")

    projection_before = (source / "mechanic-reconstruction-projection.json").read_bytes()
    feedback_before = (source / "feedback-trace.json").read_bytes()
    feedback = json.loads(feedback_before.decode("utf-8"))
    coverage = {
        "fully_reflected": sum(item.get("verificationStatus") == "fully_reflected" for item in feedback.get("records") or []),
        "partially_reflected": sum(item.get("verificationStatus") == "partially_reflected" for item in feedback.get("records") or []),
        "regressed": sum(item.get("verificationStatus") == "regressed" for item in feedback.get("records") or []),
    }
    if coverage != {"fully_reflected": 12, "partially_reflected": 0, "regressed": 0}:
        raise RuntimeError(f"feedback regression gate failed: {coverage}")

    render_document = deepcopy(polished)
    render_document["title"] = delivery_title
    markdown = _clean_markdown(document_to_markdown(render_document))
    before_markdown = _clean_markdown((source / "result-a-final.md").read_text(encoding="utf-8"))
    diff = "".join(difflib.unified_diff(
        before_markdown.splitlines(keepends=True), markdown.splitlines(keepends=True),
        fromfile="Final Delivery Candidate v2", tofile="Final Delivery Candidate v3",
        n=0,
    ))

    output.mkdir(parents=True, exist_ok=True)
    (output / "result-a-final.json").write_text(json.dumps(polished, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "result-a-final.md").write_text(markdown, encoding="utf-8")
    (output / "v2-to-v3.diff").write_text(diff, encoding="utf-8")
    (output / "mechanic-reconstruction-projection.json").write_bytes(projection_before)
    (output / "feedback-trace.json").write_bytes(feedback_before)

    projection_after = (output / "mechanic-reconstruction-projection.json").read_bytes()
    feedback_after = (output / "feedback-trace.json").read_bytes()
    audit = {
        "deliveryStatus": "Final Delivery Candidate v3 / Planner Review Ready",
        "documentStructureUnchanged": structure_unchanged,
        "allowedDocumentFields": sorted(_VISIBLE_TEXT_FIELDS),
        "projectionHashBefore": _sha256(projection_before),
        "projectionHashAfter": _sha256(projection_after),
        "feedbackTraceHashBefore": _sha256(feedback_before),
        "feedbackTraceHashAfter": _sha256(feedback_after),
        "projectionUnchanged": projection_before == projection_after,
        "feedbackTraceUnchanged": feedback_before == feedback_after,
        "evidenceUnchangedByProjectionIdentity": projection_before == projection_after,
        "feedbackCoverage": coverage,
    }
    if not audit["projectionUnchanged"] or not audit["feedbackTraceUnchanged"]:
        raise RuntimeError("frozen Projection or FeedbackTrace changed during polish")
    (output / "planning-language-polish-audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return audit


def main() -> None:
    print(json.dumps(build_v3_artifacts(SOURCE, OUTPUT), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
