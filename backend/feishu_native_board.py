from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import gcd
from pathlib import Path
from typing import Any

from .review_model import is_reference_asset_path


SECTION_STYLE = {
    "border_color_type": 0,
    "border_opacity": 100,
    "border_radius": {"bottom_left": 4, "bottom_right": 4, "top_left": 4, "top_right": 4},
    "border_style": "solid",
    "border_width": "extra_narrow",
    "fill_color": "#f5f6f7",
    "fill_color_type": 0,
    "fill_opacity": 100,
    "theme_border_color_code": -1,
    "theme_fill_color_code": -1,
}


@dataclass(frozen=True)
class BoardImage:
    frame_id: str
    image_path: str
    node: dict[str, Any]


@dataclass(frozen=True)
class NativeWhiteboard:
    structure: dict[str, list[dict[str, Any]]]
    overlay: dict[str, list[dict[str, Any]]]
    images: tuple[BoardImage, ...]


@dataclass(frozen=True)
class NamedWhiteboard:
    key: str
    title: str
    board: NativeWhiteboard


def _frame_image_path(job: dict[str, Any], frame: dict[str, Any], frame_id: str) -> str:
    if frame.get("imagePath"):
        return str(frame["imagePath"])
    image_url = str(frame.get("imageUrl") or "")
    prefix = f"/artifacts/{job.get('id')}/"
    if image_url.startswith(prefix):
        return image_url[len(prefix):]
    return f"frames/{frame_id}.jpg"


def _source_dimensions(frame: dict[str, Any]) -> tuple[int, int] | None:
    structure = frame.get("structure") if isinstance(frame.get("structure"), dict) else {}
    source = frame.get("source") if isinstance(frame.get("source"), dict) else {}
    width = structure.get("width") or source.get("width") or frame.get("width")
    height = structure.get("height") or source.get("height") or frame.get("height")
    if isinstance(width, (int, float)) and isinstance(height, (int, float)) and width > 0 and height > 0:
        return int(width), int(height)
    return None


