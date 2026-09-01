from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from backend.feishu_render import render_feishu_document


ROOT = Path(__file__).resolve().parents[1]
JOB_DIR = ROOT / "data/jobs/4180cd72eeaa4819be41db50bb4c5011"
PUBLICATION = ROOT / "artifacts/full-mechanic-accepted-publication-2026-08-19"


def build_job() -> dict:
    job = json.loads((JOB_DIR / "job.json").read_text(encoding="utf-8"))
    job["acceptedPublication"] = {
        "markdown": (PUBLICATION / "human-planning-preview.md").read_text(encoding="utf-8"),
        "p5Diagrams": json.loads((JOB_DIR / "structures/p5-review-diagrams.json").read_text(encoding="utf-8"))["diagrams"],
        "p6Tables": json.loads((JOB_DIR / "structures/p6-review-tables.json").read_text(encoding="utf-8"))["tables"],
        "nativeBoards": json.loads((PUBLICATION / "accepted-native-boards.json").read_text(encoding="utf-8")),
    }
    return job


def main() -> None:
    job = build_job()
    rendered = render_feishu_document(job, JOB_DIR)
    ue_board = next(item.board for item in rendered.native_boards if item.key == "ue")
    ue_structure = ue_board.structure.get("nodes", [])
    ue_overlay = ue_board.overlay.get("nodes", [])
    ue_pages = sorted(
        int(node["pageNumber"])
        for node in ue_structure
        if type(node.get("pageNumber")) is int and node.get("pageCard") is True
    )
    component_markers = {
        page_number: sorted(
            int(node["componentNumber"])
            for node in ue_overlay
            if node.get("pageNumber") == page_number and type(node.get("componentNumber")) is int
        )
        for page_number in ue_pages
    }
    annotated_pages = sorted(
        int(node["pageNumber"])
        for node in ue_structure
        if node.get("componentAnnotation") is True
    )
    p5_structure = {}
    for diagram in job["acceptedPublication"]["p5Diagrams"]:
        out_degree = Counter(str(edge.get("from") or "") for edge in diagram.get("edges") or [])
        in_degree = Counter(str(edge.get("to") or "") for edge in diagram.get("edges") or [])
        p5_structure[str(diagram.get("id") or "")] = {
            "nodeCount": len(diagram.get("nodes") or []),
            "edgeCount": len(diagram.get("edges") or []),
            "branchNodeCount": sum(value > 1 for value in out_degree.values()),
            "mergeNodeCount": sum(value > 1 for value in in_degree.values()),
            "renderedPathCount": str(diagram.get("svg") or "").count("<path"),
        }
    checks = {
        "nativeBoardKeys": [item.key for item in rendered.native_boards],
        "embeddedP5": rendered.embedded_whiteboard_count,
        "whiteboardSlots": rendered.xml.count('<whiteboard type="blank"></whiteboard>'),
        "nativeAutoSequenceItems": rendered.xml.count('seq="auto"'),
        "uePages": ue_pages,
        "ueComponentMarkers": component_markers,
        "ueAnnotatedPages": annotated_pages,
        "p5Structure": p5_structure,
        "criticalRules": {
            "W-07": "距离载具最近" in rendered.xml,
            "C-10": "无放回" in rendered.xml,
            "C-20": "队列清空后恢复战斗" in rendered.xml,
            "D-06": "3项结果全部获得" in rendered.xml,
            "M-06": "立即造成首次伤害" in rendered.xml,
            "L-06": "剩余怪物清空" in rendered.xml,
            "S-09": "有效战斗秒数" in rendered.xml,
        },
        "legacyTitleAbsent": "Roguelike成长系统" not in rendered.xml,
        "p6TitlesPresent": all(title in rendered.xml for title in (
            "武器词条配置", "武器与接触战斗配置", "伤害统计配置",
            "关卡与奖励配置", "三选一配置", "独立抽取配置",
        )),
    }
    checks["valid"] = (
        checks["nativeBoardKeys"] == ["ue", "planning", "competitor"]
        and checks["embeddedP5"] == 5
        and checks["whiteboardSlots"] == 8
        and checks["nativeAutoSequenceItems"] > 0
        and checks["uePages"] == list(range(1, 10))
        and checks["ueAnnotatedPages"] == checks["uePages"]
        and all(numbers == [1, 2, 3, 4] for numbers in checks["ueComponentMarkers"].values())
        and all(
            item["branchNodeCount"] > 0
            and item["mergeNodeCount"] > 0
            and item["edgeCount"] >= item["nodeCount"]
            and item["renderedPathCount"] >= item["edgeCount"]
            for item in checks["p5Structure"].values()
        )
        and all(checks["criticalRules"].values())
        and checks["legacyTitleAbsent"]
        and checks["p6TitlesPresent"]
    )
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not checks["valid"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
