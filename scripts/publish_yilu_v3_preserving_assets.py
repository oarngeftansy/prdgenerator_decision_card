"""Publish v3 text while preserving prior native gameplay diagrams and tables."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
from typing import Any
import re


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "yilu-kuangbiao-feishu-v3-2026-08-24"
MANIFEST_PATH = ARTIFACT_DIR / "asset-retention-manifest.json"
CHECKPOINT_PATH = ARTIFACT_DIR / "publication-checkpoint.json"
FINAL_PATH = ROOT / "artifacts" / "yilu-kuangbiao-final-delivery-candidate-v3-2026-08-24" / "result-a-final.md"


def _text(element: ET.Element) -> str:
    return "".join(element.itertext()).strip()


def _parse_fragment(xml: str) -> ET.Element:
    stripped = xml.strip()
    try:
        return ET.fromstring(stripped)
    except ET.ParseError:
        return ET.fromstring(f"<fragment>{stripped}</fragment>")


def plan_block_reorganization(old_document: str, manifest: dict[str, Any]) -> dict[str, Any]:
    root = _parse_fragment(old_document)
    excluded = set(manifest.get("excludedSections") or [])
    retained_ids: list[str] = []
    captions: list[str] = []
    delete_ids: list[str] = []
    current_h2 = ""
    previous_heading: ET.Element | None = None
    children = list(root)
    retained_heading_ids: set[str] = set()
    for element in children:
        tag = element.tag
        if tag == "h2":
            current_h2 = _text(element)
        if tag in {"h2", "h3", "h4", "h5", "h6"}:
            previous_heading = element
        resource_allowed = current_h2 not in excluded and tag in {"table", "whiteboard"}
        if resource_allowed:
            resource_id = element.get("id")
            heading_id = previous_heading.get("id") if previous_heading is not None else None
            heading_text = _text(previous_heading) if previous_heading is not None else "既有玩法图表"
            if heading_id and heading_id not in retained_heading_ids:
                retained_ids.append(heading_id)
                retained_heading_ids.add(heading_id)
                captions.append(heading_text)
            if resource_id:
                retained_ids.append(resource_id)

    retained = set(retained_ids)
    for element in children:
        block_id = element.get("id")
        if block_id and block_id not in retained:
            delete_ids.append(block_id)
        if element.tag in {"ul", "ol"}:
            delete_ids.extend(
                child.get("id") for child in list(element)
                if child.get("id") and child.get("id") not in retained
            )
    return {
        "retainedBlockIds": retained_ids,
        "retainedAssetCaptions": captions,
        "deleteBlockIds": list(dict.fromkeys(delete_ids)),
    }


def build_v3_feishu_payload(old_document: str, final_v3: str, manifest: dict[str, Any]) -> dict[str, Any]:
    plan = plan_block_reorganization(old_document, manifest)
    appendix = str(manifest.get("appendixTitle") or "附录：既有玩法图表")
    markdown = final_v3.rstrip() + f"\n\n## {appendix}\n\n以下保留上一版中的原生玩法流程图与配置表，仅作为执行辅助，不改变本版结构化规则权威。\n"
    return {**plan, "markdown": markdown}


def _lark_cli() -> str:
    configured = os.environ.get("LARK_CLI")
    if configured:
        return configured
    found = shutil.which("lark-cli") or shutil.which("lark-cli.exe")
    if found:
        return found
    fallback = Path.home() / "Documents" / "飞书机器人（jojo）" / "node_modules" / "@larksuite" / "cli" / "bin" / "lark-cli.exe"
    if fallback.exists():
        return str(fallback)
    raise RuntimeError("lark-cli not found")


def _run(*args: str) -> dict[str, Any]:
    completed = subprocess.run(
        [_lark_cli(), *args, "--as", "user"], cwd=ROOT,
        check=False, capture_output=True, text=True, encoding="utf-8",
    )
    stream = completed.stdout or completed.stderr
    payload = json.loads(stream)
    if completed.returncode or not payload.get("ok"):
        raise RuntimeError(json.dumps(payload, ensure_ascii=False))
    return payload


def _fetch(doc: str, *args: str) -> dict[str, Any]:
    return _run("docs", "+fetch", "--doc", doc, *args)


def publish() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    if checkpoint.get("status") == "published":
        return checkpoint
    document_token = str(checkpoint["documentToken"])
    fetched = _fetch(document_token, "--detail", "full")
    document = fetched["data"]["document"]
    payload = build_v3_feishu_payload(
        document["content"], FINAL_PATH.read_text(encoding="utf-8"), manifest
    )
    payload_path = ARTIFACT_DIR / "v3-feishu-payload.md"
    payload_path.write_text(payload["markdown"], encoding="utf-8")
    (ARTIFACT_DIR / "block-reorganization-plan.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    delete_ids = payload["deleteBlockIds"]
    if delete_ids:
        _run("docs", "+update", "--doc", document_token, "--command", "block_delete", "--block-id", ",".join(delete_ids))
    _run(
        "docs", "+update", "--doc", document_token, "--command", "append",
        "--doc-format", "markdown", "--content", f"@{payload_path.relative_to(ROOT).as_posix()}",
    )
    outline = _fetch(document_token, "--scope", "outline", "--max-depth", "3", "--detail", "with-ids")
    outline_xml = outline["data"]["document"]["content"]
    appendix_heading = next(
        element for element in _parse_fragment(outline_xml).iter()
        if element.tag == "h2" and _text(element) == manifest["appendixTitle"]
    )
    refreshed = _fetch(document_token, "--detail", "full")
    refreshed_plan = plan_block_reorganization(refreshed["data"]["document"]["content"], {**manifest, "excludedSections": []})
    retained_ids = [block_id for block_id in refreshed_plan["retainedBlockIds"] if block_id != appendix_heading.get("id")]
    if retained_ids:
        _run(
            "docs", "+update", "--doc", document_token, "--command", "block_move_after",
            "--block-id", str(appendix_heading.get("id")), "--src-block-ids", ",".join(retained_ids),
        )
    checkpoint.update({
        "status": "published", "sourceRevision": document.get("revision_id"),
        "retainedAssetCount": len(payload["retainedBlockIds"]) // 2,
    })
    CHECKPOINT_PATH.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return checkpoint


def verify() -> dict[str, Any]:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    checkpoint = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    document_token = str(checkpoint["documentToken"])
    full = _fetch(document_token, "--detail", "full")["data"]["document"]
    outline = _fetch(document_token, "--scope", "outline", "--max-depth", "3", "--detail", "with-ids")["data"]["document"]
    content = str(full["content"])
    root = _parse_fragment(content)
    visible_text = _text(root)
    captions = [
        _text(element) for element in root.iter()
        if element.tag in {"h3", "h4", "h5"}
        and _text(element).startswith(("图示：", "配置表："))
    ]
    forbidden = {
        term: visible_text.count(term)
        for term in manifest.get("excludedSections") or []
    }
    internal_ids = re.findall(r"\b(?:RULE|FACT|GAP|PROPOSAL)-[A-Za-z0-9_-]+", visible_text)
    result = {
        "schemaVersion": "feishu-v3-remote-verification-v1",
        "documentToken": document_token,
        "documentUrl": checkpoint["documentUrl"],
        "revisionId": full.get("revision_id"),
        "titlePresent": "Final Delivery Candidate v3 / Planner Review Ready" in visible_text,
        "forbiddenSectionMatches": forbidden,
        "retainedAssetCaptions": captions,
        "retainedTableCount": sum(element.tag == "table" for element in root.iter()),
        "retainedWhiteboardCount": sum(element.tag == "whiteboard" for element in root.iter()),
        "internalIdMatches": internal_ids,
    }
    result["passed"] = (
        result["titlePresent"]
        and all(count == 0 for count in forbidden.values())
        and len(captions) >= 1
        and result["retainedTableCount"] >= 1
        and not internal_ids
    )
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    (ARTIFACT_DIR / "remote-verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (ARTIFACT_DIR / "remote-outline.xml").write_text(str(outline["content"]), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.publish:
        result = publish()
    elif args.verify:
        result = verify()
    else:
        raise SystemExit("use --publish or --verify")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
