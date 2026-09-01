from __future__ import annotations

from collections import Counter
from typing import Any

from .models import make_source_ref


def _attached_id(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    attached = value.get("attached_object") or value.get("attachedObject")
    if isinstance(attached, dict) and attached.get("id"):
        return str(attached["id"])
    if value.get("id"):
        return str(value["id"])
    return None


def _node_text(node: dict[str, Any]) -> str:
    value = node.get("text")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or "").strip()
    for key in ("composite_shape", "shape"):
        nested = node.get(key)
        if isinstance(nested, dict):
            text = nested.get("text")
            if isinstance(text, dict):
                text = text.get("text")
            if text:
                return str(text).strip()
    return ""


def parse_whiteboard(nodes: list[dict[str, Any]], board_id: str) -> dict[str, Any]:
    normalized: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []
    assets: list[dict[str, Any]] = []
    unresolved: list[str] = []
    counts = Counter(str(node.get("type", "unknown")) for node in nodes)
    for node in nodes:
        node_id = str(node.get("id", ""))
        node_type = str(node.get("type", "unknown"))
        if node_type == "connector":
            connector = node.get("connector") if isinstance(node.get("connector"), dict) else node
            start = _attached_id(connector.get("start_object") or connector.get("start"))
            end = _attached_id(connector.get("end_object") or connector.get("end"))
            edge = {"id": node_id, "from": start, "to": end, "shape": connector.get("shape")}
            edges.append(edge)
            if not start or not end:
                unresolved.append(node_id)
            continue
        item = {
            "id": node_id,
            "type": node_type,
            "text": _node_text(node),
            "parentId": node.get("parent_id") or node.get("parentId"),
            "bounds": {key: node.get(key) for key in ("x", "y", "width", "height", "angle")},
            "style": node.get("style") or {},
            "sourceRef": make_source_ref("whiteboard", board_id, node_id),
        }
        normalized.append(item)
        if node_type in {"group", "section"}:
            groups.append(item)
        if node_type == "image":
            assets.append(item)
    return {
        "boardId": board_id,
        "nodes": normalized,
        "edges": edges,
        "groups": groups,
        "assets": assets,
        "sourceCounts": dict(counts),
        "diagnostics": {"unresolvedEdges": unresolved},
    }
