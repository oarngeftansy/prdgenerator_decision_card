from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.evaluate_phase51_baseline import _annotated_chapters, _snapshot_markdown


ROOT = Path(__file__).resolve().parents[1]
DELIVERY = ROOT / "artifacts/planning-content-phase5.1-2026-08-17/phase51-delivery.json"
BLOCKS = ROOT / "artifacts/planning-content-phase4.3-2026-08-17/mechanism-role-blocks.json"
VISUALS = ROOT / "artifacts/planning-content-phase5.1-2026-08-17/visual-blocks.json"
COMPARISON = ROOT / "artifacts/planning-content-phase5.1-2026-08-17/six-chapter-comparison.md"
OUTPUT = ROOT / "artifacts/planning-content-phase5.1-evaluation-2026-08-17"


def _artifact_hash(delivery: dict[str, Any]) -> str:
    payload = json.dumps(delivery, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def export_existing_baseline_snapshot(output_dir: Path = OUTPUT) -> str:
    delivery = json.loads(DELIVERY.read_text(encoding="utf-8"))
    block_data = json.loads(BLOCKS.read_text(encoding="utf-8"))
    mechanism_blocks = [block for chapter in block_data["chapters"].values() for block in chapter["blocks"]]
    artifact_hash = _artifact_hash(delivery)
    annotated = _annotated_chapters(delivery, mechanism_blocks)
    snapshot = {
        "evaluatedArtifactHash": artifact_hash,
        "executionDelivery": delivery,
        "annotatedChapters": annotated,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "evaluated_delivery_snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (output_dir / "evaluated_delivery_snapshot.md").write_text(
        _snapshot_markdown(delivery, annotated, artifact_hash), encoding="utf-8"
    )

    report_path = output_dir / "target-alignment-report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["evaluatedArtifactHash"] = artifact_hash
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    audit_lines = [
        COMPARISON.read_text(encoding="utf-8").rstrip(), "", "---", "",
        "## 本次 90.42 分实际正文段落审计", "",
        "> 下列标注来自既有 Granularity/TargetAlignment findings；不修改正文，也不重新评分。", "",
    ]
    for chapter in annotated:
        audit_lines += [f"### {chapter['title']}", ""]
        for paragraph in chapter["paragraphs"]:
            audit_lines += [
                f"#### {paragraph['paragraphId']} · {paragraph['carrierType']}", "",
                paragraph["text"], "",
                f"- supportingRuleIds[]: `{json.dumps(paragraph['supportingRuleIds'], ensure_ascii=False)}`",
                f"- mechanismBlockId: `{paragraph['mechanismBlockId']}`",
                f"- 包含 VisualBlock 引用: `{str(paragraph['containsVisualBlockReference']).lower()}`",
                f"- 扣分标注: `{json.dumps(paragraph['evaluatorFindings'], ensure_ascii=False)}`", "",
            ]
    audit_lines += [
        "### 关卡流程", "",
        "- 最终正文：无。Phase 5.1 判定为 evidence_insufficient，未进入本次评分正文段落。", "",
        "### 结算", "",
        "- 最终正文：无。两条既有信息均为 Presentation Rule，已进入 VisualBlock，未进入本次 Logic-only 评分正文。", "",
        f"- evaluatedArtifactHash: `{artifact_hash}`", "",
    ]
    (output_dir / "six-chapter-evaluated-delivery-acceptance.md").write_text(
        "\n".join(audit_lines), encoding="utf-8"
    )
    return artifact_hash


if __name__ == "__main__":
    print(export_existing_baseline_snapshot())