def _fit_original_ratio(frame: dict[str, Any], max_width: int = 300, max_height: int = 462) -> tuple[int, int]:
    dimensions = _source_dimensions(frame)
    if not dimensions:
        return max_width, max_height
    width, height = dimensions
    divisor = gcd(width, height)
    unit_width, unit_height = width // divisor, height // divisor
    multiplier = max(1, min(max_width // unit_width, max_height // unit_height))
    return unit_width * multiplier, unit_height * multiplier


def _text_node(node_id: str, text: str, x: int, y: int, width: int, *, size: int = 15) -> dict[str, Any]:
    # Narrow connector labels must wrap instead of overflowing their capsule.
    # CJK copy is approximately one font-size unit per character at this scale.
    chars_per_line = max(1, width // max(size, 1))
    line_count = sum(max(1, (len(line) + chars_per_line - 1) // chars_per_line) for line in (text.splitlines() or [""]))
    return {
        "id": node_id,
        "type": "text_shape",
        "x": x,
        "y": y,
        "width": width,
        "height": max(48, round(line_count * size * 1.5) + 12),
        "text": {
            "text": text,
            "font_size": size,
            "font_weight": "regular",
            "horizontal_align": "left",
            "vertical_align": "top",
            "text_color": "#1f2329",
            "text_color_type": 1,
        },
    }


def _section(node_id: str, title: str, x: int, width: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "section",
        "x": x,
        "y": 0,
        "width": width,
        "height": 720,
        "locked": False,
        "children": [],
        "section": {"title": title},
        "style": dict(SECTION_STYLE),
    }


def _connector(
    node_id: str, start: tuple[int, int], end: tuple[int, int], *, dashed: bool, end_arrow: bool,
) -> dict[str, Any]:
    """Create one standard, straight Feishu connector segment."""
    x1, y1 = start
    x2, y2 = end
    return {
        "id": node_id,
        "type": "connector",
        "x": min(x1, x2),
        "y": min(y1, y2),
        "width": abs(x2 - x1),
        "height": abs(y2 - y1),
        "style": {
            "border_opacity": 100,
            "border_width": "narrow",
            "border_color": "#8f959e",
            "border_color_type": 1,
            "border_style": "dash" if dashed else "solid",
        },
        "connector": {
            "start": {"position": {"x": x1, "y": y1}, "arrow_style": "none"},
            "end": {"position": {"x": x2, "y": y2}, "arrow_style": "triangle_arrow" if end_arrow else "none"},
            "shape": "straight",
            "specified_coordinate": True,
            "caption_auto_direction": False,
        },
    }


def _marker(node_id: str, number: int, x: int, y: int) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "composite_shape",
        "x": x,
        "y": y,
        "width": 22,
        "height": 22,
        "style": {
            "border_width": "narrow",
            "border_color": "#ffffff",
            "border_color_type": 1,
            "fill_color": "#f54a45",
            "fill_color_type": 1,
        },
        "composite_shape": {"type": "ellipse"},
        "text": {
            "text": str(number),
            "font_size": 12,
            "font_weight": "regular",
            "horizontal_align": "center",
            "vertical_align": "mid",
            "text_color": "#ffffff",
            "text_color_type": 1,
        },
    }


def _note(node_id: str, text: str, x: int, y: int, width: int = 360) -> dict[str, Any]:
    node = _text_node(node_id, text, x, y, width, size=14)
    node["type"] = "composite_shape"
    node["composite_shape"] = {"type": "round_rect"}
    node["style"] = {"fill_color": "#fff3bf", "fill_color_type": 1, "border_color": "#f5c842", "border_color_type": 1}
    return node


def _asset_is_ready(asset: dict[str, Any], key: str, job_dir: Path | None) -> bool:
    asset_id, path, order = asset.get("id"), asset.get("relativePath"), asset.get("order")
    if asset.get("status") != "ready" or not isinstance(asset_id, str) or not asset_id or type(order) is not int or order < 1 or not is_reference_asset_path(key, path):
        return False
    if job_dir is None:
        return True
    root = Path(job_dir)
    if not root.is_dir():
        return False
    root, candidate = root.resolve(), (root / str(path)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return False
    return candidate.is_file()


def compile_reference_whiteboard(job: dict[str, Any], key: str, title: str, job_dir: Path | None = None) -> NativeWhiteboard:
    """Compile an optional reference board without video-analysis assets."""
    review = job.get("reviewModel") if isinstance(job.get("reviewModel"), dict) else {}
    boards = review.get("referenceBoards") if isinstance(review.get("referenceBoards"), dict) else {}
    board = boards.get(key) if isinstance(boards.get(key), dict) else {}
    assets = board.get("assets") if isinstance(board.get("assets"), list) else []
    candidates = [asset for asset in assets if isinstance(asset, dict) and _asset_is_ready(asset, key, job_dir)]
    duplicate_ids = Counter(str(asset["id"]) for asset in candidates)
    duplicate_orders = Counter(int(asset["order"]) for asset in candidates)
    duplicate_paths = Counter(str(asset["relativePath"]) for asset in candidates)
    valid_assets = [
        asset for asset in candidates
        if duplicate_ids[str(asset["id"])] == duplicate_orders[int(asset["order"])] == duplicate_paths[str(asset["relativePath"])] == 1
    ]
    valid_assets.sort(key=lambda item: (item["order"], item["id"]))
    structure = {"nodes": [_section(f"section-{key}", title, 0, max(560, 80 + len(valid_assets) * 320))]}
    images: list[BoardImage] = []
    overlay: list[dict[str, Any]] = []
    if not valid_assets:
        overlay.append(_note(f"note-{key}-pending", "待补充", 80, 140))
    elif len(valid_assets) != len(assets):
        overlay.append(_note(f"note-{key}-pending", "素材缺失/待补充", 80, 140))
    for index, asset in enumerate(valid_assets, 1):
        x = 80 + (index - 1) * 320
        node = {"id": f"image-{key}-{index}", "type": "image", "x": x, "y": 120, "width": 280, "height": 500, "style": {"border_style": "none"}}
        images.append(BoardImage(asset["id"], asset["relativePath"], node))
        overlay.append(_text_node(f"label-{key}-{index}", str(asset.get("sourceName") or ""), x, 640, 280))
    return NativeWhiteboard(structure, {"nodes": overlay}, tuple(images))


def compile_gve16_whiteboards(job: dict[str, Any], job_dir: Path | None = None) -> tuple[NamedWhiteboard, ...]:
    return compile_gve16_delivery_whiteboards(job, job_dir)


def compile_gve16_delivery_whiteboards(job: dict[str, Any], job_dir: Path | None = None) -> tuple[NamedWhiteboard, ...]:
    """Current board policy: emit the planning sketch only."""
    return (NamedWhiteboard("planning", "策划草图", compile_gve16_whiteboard(job)),)


def _flow_node(node_id: str, title: str, detail: str, x: int, y: int, width: int, height: int, kind: str) -> dict[str, Any]:
    palette = {
        "start": ("#E8F3FF", "#3370FF"),
        "state": ("#FFFFFF", "#8F959E"),
        "decision": ("#FFF7E8", "#F59E0B"),
        "success": ("#E8FFEA", "#34A853"),
        "failure": ("#FFF0F0", "#F54A45"),
        "return": ("#F3F0FF", "#7B61FF"),
    }
    fill, border = palette.get(kind, palette["state"])
    text = title if not detail else f"{title}\n{detail}"
    node = _text_node(node_id, text, x, y, width, size=14)
    node.update({
        "type": "composite_shape",
        "height": height,
        "composite_shape": {"type": "diamond" if kind == "decision" else "round_rect"},
        "style": {
            "fill_color": fill,
            "fill_color_type": 1,
            "border_color": border,
            "border_color_type": 1,
            "border_width": "narrow",
        },
    })
    node["text"].update({"horizontal_align": "center", "vertical_align": "mid"})
    return node


def _component_marker_point(component: dict[str, Any]) -> tuple[float, float, list[float]]:
    """Derive one marker point from a verified component region.

    A marker is no longer allowed to carry an unrelated freehand x/y pair. The
    normalized target box is the visual contract; the named anchor only chooses
    a readable point inside that same component.
    """
    values = component.get("targetBox")
    if not isinstance(values, list) or len(values) != 4 or not all(isinstance(value, (int, float)) for value in values):
        raise ValueError("UE component requires normalized targetBox")
    left, top, right, bottom = (float(value) for value in values)
    if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
        raise ValueError("UE component targetBox must stay inside screenshot")
    points = {
        "center": (0.5, 0.5),
        "left": (0.15, 0.5),
        "right": (0.85, 0.5),
        "top_left": (0.2, 0.2),
        "top_right": (0.8, 0.2),
        "bottom_left": (0.2, 0.8),
        "bottom_right": (0.8, 0.8),
    }
    anchor = str(component.get("markerAnchor") or "center")
    if anchor not in points:
        raise ValueError(f"unsupported UE component markerAnchor: {anchor}")
    horizontal, vertical = points[anchor]
    return (
        left + (right - left) * horizontal,
        top + (bottom - top) * vertical,
        [left, top, right, bottom],
    )


def _edge_label(node_id: str, text: str, x: int, y: int, *, width: int | None = None) -> dict[str, Any]:
    # Keep the opaque readability background, but size it to its caption so it
    # does not mask an unnecessarily long stretch of the connector underneath.
    label_width = width if width is not None else max(72, min(180, len(text) * 14 + 24))
    node = _text_node(node_id, text, x, y, label_width, size=12)
    node.update({
        "type": "composite_shape",
        "height": node["height"],
        "composite_shape": {"type": "round_rect"},
        "style": {
            "fill_color": "#FFFFFF",
            "fill_color_type": 1,
            "border_color": "#FFFFFF",
            "border_color_type": 1,
            "border_width": "narrow",
        },
    })
    return node


def _boxes_overlap(first: dict[str, Any], second: dict[str, Any], *, padding: int = 0) -> bool:
    return (
        float(first.get("x") or 0) < float(second.get("x") or 0) + float(second.get("width") or 0) + padding
        and float(first.get("x") or 0) + float(first.get("width") or 0) + padding > float(second.get("x") or 0)
        and float(first.get("y") or 0) < float(second.get("y") or 0) + float(second.get("height") or 0) + padding
        and float(first.get("y") or 0) + float(first.get("height") or 0) + padding > float(second.get("y") or 0)
    )


def _place_edge_label(
    node_id: str,
    text: str,
    points: list[tuple[int, int]],
    occupied: list[dict[str, Any]],
    preferred: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Place a connector caption beside a segment without covering content.

    The normal editorial capsule is tried first. Dense corridors fall back to
    a narrow wrapped capsule, keeping the label in the connector lane instead
    of masking a screenshot, component explanation or state node.
    """

    segments = sorted(
        zip(points, points[1:]),
        key=lambda pair: abs(pair[1][0] - pair[0][0]) + abs(pair[1][1] - pair[0][1]),
        reverse=True,
    )
    widths = [max(72, min(180, len(text) * 14 + 24)), 30]
    for width in widths:
        probe = _edge_label(node_id, text, 0, 0, width=width)
        height = int(probe["height"])
        candidates: list[tuple[int, int]] = []
        if preferred is not None:
            candidates.append(preferred)
        if points:
            start_x, start_y = points[0]
            end_x, end_y = points[-1]
            # Default elbow routes split a narrow inter-node corridor into two
            # short segments. Center the compact label in the whole corridor.
            if start_x != end_x:
                candidates.extend([
                    (round((start_x + end_x) / 2) - width // 2, min(start_y, end_y) - height - 8),
                    (round((start_x + end_x) / 2) - width // 2, max(start_y, end_y) + 8),
                ])
            if start_y != end_y:
                candidates.extend([
                    (min(start_x, end_x) - width - 8, round((start_y + end_y) / 2) - height // 2),
                    (max(start_x, end_x) + 8, round((start_y + end_y) / 2) - height // 2),
                ])
        for (x1, y1), (x2, y2) in segments:
            if y1 == y2:
                center_x = round((x1 + x2) / 2)
                candidates.extend([
                    (center_x - width // 2, y1 - height - 8),
                    (center_x - width // 2, y1 + 8),
                ])
            elif x1 == x2:
                center_y = round((y1 + y2) / 2)
                candidates.extend([
                    (x1 + 8, center_y - height // 2),
                    (x1 - width - 8, center_y - height // 2),
                ])
        for x, y in candidates:
            candidate = _edge_label(node_id, text, max(0, x), max(0, y), width=width)
            if not any(_boxes_overlap(candidate, item, padding=4) for item in occupied):
                return candidate
    raise ValueError(f"unable to place edge label without visual occlusion: {node_id}")


def _section_box(node_id: str, title: str, x: int, y: int, width: int, height: int, children: list[str]) -> dict[str, Any]:
    node = _section(node_id, title, x, width)
    node.update({"y": y, "height": height, "children": children})
    return node


def _orthogonal_connectors(
    edge_id: str,
    start: tuple[int, int],
    end: tuple[int, int],
    *,
    dashed: bool = False,
) -> list[dict[str, Any]]:
    """Route a visible elbow using only Feishu-supported straight segments."""
    x1, y1 = start
    x2, y2 = end
    if x1 == x2 or y1 == y2:
        return [_connector(f"edge-{edge_id}-1", start, end, dashed=dashed, end_arrow=True)]
    middle_x = round((x1 + x2) / 2)
    return [
        _connector(f"edge-{edge_id}-1", start, (middle_x, y1), dashed=dashed, end_arrow=False),
        _connector(f"edge-{edge_id}-2", (middle_x, y1), (middle_x, y2), dashed=dashed, end_arrow=False),
        _connector(f"edge-{edge_id}-3", (middle_x, y2), end, dashed=dashed, end_arrow=True),
    ]


def _accepted_ue_whiteboard(job: dict[str, Any], spec: dict[str, Any]) -> NativeWhiteboard:
    sections = [item for item in spec.get("sections") or [] if isinstance(item, dict)]
    nodes = [item for item in spec.get("nodes") or [] if isinstance(item, dict)]
    edges = [item for item in spec.get("edges") or [] if isinstance(item, dict)]
    if len(sections) < 3 or len(nodes) < 8 or len(edges) < 8:
        raise ValueError("accepted UE flow must contain detailed sections, states and transitions")

    structure: list[dict[str, Any]] = []
    page_backgrounds: list[dict[str, Any]] = []
    overlay: list[dict[str, Any]] = []
    images: list[BoardImage] = []
    frame_by_id = {str(frame.get("id") or ""): frame for frame in job.get("frames") or [] if isinstance(frame, dict)}
    positioned: dict[str, dict[str, Any]] = {}
    child_ids: dict[str, list[str]] = {str(item.get("id") or ""): [] for item in sections}
    for item in nodes:
        node_id = str(item.get("id") or "")
        if not node_id or node_id in positioned:
            raise ValueError("accepted UE flow node ids must be unique and non-empty")
        page_number = item.get("pageNumber")
        components = [value for value in item.get("components") or [] if isinstance(value, dict)]
        is_page = type(page_number) is int and page_number > 0 and bool(components)
        node_title = f"页面 {page_number}｜{str(item.get('title') or '')}" if is_page else str(item.get("title") or "")
        node_detail = "" if is_page else str(item.get("detail") or "")
        node = _flow_node(
            f"ue-{node_id}", node_title, node_detail,
            int(item.get("x") or 0), int(item.get("y") or 0),
            int(item.get("width") or 260), int(item.get("height") or 104),
            str(item.get("kind") or "state"),
        )
        if is_page:
            node["pageNumber"] = page_number
            node["pageCard"] = True
            node["text"].update({"vertical_align": "top", "horizontal_align": "left"})
        positioned[node_id] = node
        # Feishu assigns a higher remote z-index to nodes written earlier in
        # one raw update.  A page card is a background carrier, so defer it
        # until its screenshot, component copy, and fallback wireframe have
        # all been written.  Otherwise the white card covers those children.
        if is_page:
            page_backgrounds.append(node)
        else:
            structure.append(node)
        section_id = str(item.get("sectionId") or "")
        child_ids.setdefault(section_id, []).append(node["id"])
        frame_id = str(item.get("frameId") or "")
        if is_page:
            image_x, image_y = node["x"] + 24, node["y"] + 66
            image_width, image_height = 170, 320
            image_node = {
                "id": f"ue-evidence-{node_id}", "type": "image",
                "x": image_x, "y": image_y,
                "width": image_width, "height": image_height, "style": {"border_style": "none"},
                "pageNumber": page_number,
            }
            structure.append(image_node)
            child_ids.setdefault(section_id, []).append(image_node["id"])
            if frame_id and frame_id in frame_by_id:
                images.append(BoardImage(frame_id, _frame_image_path(job, frame_by_id[frame_id], frame_id), image_node))
            else:
                image_node.update({
                    "type": "composite_shape", "composite_shape": {"type": "round_rect"},
                    "style": {"fill_color": "#F7F8FA", "fill_color_type": 1, "border_color": "#B8BDC7", "border_color_type": 1},
                    "text": {
                        "text": "策划页面线框\n无原始失败截图", "font_size": 11, "font_weight": "regular",
                        "horizontal_align": "center", "vertical_align": "mid",
                        "text_color": "#646A73", "text_color_type": 1,
                    },
                })
                for component in components:
                    component_number = int(component.get("number") or 0)
                    component_name = str(component.get("name") or "组件")
                    _, _, target_box = _component_marker_point(component)
                    left, top, right, bottom = target_box
                    wireframe = _flow_node(
                        f"ue-wireframe-{page_number}-{component_number}", component_name, "",
                        image_x + round(left * image_width), image_y + round(top * image_height),
                        max(36, round((right - left) * image_width)),
                        max(32, round((bottom - top) * image_height)),
                        "failure" if component_number == 1 else "state",
                    )
                    wireframe["text"].update({"font_size": 10})
                    wireframe.update({
                        "pageNumber": page_number,
                        "componentNumber": component_number,
                        "wireframeComponent": True,
                    })
                    structure.append(wireframe)
                    child_ids.setdefault(section_id, []).append(wireframe["id"])
            copy_lines: list[str] = []
            for component in components:
                component_number = int(component.get("number") or len(copy_lines) + 1)
                copy_lines.extend([
                    f"{component_number}. {str(component.get('name') or '组件')}",
                    f"作用：{str(component.get('role') or '')}",
                    f"交互：{str(component.get('interaction') or '')}",
                ])
                marker_point_x, marker_point_y, target_box = _component_marker_point(component)
                marker_x = image_x + round(marker_point_x * image_width) - 11
                marker_y = image_y + round(marker_point_y * image_height) - 11
                marker = _marker(f"ue-component-marker-{page_number}-{component_number}", component_number, marker_x, marker_y)
                marker.update({
                    "pageNumber": page_number,
                    "componentNumber": component_number,
                    "pageNodeId": node_id,
                    "targetBox": target_box,
                    "markerPoint": [marker_point_x, marker_point_y],
                    "embeddedNumber": True,
                })
                overlay.append(marker)
            copy_node = _text_node(
                f"ue-component-copy-{page_number}", "\n".join(copy_lines),
                node["x"] + 216, node["y"] + 62, node["width"] - 238, size=13,
            )
            copy_node.update({"pageNumber": page_number, "componentAnnotation": True})
            structure.append(copy_node)
            child_ids.setdefault(section_id, []).append(copy_node["id"])
        elif frame_id and frame_id in frame_by_id:
            image_node = {
                "id": f"ue-evidence-{node_id}", "type": "image",
                "x": node["x"] + node["width"] - 72, "y": node["y"] + 10,
                "width": 56, "height": 84, "style": {"border_style": "none"},
            }
            structure.append(image_node)
            child_ids.setdefault(section_id, []).append(image_node["id"])
            images.append(BoardImage(frame_id, _frame_image_path(job, frame_by_id[frame_id], frame_id), image_node))
    # Page cards sit below all page-local children, while section fills sit
    # below the complete page cards.  Both orderings are required by Feishu's
    # reversed remote z-index convention.
    structure.extend(page_backgrounds)
    section_nodes: list[dict[str, Any]] = []
    for item in sections:
        section_id = str(item.get("id") or "")
        section = _section_box(
            f"ue-section-{section_id}", str(item.get("title") or ""),
            int(item.get("x") or 0), int(item.get("y") or 0),
            int(item.get("width") or 2200), int(item.get("height") or 600),
            child_ids.get(section_id, []),
        )
        section_nodes.append(section)
    structure.extend(section_nodes)
    structure.insert(0, _note(
        "ue-board-header",
        "UE流转图｜页面、组件作用、交互逻辑与分支回流（各分区可独立移动）",
        760,
        0,
        1800,
    ))

    for edge_index, item in enumerate(edges, 1):
        source_id, target_id = str(item.get("from") or ""), str(item.get("to") or "")
        if source_id not in positioned or target_id not in positioned:
            raise ValueError(f"accepted UE edge references missing node: {source_id}->{target_id}")
        source, target = positioned[source_id], positioned[target_id]
        def anchor(node: dict[str, Any], value: str) -> tuple[int, int]:
            if value == "left":
                return node["x"], node["y"] + node["height"] // 2
            if value == "top":
                return node["x"] + node["width"] // 2, node["y"]
            if value == "bottom":
                return node["x"] + node["width"] // 2, node["y"] + node["height"]
            return node["x"] + node["width"], node["y"] + node["height"] // 2

        default_start, default_end = "right", "left"
        if str(item.get("route") or "") == "vertical":
            default_start, default_end = "bottom", "top"
        start = anchor(source, str(item.get("startAnchor") or default_start))
        end = anchor(target, str(item.get("endAnchor") or default_end))
        edge_id = str(item.get("id") or edge_index)
        via = [
            (int(point[0]), int(point[1]))
            for point in item.get("via") or []
            if isinstance(point, list) and len(point) == 2
        ]
        points = [start, *via, end]
        if via:
            for segment_index, (segment_start, segment_end) in enumerate(zip(points, points[1:]), 1):
                overlay.append(_connector(
                    f"edge-{edge_id}-{segment_index}", segment_start, segment_end,
                    dashed=bool(item.get("dashed")), end_arrow=segment_index == len(points) - 1,
                ))
        else:
            overlay.extend(_orthogonal_connectors(edge_id, start, end, dashed=bool(item.get("dashed"))))
        label = str(item.get("label") or "").strip()
        if label:
            occupied = [
                node for node in [*structure, *overlay]
                if node.get("type") not in {"section", "connector"}
                and not str(node.get("id") or "").startswith("ue-component-marker-")
            ]
            overlay.append(_place_edge_label(
                f"ue-edge-label-{edge_id}", label, points, occupied,
                (
                    int(item.get("labelX")), int(item.get("labelY"))
                ) if item.get("labelX") is not None and item.get("labelY") is not None else None,
            ))
    for note_index, item in enumerate(spec.get("notes") or [], 1):
        if not isinstance(item, dict):
            continue
        overlay.append(_note(
            f"ue-note-{note_index}", str(item.get("text") or ""),
            int(item.get("x") or 0), int(item.get("y") or 0), int(item.get("width") or 360),
        ))
    return NativeWhiteboard({"nodes": structure}, {"nodes": overlay}, tuple(images))


def _accepted_planning_whiteboard(job: dict[str, Any], spec: dict[str, Any]) -> NativeWhiteboard:
    screens = [item for item in spec.get("screens") or [] if isinstance(item, dict)]
    if screens:
        if len(screens) < 10:
            raise ValueError("accepted planning sketch must preserve the observed page/state map")
        sections = [item for item in spec.get("sections") or [] if isinstance(item, dict)]
        section_ids = {str(item.get("id") or "") for item in sections}
        if not section_ids:
            raise ValueError("accepted planning sketch requires functional sections")
        frame_by_id = {
            str(frame.get("id") or ""): frame
            for frame in job.get("frames") or []
            if isinstance(frame, dict)
        }
        content: list[dict[str, Any]] = []
        overlay: list[dict[str, Any]] = []
        images: list[BoardImage] = []
        child_ids: dict[str, list[str]] = {section_id: [] for section_id in section_ids}
        positioned: dict[str, dict[str, int]] = {}
        # GVE16 uses a page/state specification map: screenshots remain primary
        # and the composition copy sits beside each screenshot.  A compact
        # three-column snake layout keeps the remote default zoom readable and
        # gives every transition a clear horizontal/vertical exit.
        card_width, card_height = 900, 650
        column_gap, row_gap = 80, 70
        section_gap, section_top = 100, 110
        board_width = card_width * 3 + column_gap * 2
        section_layout: dict[str, dict[str, int]] = {}
        cursor_y = 100
        for section in sections:
            current_section_id = str(section.get("id") or "")
            count = sum(1 for screen in screens if str(screen.get("sectionId") or "") == current_section_id)
            rows = max(1, (count + 2) // 3)
            section_height = section_top + rows * card_height + max(0, rows - 1) * row_gap + 40
            section_layout[current_section_id] = {
                "x": 0, "y": cursor_y, "width": board_width, "height": section_height,
            }
            cursor_y += section_height + section_gap
        page_title_offset = 48
        page_content_offset = 118
        section_screen_index: dict[str, int] = {section_id: 0 for section_id in section_ids}
        for index, screen in enumerate(screens, 1):
            screen_id = str(screen.get("id") or index)
            section_id = str(screen.get("sectionId") or "")
            frame_id = str(screen.get("frameId") or "")
            if section_id not in section_ids or frame_id not in frame_by_id:
                raise ValueError(f"planning screen requires valid section and frame: {screen_id}")
            local_index = section_screen_index[section_id]
            section_screen_index[section_id] += 1
            row, position = divmod(local_index, 3)
            column = position if row % 2 == 0 else 2 - position
            section_box = section_layout[section_id]
            x = section_box["x"] + column * (card_width + column_gap)
            y = section_box["y"] + section_top + row * (card_height + row_gap)
            width, height = card_width, card_height
            positioned[screen_id] = {"x": x, "y": y, "width": width, "height": height}
            title = _note(
                f"planning-title-{screen_id}",
                str(screen.get("title") or f"状态 {index}"),
                x + 20, y + page_title_offset, width - 40,
            )
            image_width, image_height = _fit_original_ratio(frame_by_id[frame_id], 240, 450)
            image_node = {
                "id": f"planning-image-{screen_id}", "type": "image",
                "x": x + 28, "y": y + page_content_offset,
                "width": image_width, "height": image_height,
                "style": {"border_style": "none"},
                "planningScreenId": screen_id,
            }
            items = [str(value).strip() for value in screen.get("items") or [] if str(value).strip()]
            copy_x = image_node["x"] + image_node["width"] + 28
            copy = _text_node(
                f"planning-copy-{screen_id}",
                "界面构成\n" + "\n".join(f"• {value}" for value in items),
                copy_x, y + page_content_offset, x + width - 28 - copy_x, size=14,
            )
            copy.update({"planningScreenId": screen_id, "pageComposition": True})
            content.extend([title, image_node, copy])
            child_ids[section_id].extend([title["id"], image_node["id"], copy["id"]])
            images.append(BoardImage(
                frame_id,
                _frame_image_path(job, frame_by_id[frame_id], frame_id),
                image_node,
            ))
        section_nodes = [
            _section_box(
                f"planning-section-{str(item.get('id') or '')}",
                str(item.get("title") or ""),
                section_layout[str(item.get("id") or "")]["x"],
                section_layout[str(item.get("id") or "")]["y"],
                section_layout[str(item.get("id") or "")]["width"],
                section_layout[str(item.get("id") or "")]["height"],
                child_ids[str(item.get("id") or "")],
            )
            for item in sections
        ]
        header = _note(
            "planning-board-header",
            "策划草图｜已确认页面与状态、界面构成及画面衔接（各分区可独立移动）",
            0, 0, board_width,
        )
        for edge_index, edge in enumerate(spec.get("edges") or [], 1):
            if not isinstance(edge, dict):
                continue
            source_id, target_id = str(edge.get("from") or ""), str(edge.get("to") or "")
            if source_id not in positioned or target_id not in positioned:
                raise ValueError(f"planning edge references missing screen: {source_id}->{target_id}")
            source, target = positioned[source_id], positioned[target_id]
            if edge.get("route") == "vertical":
                start = (source["x"] + source["width"] // 2, source["y"] + source["height"])
                end = (target["x"] + target["width"] // 2, target["y"])
            elif target["x"] < source["x"]:
                start = (source["x"], source["y"] + source["height"] // 2)
                end = (target["x"] + target["width"], target["y"] + target["height"] // 2)
            else:
                start = (source["x"] + source["width"], source["y"] + source["height"] // 2)
                end = (target["x"], target["y"] + target["height"] // 2)
            connector_id = str(edge.get("id") or edge_index)
            overlay.extend(_orthogonal_connectors(
                f"planning-{connector_id}", start, end,
                dashed=bool(edge.get("dashed")),
            ))
            label = str(edge.get("label") or "").strip()
            if label:
                overlay.append(_edge_label(
                    f"planning-edge-label-{connector_id}", label,
                    round((start[0] + end[0]) / 2) - 50,
                    round((start[1] + end[1]) / 2) - 32,
                ))
        for note_index, note in enumerate(spec.get("notes") or [], 1):
            if isinstance(note, dict):
                overlay.append(_note(
                    f"planning-note-{note_index}", str(note.get("text") or ""),
                    int(note.get("x") or 0), int(note.get("y") or 0), int(note.get("width") or 360),
                ))
        return NativeWhiteboard({"nodes": [*section_nodes, header, *content]}, {"nodes": overlay}, tuple(images))

    cards = [item for item in spec.get("cards") or [] if isinstance(item, dict)]
    if len(cards) < 4:
        raise ValueError("accepted planning sketch must contain at least four presentation cards")
    frame_by_id = {str(frame.get("id") or ""): frame for frame in job.get("frames") or [] if isinstance(frame, dict)}
    structure: list[dict[str, Any]] = []
    overlay: list[dict[str, Any]] = []
    images: list[BoardImage] = []
    card_width, card_height, x_gap, y_gap = 900, 760, 60, 60
    top_safe_area = 100
    structure.append(_note(
        "planning-board-header",
        "策划草图｜页面构成、截图证据与交互说明（各分区可独立移动）",
        0,
        0,
        card_width * 2 + x_gap,
    ))
    for index, card in enumerate(cards, 1):
        column, row = (index - 1) % 2, (index - 1) // 2
        x, y = column * (card_width + x_gap), top_safe_area + row * (card_height + y_gap)
        card_id = str(card.get("id") or index)
        children: list[str] = []
        title = _note(f"planning-title-{card_id}", str(card.get("title") or ""), x + 24, y + 54, card_width - 48)
        structure.append(title)
        children.append(title["id"])
        frame_ids = [str(value) for value in card.get("frameIds") or [] if str(value) in frame_by_id]
        image_width = 170 if len(frame_ids) >= 4 else 210
        image_height = 302 if len(frame_ids) >= 4 else 374
        image_gap = 18
        image_y = y + 148
        for frame_index, frame_id in enumerate(frame_ids, 1):
            image_x = x + 32 + (frame_index - 1) * (image_width + image_gap)
            node = {
                "id": f"planning-image-{card_id}-{frame_index}", "type": "image",
                "x": image_x, "y": image_y, "width": image_width, "height": image_height,
                "style": {"border_style": "none"},
            }
            structure.append(node)
            children.append(node["id"])
            images.append(BoardImage(frame_id, _frame_image_path(job, frame_by_id[frame_id], frame_id), node))
            marker = _marker(f"planning-marker-{card_id}-{frame_index}", frame_index, image_x + 8, image_y + 8)
            overlay.append(marker)
        copy = "\n".join(f"• {str(value)}" for value in card.get("bullets") or [] if str(value).strip())
        copy_y = y + (500 if len(frame_ids) >= 4 else 540)
        copy_node = _text_node(f"planning-copy-{card_id}", copy, x + 32, copy_y, card_width - 64, size=14)
        structure.append(copy_node)
        children.append(copy_node["id"])
        structure.insert(
            len(structure) - len(children),
            _section_box(f"planning-section-{card_id}", str(card.get("title") or ""), x, y, card_width, card_height, children),
        )
    return NativeWhiteboard({"nodes": structure}, {"nodes": overlay}, tuple(images))


def _accepted_competitor_whiteboard(job: dict[str, Any], spec: dict[str, Any]) -> NativeWhiteboard:
    cards = [item for item in spec.get("cards") or [] if isinstance(item, dict)]
    frame_by_id = {str(frame.get("id") or ""): frame for frame in job.get("frames") or [] if isinstance(frame, dict)}
    if not cards:
        cards = [{"frameId": frame_id, "title": f"原始画面 {index}"} for index, frame_id in enumerate(frame_by_id, 1)]
    structure: list[dict[str, Any]] = []
    images: list[BoardImage] = []
    # GVE16's competitor board is an unannotated source-image wall.  Captions,
    # deductions and implementation notes belong to the planning board/body,
    # otherwise this becomes a second PRD instead of a visual reference.
    image_width, image_height, columns = 300, 560, 5
    column_gap, row_gap = 48, 80
    top_safe_area = 100
    structure.append(_note(
        "competitor-board-header",
        "竞品参考｜原始画面墙（仅核对视觉结构与信息密度）",
        0,
        0,
        image_width * columns + column_gap * (columns - 1),
    ))
    for index, card in enumerate(cards, 1):
        frame_id = str(card.get("frameId") or "")
        if frame_id not in frame_by_id:
            continue
        column, row = (index - 1) % columns, (index - 1) // columns
        x, y = column * (image_width + column_gap), top_safe_area + row * (image_height + row_gap)
        card_id = str(card.get("id") or index)
        image_node = {
            "id": f"competitor-image-{card_id}", "type": "image",
            "x": x, "y": y, "width": image_width, "height": image_height,
            "style": {"border_style": "none"},
        }
        image_node.update({"referenceIndex": index, "rawReferenceImage": True})
        structure.append(image_node)
        images.append(BoardImage(frame_id, _frame_image_path(job, frame_by_id[frame_id], frame_id), image_node))
    return NativeWhiteboard({"nodes": structure}, {"nodes": []}, tuple(images))


def compile_accepted_delivery_whiteboards(job: dict[str, Any], job_dir: Path | None = None) -> tuple[NamedWhiteboard, ...]:
    """Compile only the accepted planning sketch board."""
    accepted = job.get("acceptedPublication") if isinstance(job.get("acceptedPublication"), dict) else {}
    payload = accepted.get("nativeBoards") if isinstance(accepted.get("nativeBoards"), dict) else {}
    planning_spec = payload.get("planningSketch") if isinstance(payload.get("planningSketch"), dict) else {}
    board = _accepted_planning_whiteboard(job, planning_spec) if planning_spec else compile_gve16_whiteboard(job)
    return (NamedWhiteboard("planning", "策划草图", board),)


def _shared_screenshot_size(screenshot: dict[str, Any]) -> tuple[int | float, int | float]:
    """Fit known source dimensions without changing their aspect ratio."""
    width, height = screenshot.get("sourceWidth", 0), screenshot.get("sourceHeight", 0)
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        return 270, 500
    divisor = gcd(width, height)
    unit_width, unit_height = width // divisor, height // divisor
    multiplier = min(360 // unit_width, 500 // unit_height)
    if multiplier >= 1:
        return unit_width * multiplier, unit_height * multiplier
    scale = min(360 / width, 500 / height)
    return round(width * scale, 6), round(height * scale, 6)


def _page_copy(groups: list[dict[str, Any]]) -> str:
    lines: list[str] = []

    def add_items(items: list[dict[str, Any]], depth: int) -> None:
        for item in items:
            lines.append(f"{'  ' * depth}• {str(item.get('text') or '')}")
            add_items(list(item.get("children") or []), depth + 1)

    for group in groups:
        lines.append(str(group.get("title") or ""))
        add_items(list(group.get("items") or []), 0)
    return "\n".join(line for line in lines if line)


def compile_gve16_whiteboard(job: dict[str, Any]) -> NativeWhiteboard:
    """Compile the shared page-spec model into a native, screenshot-first board."""
    from .planning_board_model import build_planning_board_model

    board_model = build_planning_board_model(job)
    pages = list(board_model.get("pages") or [])
    tree_mode = any(bool((page.get("topology") or {}).get("branching")) for page in pages)
    if tree_mode:
        pages.sort(key=lambda page: (
            int((page.get("topology") or {}).get("depth", 0)),
            float((page.get("topology") or {}).get("column", 0)),
        ))
    structure: list[dict[str, Any]] = []
    images: list[BoardImage] = []
    markers: list[dict[str, Any]] = []
    page_bounds: dict[str, tuple[int, int, int, int]] = {}
    frame_by_id = {str(frame.get("id") or ""): frame for frame in job.get("frames") or [] if isinstance(frame, dict)}
    base_page_x, title_width, copy_width = 1100, 980, 500
    page_x = base_page_x
    note_x = base_page_x + 1040
    y = 80
    active_depth = -1
    depth_y = 80
    depth_max_height = 0

    for page_index, page in enumerate(pages, 1):
        topology = page.get("topology") if isinstance(page.get("topology"), dict) else {}
        if tree_mode:
            depth = int(topology.get("depth", 0))
            if depth != active_depth:
                if active_depth >= 0:
                    depth_y += depth_max_height + 120
                active_depth = depth
                depth_max_height = 0
            y = depth_y
            page_x = round(base_page_x + float(topology.get("column", 0)) * 1500)
        else:
            page_x = base_page_x
        content_x, copy_x, note_x = page_x + 24, page_x + 440, page_x + 1040
        page_id = str(page.get("id") or page_index)
        page_node_start = len(structure)
        title = _note(f"page-title-{page_id}", str(page.get("title") or ""), page_x, y, title_width)
        structure.append(title)
        content_y = y + title["height"] + 24
        screenshots = list(page.get("screenshots") or [])
        subflow = page.get("subflow") if isinstance(page.get("subflow"), dict) else {}
        states = sorted((state for state in subflow.get("states") or [] if isinstance(state, dict)), key=lambda state: state.get("order", 0))
        state_by_frame = {str(state.get("frameId") or ""): state for state in states}
        steps = list(subflow.get("steps") or [])
        image_y = content_y
        image_bottom = content_y
        for screenshot_index, screenshot in enumerate(screenshots, 1):
            frame_id = str(screenshot.get("frameId") or "")
            state = state_by_frame.get(frame_id)
            if state:
                state_label = _text_node(
                    f"page-subflow-state-{page_id}-{screenshot_index}", str(state.get("title") or ""),
                    content_x, image_y, 360, size=13,
                )
                structure.append(state_label)
                image_y += state_label["height"] + 8
            image_width, image_height = _shared_screenshot_size(screenshot)
            node = {
                "id": f"page-image-{page_id}-{screenshot_index}", "type": "image",
                "x": content_x, "y": image_y, "width": image_width, "height": image_height,
                "style": {"border_style": "none"},
            }
            structure.append(node)
            image_path = _frame_image_path(job, frame_by_id.get(frame_id, {}), frame_id)
            images.append(BoardImage(frame_id, image_path, node))
            if board_model.get("showUeMarkers") is True:
                markers.append(_marker(f"marker-{page_id}-{screenshot_index}", len(markers) + 1, node["x"] + 12, node["y"] + 12))
            image_bottom = image_y + image_height
            image_y = image_bottom + 20
            if screenshot_index < len(screenshots) and screenshot_index <= len(steps):
                step = steps[screenshot_index - 1]
                center_x = content_x + image_width // 2
                edge_end = image_y + 36
                markers.append(_connector(
                    f"page-subflow-{str(step.get('id') or screenshot_index)}",
                    (center_x, image_bottom + 4), (center_x, edge_end), dashed=False, end_arrow=True,
                ))
                markers.append(_text_node(
                    f"page-subflow-label-{str(step.get('id') or screenshot_index)}",
                    str(step.get("label") or ""), center_x + 14, image_bottom + 10, 220, size=12,
                ))
                image_y = edge_end + 16
                image_bottom = image_y

        copy = _text_node(f"page-copy-{page_id}", _page_copy(list(page.get("groups") or [])), copy_x, content_y, copy_width, size=14)
        structure.append(copy)
        crop_y = copy["y"] + copy["height"] + 20
        crop_bottom = crop_y
        for crop_index, crop in enumerate(page.get("detailCrops") or [], 1):
            column = (crop_index - 1) % 2
            row = (crop_index - 1) // 2
            node_x = copy_x + column * 250
            node_y = crop_y + row * 190
            crop_id = str(crop.get("id") or crop_index)
            crop_title = _text_node(f"page-detail-crop-title-{page_id}-{crop_id}", str(crop.get("title") or ""), node_x, node_y, 230, size=12)
            structure.append(crop_title)
            node = {
                "id": f"page-detail-crop-{page_id}-{crop_id}", "type": "image",
                "x": node_x, "y": node_y + crop_title["height"], "width": 230, "height": 130,
                "crop": dict(crop.get("bounds") or {}),
                "style": {"border_style": "none"},
            }
            structure.append(node)
            frame_id = str(crop.get("frameId") or "")
            image_path = _frame_image_path(job, frame_by_id.get(frame_id, {}), frame_id)
            images.append(BoardImage(f"{frame_id}#{crop_id}", image_path, node))
            crop_bottom = max(crop_bottom, node["y"] + node["height"])
        note_y = content_y
        note_bottom = content_y
        for note_index, note in enumerate(page.get("notes") or [], 1):
            note_node = _note(f"page-note-{page_id}-{note_index}", str(note.get("text") or ""), note_x, note_y, 360)
            structure.append(note_node)
            note_y += note_node["height"] + 16
            note_bottom = note_y - 16

        page_bottom = max(image_bottom, copy["y"] + copy["height"], crop_bottom, note_bottom, content_y) + 40
        page_children = [str(node.get("id")) for node in structure[page_node_start:] if node.get("id")]
        page_section = _section(f"section-page-{page_id}", str(page.get("title") or ""), page_x - 32, 1464)
        page_section.update({"y": y - 24, "height": page_bottom - y + 48, "children": page_children})
        structure.insert(page_node_start, page_section)
        page_bounds[page_id] = (page_x, y, page_x + title_width, page_bottom)
        if tree_mode:
            depth_max_height = max(depth_max_height, page_bottom - y)
        else:
            y = page_bottom + 90

    if tree_mode:
        y = depth_y + depth_max_height + 120
        page_x = base_page_x
        note_x = base_page_x + 1040

    global_notes = [
        note for note in board_model.get("notes") or []
        if isinstance(note, dict) and not str(note.get("pageId") or "")
    ]
    for note_index, note in enumerate(global_notes, 1):
        note_node = _note(f"board-note-{note_index}", str(note.get("text") or ""), page_x, y, title_width)
        structure.append(note_node)
        y += note_node["height"] + 16

    overlay: list[dict[str, Any]] = markers
    valid_relations = [
        relation for relation in board_model.get("relations") or []
        if str(relation.get("sourcePageId") or "") in page_bounds
        and str(relation.get("targetPageId") or "") in page_bounds
    ]
    incidents: dict[str, list[int]] = {page_id: [] for page_id in page_bounds}
    for relation_index, relation in enumerate([] if tree_mode else valid_relations):
        incidents[str(relation.get("sourcePageId"))].append(relation_index)
        incidents[str(relation.get("targetPageId"))].append(relation_index)
    anchors: dict[tuple[str, int], int] = {}
    for page_id, relation_indexes in incidents.items():
        _, page_top, _, page_bottom = page_bounds[page_id]
        for anchor_slot, relation_index in enumerate(relation_indexes, 1):
            anchors[(page_id, relation_index)] = page_top + round(
                (page_bottom - page_top) * anchor_slot / (len(relation_indexes) + 1)
            )
    has_page_notes = any(page.get("notes") for page in pages)
    notes_right = note_x + 360 if has_page_notes else max((bounds[2] for bounds in page_bounds.values()), default=0)
    page_has_notes = {
        str(page.get("id") or page_index): bool(page.get("notes"))
        for page_index, page in enumerate(pages, 1)
    }
    lane_counts = {True: 0, False: 0}

    for relation_index, relation in enumerate([] if tree_mode else valid_relations):
        source_id = str(relation.get("sourcePageId"))
        target_id = str(relation.get("targetPageId"))
        source_left, source_top, source_right, source_bottom = page_bounds[source_id]
        target_left, target_top, target_right, target_bottom = page_bounds[target_id]
        # A right-side route would have to cross the note column before it
        # reaches an exterior lane. Keep relations incident to noted pages on
        # the left, and allocate each side's lanes independently.
        left_lane = (
            page_has_notes.get(source_id, False)
            or page_has_notes.get(target_id, False)
            or relation_index % 2 == 0
        )
        lane_slot = lane_counts[left_lane]
        lane_counts[left_lane] += 1
        lane_x = (min(source_left, target_left) - 100 - lane_slot * 300 if left_lane
                  else max(source_right, target_right, notes_right) + 100 + lane_slot * 300)
        start_x = source_left if left_lane else source_right
        end_x = target_left if left_lane else target_right
        start_y = anchors[(source_id, relation_index)]
        end_y = anchors[(target_id, relation_index)]
        dashed = relation.get("lineStyle") == "dashed"
        relation_id = str(relation.get("id") or relation_index + 1)
        # Feishu's published contract supports straight connectors. Compose a
        # three-segment exterior route instead of emitting an unverified elbow.
        overlay.extend([
            _connector(f"page-relation-{relation_id}-1", (start_x, start_y), (lane_x, start_y), dashed=dashed, end_arrow=False),
            _connector(f"page-relation-{relation_id}-2", (lane_x, start_y), (lane_x, end_y), dashed=dashed, end_arrow=False),
            _connector(f"page-relation-{relation_id}-3", (lane_x, end_y), (end_x, end_y), dashed=dashed, end_arrow=True),
        ])
        label_x = lane_x - 236 if left_lane else lane_x + 16
        overlay.append(_text_node(f"page-relation-label-{relation_id}", str(relation.get("label") or ""), label_x, min(start_y, end_y) + 16, 220, size=12))

    if tree_mode:
        for relation_index, relation in enumerate(valid_relations, 1):
            source_id = str(relation.get("sourcePageId") or "")
            target_id = str(relation.get("targetPageId") or "")
            source_left, source_top, source_right, source_bottom = page_bounds[source_id]
            target_left, target_top, target_right, target_bottom = page_bounds[target_id]
            start = ((source_left + source_right) // 2, source_bottom)
            end = ((target_left + target_right) // 2, target_top)
            middle_y = start[1] + max(34, (end[1] - start[1]) // 2)
            dashed = relation.get("lineStyle") == "dashed"
            relation_id = str(relation.get("id") or relation_index)
            segments = [
                _connector(f"tree-relation-{relation_id}-1", start, (start[0], middle_y), dashed=dashed, end_arrow=False),
                _connector(f"tree-relation-{relation_id}-2", (start[0], middle_y), (end[0], middle_y), dashed=dashed, end_arrow=False),
                _connector(f"tree-relation-{relation_id}-3", (end[0], middle_y), end, dashed=dashed, end_arrow=True),
            ]
            for segment in segments:
                segment["treeRelation"] = True
            overlay.extend(segments)
            overlay.append(_text_node(
                f"tree-relation-label-{relation_id}", str(relation.get("label") or ""),
                round((start[0] + end[0]) / 2) + 12, middle_y - 28, 220, size=12,
            ))

    return NativeWhiteboard({"nodes": structure}, {"nodes": overlay}, tuple(images))
