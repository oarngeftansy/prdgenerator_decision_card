from __future__ import annotations

import hashlib
import base64
import json
import re
from dataclasses import dataclass
from datetime import date
from html import escape
from pathlib import Path
from typing import Any

from .feishu_native_board import (
    NamedWhiteboard,
    NativeWhiteboard,
    compile_accepted_delivery_whiteboards,
    compile_gve16_delivery_whiteboards,
    compile_gve16_whiteboards,
)


@dataclass(frozen=True)
class EvidenceImage:
    frame_id: str
    path: Path
    anchor_text: str
    caption: str


@dataclass(frozen=True)
class RenderedFeishuDocument:
    title: str
    xml: str
    mermaid: str
    board_svg: str
    board_format: str
    evidence_images: tuple[EvidenceImage, ...]
    content_fingerprint: str
    native_boards: tuple[NamedWhiteboard, ...]
    embedded_whiteboard_count: int = 0
    preview_order: tuple[dict[str, Any], ...] = ()
    embedded_whiteboards: tuple[tuple[str, str], ...] = ()
    preview_board_svgs: tuple[tuple[str, str], ...] = ()

    @property
    def native_board(self) -> NativeWhiteboard:
        return next(item.board for item in self.native_boards if item.key == "planning")


def _text(value: Any) -> str:
    if value in (None, ""):
        return "视频未明确展示"
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _svg_text_block(text: Any, x: int, y: int, font_size: int, max_chars: int, max_lines: int, **attributes: Any) -> str:
    value = " ".join(_text(text).split())
    lines = [value[index:index + max_chars] for index in range(0, len(value), max_chars)] or [""]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1][:-1] + "…" if lines[-1] else "…"
    attrs = " ".join(f'{key.replace("_", "-")}="{escape(str(val), quote=True)}"' for key, val in attributes.items())
    tspans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else round(font_size * 1.35)}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text x="{x}" y="{y}" font-size="{font_size}" {attrs}>{tspans}</text>'


def _svg_rule_card(card: dict[str, Any], x: int, y: int, width: int) -> str:
    items = card.get("items") or []
    lines = [f'{item.get("label")}：{item.get("text")}' for item in items]
    max_chars = max(8, (width - 28) // 13)
    height = max(82, 34 + len(lines) * 44)
    content = [
        f'<g data-node-kind="rule-card"><rect x="{x}" y="{y}" width="{width}" height="{height}" rx="8" fill="#F8F9FA" stroke="#D0D3D8"/>'
    ]
    for index, line in enumerate(lines):
        content.append(_svg_text_block(f"• {line}", x + 14, y + 27 + index * 44, 13, max_chars, 2, fill="#3A3F47"))
    content.append("</g>")
    return "".join(content)


def _confirmed_text(value: Any) -> str:
    """Keep unobserved review fields explicit instead of turning them into facts."""
    if value is None or value == "" or (isinstance(value, str) and value.strip().lower() in {"unknown", "待确认"}):
        return "待确认"
    return _text(value)


def _label(value: Any) -> str:
    return re.sub(r"[\[\]{}()\"\n\r]", " ", _text(value)).strip()


def render_ue_flow(model: dict[str, Any]) -> str:
    gameplay = model.get("mode") == "gameplay"
    edges = model.get("designHandoff", {}).get("flowEdges") or []
    lines = ["flowchart LR"]
    for index, edge in enumerate(edges, 1):
        prefix = f"N{index:03d}"
        before = _label(edge.get("from"))
        action = _label(edge.get("trigger"))
        after = _label(edge.get("to"))
        action_name = "玩家操作" if gameplay else "用户输入"
        response_name = "玩法状态" if gameplay else "系统响应"
        lines.extend([
            f'  {prefix}A["{before}"] --> {prefix}B["{action_name}：{action}"]',
            f'  {prefix}B --> {prefix}C["{response_name}：{after}"]',
        ])
    if not edges:
        lines.append('  EMPTY["视频未明确展示完整流程"]')
    return "\n".join(lines)


def _frame_lookup(job: dict[str, Any], job_dir: Path) -> dict[str, Path]:
    return {image.frame_id: image.path for image in _evidence_images(job, job_dir)}


def _svg_image(path: Path) -> str:
    if not path.is_file():
        return ""
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def render_ue_board_svg(job: dict[str, Any], job_dir: Path) -> tuple[str, tuple[EvidenceImage, ...]]:
    """Render a screenshot-first board; scenes remain evidence, never board chapters."""
    from .planning_board_model import build_planning_board_model
    board = build_planning_board_model(job)
    if board.get("pages"):
        return _render_shared_planning_board_svg(job, job_dir, board)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1380" height="700" viewBox="0 0 1380 700">'
        '<g data-node-kind="empty-page-board"><rect x="90" y="50" width="1120" height="180" rx="16" '
        'fill="#F5F6F7" stroke="#D0D3D8"/><text x="650" y="145" text-anchor="middle" '
        'font-size="20" fill="#646A73">暂无已确认页面</text></g></svg>'
    )
    return svg, ()


def render_competitor_board_svg(job: dict[str, Any], job_dir: Path) -> str:
    """Render user-provided screenshots as a distinct competitor evidence gallery."""
    frame_paths = _frame_lookup(job, job_dir)
    frames = [item for item in job.get("frames") or [] if str(item.get("id") or "") in frame_paths]
    if not frames:
        return ""
    review = job.get("reviewModel") or {}
    stage_by_frame: dict[str, str] = {}
    for stage in review.get("stages") or []:
        title = _text(stage.get("name") or "竞品页面")
        frame_ids = list(stage.get("sourceFrameIds") or [])
        frame_ids.extend(str(item.get("frameId") or "") for item in stage.get("representativeFrames") or [])
        for frame_id in frame_ids:
            stage_by_frame.setdefault(frame_id, title)
    insights = ((job.get("reviewModel") or {}).get("referenceBoards") or {}).get("competitor", {}).get("insights") or {}
    columns, card_width, gap, margin = 3, 370, 28, 36
    image_width, image_height = 220, 390
    rows = (len(frames) + columns - 1) // columns
    width = margin * 2 + columns * card_width + (columns - 1) * gap
    row_height, card_height = 750, 720
    height = 110 + rows * row_height + 30
    nodes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="{width}" height="{height}" fill="#F5F6F7"/>',
        '<text x="36" y="44" font-size="26" font-weight="700" fill="#1F2329">竞品参考</text>',
        '<text x="36" y="76" font-size="15" fill="#646A73">用户提供的原始截图，仅作为界面、反馈和可见数值的证据；隐藏规则仍需其他来源支持。</text>',
    ]
    for index, frame in enumerate(frames):
        frame_id = str(frame.get("id") or "")
        x = margin + (index % columns) * (card_width + gap)
        y = 100 + (index // columns) * row_height
        href = _svg_image(frame_paths[frame_id])
        title = stage_by_frame.get(frame_id, f"竞品画面 {index + 1}")
        insight = insights.get(frame_id) if isinstance(insights.get(frame_id), dict) else {}
        title_lines = _page_copy_lines(title, 20)[:2]
        observed = _page_copy_lines(insight.get("observed") or "保留原图用于核对可见页面状态。", 24)[:3]
        adopted = _page_copy_lines(insight.get("adopted") or "作为对应策划节点与玩法规则的视觉依据。", 24)[:3]
        excluded = _page_copy_lines(insight.get("excluded") or "不据此推导隐藏公式或概率。", 24)[:2]
        nodes.extend([
            f'<g data-node-kind="competitor-reference" data-source-index="{index + 1}">',
            f'<rect x="{x}" y="{y}" width="{card_width}" height="{card_height}" rx="12" fill="#FFFFFF" stroke="#D0D3D8"/>',
            _svg_full_text_block(title_lines, x + 18, y + 31, 16, font_weight="700", fill="#1F2329", data_copy_kind="title"),
            f'<image x="{x + 25}" y="{y + 70}" width="{image_width}" height="{image_height}" preserveAspectRatio="xMidYMid meet" href="{href}"/>',
            f'<text x="{x + 18}" y="{y + 480}" font-size="13" font-weight="700" fill="#1F2329">可见信息</text>',
            _svg_full_text_block(observed, x + 18, y + 501, 13, fill="#4E5969", data_copy_kind="observed"),
            f'<text x="{x + 18}" y="{y + 558}" font-size="13" font-weight="700" fill="#1F2329">对本方案的采用点</text>',
            _svg_full_text_block(adopted, x + 18, y + 579, 13, fill="#4E5969", data_copy_kind="adopted"),
            f'<text x="{x + 18}" y="{y + 638}" font-size="12" font-weight="700" fill="#8F959E">推导边界</text>',
            _svg_full_text_block(excluded, x + 18, y + 659, 12, fill="#8F959E", data_copy_kind="excluded"),
            '</g>',
        ])
    nodes.append('</svg>')
    return ''.join(nodes)


def render_native_whiteboard_svg(board: NativeWhiteboard, job_dir: Path) -> str:
    """Render the exact raw-board geometry for local visual acceptance."""
    structure = [item for item in board.structure.get("nodes", []) if isinstance(item, dict)]
    overlay = [item for item in board.overlay.get("nodes", []) if isinstance(item, dict)]
    nodes = [*structure, *overlay]
    if not nodes:
        return ""
    min_x = min(float(item.get("x") or 0) for item in nodes)
    min_y = min(float(item.get("y") or 0) for item in nodes)
    max_x = max(float(item.get("x") or 0) + float(item.get("width") or 0) for item in nodes)
    max_y = max(float(item.get("y") or 0) + float(item.get("height") or 0) for item in nodes)
    margin = 40
    width = max(300, round(max_x - min_x + margin * 2))
    height = max(300, round(max_y - min_y + margin * 2))
    tx, ty = margin - min_x, margin - min_y
    image_by_node = {str(item.node.get("id") or ""): item for item in board.images}

    def color(style: dict[str, Any], key: str, fallback: str) -> str:
        value = style.get(key)
        return str(value) if isinstance(value, str) and value else fallback

    def text_svg(item: dict[str, Any]) -> str:
        text = item.get("text") if isinstance(item.get("text"), dict) else {}
        value = str(text.get("text") or "")
        if not value:
            return ""
        font_size = int(text.get("font_size") or 14)
        raw_node_width = max(1, int(item.get("width") or 220))
        # Compact centered annotations (notably the numbered UE markers) must
        # use their real geometry. Expanding a 22px marker to the historical
        # 80px text minimum separates the digit from its red circle.
        node_width = (
            raw_node_width
            if text.get("horizontal_align") == "center"
            else max(80, raw_node_width)
        )
        lines: list[str] = []
        max_chars = max(6, node_width // max(font_size, 1))
        for raw_line in value.splitlines() or [""]:
            lines.extend(raw_line[index:index + max_chars] for index in range(0, len(raw_line), max_chars))
        x = float(item.get("x") or 0) + node_width / 2
        item_y = float(item.get("y") or 0)
        item_height = float(item.get("height") or 0)
        y = item_y + 24
        if text.get("vertical_align") == "mid" and item_height:
            y = item_y + item_height / 2 + font_size * 0.34
        align = "middle" if text.get("horizontal_align") == "center" else "start"
        if align == "start":
            x = float(item.get("x") or 0) + 12
        fill = color(text, "text_color", "#1F2329")
        weight = "700" if text.get("font_weight") in {"bold", "medium"} else "400"
        tspans = "".join(
            f'<tspan x="{x}" dy="{0 if index == 0 else round(font_size * 1.45)}">{escape(line)}</tspan>'
            for index, line in enumerate(lines)
        )
        return f'<text x="{x}" y="{y}" text-anchor="{align}" font-size="{font_size}" font-weight="{weight}" fill="{fill}">{tspans}</text>'

    def node_svg(item: dict[str, Any]) -> str:
        node_type = str(item.get("type") or "")
        x, y = float(item.get("x") or 0), float(item.get("y") or 0)
        w, h = float(item.get("width") or 0), float(item.get("height") or 0)
        style = item.get("style") if isinstance(item.get("style"), dict) else {}
        fill = color(style, "fill_color", "#FFFFFF")
        stroke = color(style, "border_color", "#D0D3D8")
        if node_type == "section":
            title = escape(str((item.get("section") or {}).get("title") or ""))
            return (
                f'<g data-node-type="section"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="{stroke}"/>'
                f'<text x="{x + 18}" y="{y + 30}" font-size="18" font-weight="700" fill="#1F2329">{title}</text></g>'
            )
        if node_type == "connector":
            connector = item.get("connector") if isinstance(item.get("connector"), dict) else {}
            start = (connector.get("start") or {}).get("position") or {}
            end = (connector.get("end") or {}).get("position") or {}
            dashed = ' stroke-dasharray="9 7"' if style.get("border_style") == "dash" else ""
            marker = ' marker-end="url(#native-arrow)"' if (connector.get("end") or {}).get("arrow_style") != "none" else ""
            return (
                f'<line data-node-type="connector" x1="{float(start.get("x") or 0)}" y1="{float(start.get("y") or 0)}" '
                f'x2="{float(end.get("x") or 0)}" y2="{float(end.get("y") or 0)}" stroke="{color(style, "border_color", "#646A73")}" '
                f'stroke-width="2"{dashed}{marker}/>'
            )
        if node_type == "image":
            image = image_by_node.get(str(item.get("id") or ""))
            href = _svg_image(job_dir / image.image_path) if image else ""
            if href:
                return f'<image data-node-type="image" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid meet" href="{href}"/>'
            return f'<rect data-node-type="image-missing" x="{x}" y="{y}" width="{w}" height="{h}" rx="6" fill="#ECEEF2" stroke="#B8BDC7"/>'
        if node_type == "text_shape":
            return f'<g data-node-type="text_shape">{text_svg(item)}</g>'
        shape = str((item.get("composite_shape") or {}).get("type") or "round_rect")
        if shape == "diamond":
            points = f"{x + w / 2},{y} {x + w},{y + h / 2} {x + w / 2},{y + h} {x},{y + h / 2}"
            body = f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        elif shape == "ellipse":
            body = f'<ellipse cx="{x + w / 2}" cy="{y + h / 2}" rx="{w / 2}" ry="{h / 2}" fill="{fill}" stroke="{stroke}"/>'
        else:
            body = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'
        return f'<g data-node-type="{escape(node_type, quote=True)}">{body}{text_svg(item)}</g>'

    section_nodes = [item for item in structure if item.get("type") == "section"]
    connector_nodes = [item for item in overlay if item.get("type") == "connector"]
    # A Feishu raw structure update assigns the earlier node the higher
    # z-index. SVG paints later elements on top, so reverse structure content
    # here to make the local acceptance preview reproduce the remote board.
    content_nodes = list(reversed([
        item for item in structure if item.get("type") != "section"
    ]))
    overlay_nodes = [item for item in overlay if item.get("type") != "connector"]
    rendered_nodes = "".join(node_svg(item) for item in [*section_nodes, *connector_nodes, *content_nodes, *overlay_nodes])
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">'
        '<defs><marker id="native-arrow" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#646A73"/></marker></defs>'
        f'<rect width="100%" height="100%" fill="#FFFFFF"/><g transform="translate({tx} {ty})">{rendered_nodes}</g></svg>'
    )

def _page_copy_lines(value: Any, max_chars: int) -> list[str]:
    """Wrap all shared copy into visible SVG lines; never elide planner content."""
    compact = " ".join(_text(value).split())
    if compact in {"/", "||", "级", "伤害-", "次数:/", "见上方说明", "本页未单独展示"}:
        return []
    if re.fullmatch(r"(?:[^\w\u4e00-\u9fff]|[|/_-])+", compact):
        return []
    if re.search(r"可进行的操作[：:]\s*(?:未发生|没有发生|未检测到)(?:任何)?(?:点击|操作)(?:输入|事件|动作)?", compact):
        return []
    if re.search(r"数字快捷键(?:提示)?[^。；]*入口$", compact):
        return []
    if not compact:
        return []
    return [compact[index:index + max_chars] for index in range(0, len(compact), max_chars)]


def _svg_full_text_block(lines: list[str], x: int, y: int, font_size: int, **attributes: Any) -> str:
    attrs = " ".join(f'{key.replace("_", "-")}="{escape(str(value), quote=True)}"' for key, value in attributes.items())
    tspans = "".join(
        f'<tspan x="{x}" dy="{0 if index == 0 else round(font_size * 1.45)}">{escape(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text x="{x}" y="{y}" font-size="{font_size}" {attrs}>{tspans}</text>'


def _page_screenshot_size(screenshot: dict[str, Any]) -> tuple[int | float, int | float]:
    """Size screenshots only from their shared-model source dimensions."""
    source_width = int(screenshot["sourceWidth"])
    source_height = int(screenshot["sourceHeight"])
    if source_width <= 0 or source_height <= 0:
        # The SVG still preserves the image's intrinsic aspect ratio; no source-ratio
        # claim is made when the shared model explicitly records it as unknown.
        return 370, 300
    scale = min(370 / source_width, 300 / source_height)
    return max(1, round(source_width * scale, 6)), max(1, round(source_height * scale, 6))


def _nested_copy_rows(items: list[dict[str, Any]], max_chars: int, depth: int = 0) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    for item in items:
        available = max(12, max_chars - depth * 3)
        rows.append((depth, _page_copy_lines(f"• {_text(item.get('text'))}", available)))
        rows.extend(_nested_copy_rows(list(item.get("children") or []), max_chars, depth + 1))
    return rows


def _safe_local_image_uri(path: Path, job_dir: Path) -> str:
    try:
        resolved = path.resolve()
        resolved.relative_to(job_dir.resolve())
    except (OSError, ValueError):
        return ""
    return _svg_image(resolved)


def _screenshot_href(
    screenshot: dict[str, Any], job: dict[str, Any], job_dir: Path, frame_paths: dict[str, Path],
) -> str:
    image_url = str(screenshot.get("imageUrl") or "").strip()
    if re.fullmatch(r"data:image/(?:png|jpeg|jpg|gif|webp);base64,[A-Za-z0-9+/=\s]+", image_url, flags=re.I):
        return image_url
    artifact_prefix = f"/artifacts/{job.get('id')}/"
    candidates: list[Path] = []
    if image_url.startswith(artifact_prefix):
        candidates.append(job_dir / image_url[len(artifact_prefix):])
    elif image_url and not image_url.startswith(("/", "\\")) and ":" not in image_url:
        candidates.append(job_dir / image_url)
    frame_id = str(screenshot.get("frameId") or "")
    if frame_id in frame_paths:
        candidates.append(frame_paths[frame_id])
    for candidate in candidates:
        if uri := _safe_local_image_uri(candidate, job_dir):
            return uri
    return ""


def _render_shared_planning_board_svg(job: dict[str, Any], job_dir: Path, board: dict[str, Any]) -> tuple[str, tuple[EvidenceImage, ...]]:
    """Render canonical pages with complete copy, explicit notes, and isolated relation lanes."""
    frame_paths = _frame_lookup(job, job_dir)
    evidence = {image.frame_id: image for image in _evidence_images(job, job_dir)}
    selected: list[EvidenceImage] = []
    pages = list(board.get("pages") or [])
    tree_mode = any(bool((page.get("topology") or {}).get("branching")) for page in pages)
    if tree_mode:
        pages.sort(key=lambda page: (
            int((page.get("topology") or {}).get("depth", 0)),
            float((page.get("topology") or {}).get("column", 0)),
        ))
    page_order = {str(page.get("id") or ""): index for index, page in enumerate(pages)}
    candidates = [
        (original_index, relation)
        for original_index, relation in enumerate(board.get("relations") or [])
        if str(relation.get("sourcePageId") or "") in page_order
        and str(relation.get("targetPageId") or "") in page_order
    ]
    candidates.sort(key=lambda item: (
        -abs(page_order[str(item[1].get("sourcePageId"))] - page_order[str(item[1].get("targetPageId"))]),
        item[0],
    ))
    side_counts = {"left": 0, "right": 0}
    route_records: list[dict[str, Any]] = []
    tree_candidates = list(candidates)
    for route_index, (_, relation) in enumerate([] if tree_mode else candidates):
        side = "left" if route_index % 2 == 0 else "right"
        label_lines = _page_copy_lines(relation.get("label"), 16)
        # Relation labels render at 12px. Reserve one full em per character so
        # CJK/full-width glyphs cannot escape the viewBox; ASCII remains over-reserved.
        label_width = max(12, max(map(len, label_lines), default=1) * 12)
        route_records.append({
            "relation": relation, "side": side, "slot": side_counts[side],
            "labelLines": label_lines, "labelWidth": label_width,
        })
        side_counts[side] += 1

    max_label_width = {
        side: max((record["labelWidth"] for record in route_records if record["side"] == side), default=0)
        for side in ("left", "right")
    }
    # Labels sit 8px away from their own lane. Add another 24px so the
    # neighbouring lane/gap path never touches the independently measured bbox.
    lane_spacing = {side: max(56, max_label_width[side] + 32) for side in ("left", "right")}
    page_width = 1120
    base_page_x = 50 + side_counts["left"] * lane_spacing["left"] + max_label_width["left"]
    page_x = base_page_x
    copy_width = 610
    image_width = 410
    page_layout: dict[str, tuple[int, int, int]] = {}
    sections: list[str] = []
    y = 50
    active_depth = -1
    depth_y = 50
    depth_max_height = 0
    grid_row_y = 50
    grid_row_max_height = 0

    for page_index, page in enumerate(pages):
        topology = page.get("topology") if isinstance(page.get("topology"), dict) else {}
        if tree_mode:
            depth = int(topology.get("depth", 0))
            if depth != active_depth:
                if active_depth >= 0:
                    depth_y += depth_max_height + 120
                active_depth = depth
                depth_max_height = 0
            y = depth_y
            page_x = round(base_page_x + float(topology.get("column", 0)) * (page_width + 100))
        else:
            page_x = base_page_x + (page_index % 2) * (page_width + 70)
            y = grid_row_y
        copy_x = page_x + 470
        image_x = page_x + 24
        title = _text(page.get("title"))
        outer_title_lines = _page_copy_lines(title, 58)
        copy_title_lines = _page_copy_lines(title, 42)
        outer_title_height = len(outer_title_lines) * 29
        copy_header_height = max(42, 18 + len(copy_title_lines) * 22)
        content_top = y + 18 + outer_title_height + 16

        group_blocks: list[tuple[list[str], list[tuple[int, list[str]]]]] = []
        copy_body_height = 24
        for group in page.get("groups") or []:
            group_title_lines = _page_copy_lines(group.get("title"), 42)
            group_key = re.sub(r"\s+", "", _text(group.get("title")))
            group_items = [
                item for item in (group.get("items") or [])
                if re.sub(r"\s+", "", _text(item.get("text"))) != group_key
            ]
            rows = _nested_copy_rows(group_items, 42)
            group_blocks.append((group_title_lines, rows))
            copy_body_height += len(group_title_lines) * 21 + sum(len(lines) * 19 + 6 for _, lines in rows) + 12
        detail_crops = list(page.get("detailCrops") or [])
        crop_blocks = [(
            _page_copy_lines(crop.get("title"), 38),
            _page_copy_lines(crop.get("description"), 48),
        ) for crop in detail_crops]
        crop_section_height = (30 + sum(max(1, len(title_lines)) * 18 + len(description_lines) * 18 + 216 for title_lines, description_lines in crop_blocks)) if detail_crops else 0
        copy_body_height += crop_section_height
        copy_height = max(154, copy_header_height + copy_body_height)

        note_blocks = [_page_copy_lines(note.get("text"), 42) for note in page.get("notes") or []]
        notes_height = sum(24 + len(lines) * 20 for lines in note_blocks)

        screenshots = list(page.get("screenshots") or [])
        # A one-shot page already has its complete specification in the right
        # column.  Repeating the same copy below the image wastes space and
        # creates a false impression that it is a separate detail view.
        show_screenshot_details = len(screenshots) >= 2
        screenshot_nodes: list[str] = []
        screenshot_cursor = content_top
        screenshot_details = {
            str(item.get("frameId") or ""): item
            for item in page.get("screenshotDetails") or []
            if isinstance(item, dict)
        }
        subflow = page.get("subflow") if isinstance(page.get("subflow"), dict) else {}
        states = sorted((state for state in subflow.get("states") or [] if isinstance(state, dict)), key=lambda state: state.get("order", 0))
        state_by_frame = {str(state.get("frameId") or ""): state for state in states}
        steps = list(subflow.get("steps") or [])
        for screenshot_index, screenshot in enumerate(screenshots):
            frame_id = str(screenshot.get("frameId") or "")
            state = state_by_frame.get(frame_id)
            if state:
                state_lines = _page_copy_lines(state.get("title"), 34)
                screenshot_nodes.append(
                    f'<g data-node-kind="page-subflow-state" data-state-id="{escape(str(state.get("id") or ""), quote=True)}">'
                    f'{_svg_full_text_block(state_lines, image_x + 12, screenshot_cursor + 18, 14, font_weight="700", fill="#1F2329")}</g>'
                )
                screenshot_cursor += len(state_lines) * 20 + 8
            image_node_width, image_node_height = _page_screenshot_size(screenshot)
            image_node_x = image_x + (image_width - image_node_width) // 2
            href = _screenshot_href(screenshot, job, job_dir, frame_paths)
            common = (
                f'data-frame-id="{escape(frame_id, quote=True)}" data-source-width="{int(screenshot["sourceWidth"])}" '
                f'data-source-height="{int(screenshot["sourceHeight"])}"'
            )
            if href:
                screenshot_nodes.append(
                    f'<g data-node-kind="page-screenshot" {common}><image x="{image_node_x}" y="{screenshot_cursor}" '
                    f'width="{image_node_width}" height="{image_node_height}" preserveAspectRatio="xMidYMid meet" '
                    f'href="{escape(href, quote=True)}"/></g>'
                )
            else:
                screenshot_nodes.append(
                    f'<g data-node-kind="page-screenshot" data-image-state="unavailable" {common}>'
                    f'<rect x="{image_node_x}" y="{screenshot_cursor}" width="{image_node_width}" height="{image_node_height}" '
                    f'rx="8" fill="#ECEEF2" stroke="#B8BDC7"/>'
                    f'<text x="{image_node_x + image_node_width // 2}" y="{screenshot_cursor + image_node_height // 2}" '
                    f'text-anchor="middle" font-size="15" fill="#646A73">截图暂不可用</text></g>'
                )
            image_bottom_y = screenshot_cursor + image_node_height
            screenshot_cursor = image_bottom_y + 18
            if show_screenshot_details:
                detail = screenshot_details.get(frame_id) or {}
                explicit_detail_title = _page_copy_lines(detail.get("title"), 34)
                detail_title = explicit_detail_title or ["补充画面"]
                detail_rows: list[tuple[int, list[str]]] = []
                for detail_group in detail.get("groups") or []:
                    group_title = _page_copy_lines(detail_group.get("title"), 34)
                    if group_title:
                        detail_rows.append((0, group_title))
                    detail_rows.extend(_nested_copy_rows(list(detail_group.get("items") or []), 34))
                render_detail_card = bool(detail_rows or explicit_detail_title)
                detail_height = max(64, 30 + len(detail_title) * 19 + sum(len(lines) * 17 + 6 for _, lines in detail_rows)) if render_detail_card else 0
                if render_detail_card:
                    screenshot_nodes.append(
                    f'<g data-node-kind="page-screenshot-detail" data-frame-id="{escape(frame_id, quote=True)}">'
                    f'<rect x="{image_x}" y="{screenshot_cursor}" width="{image_width}" height="{detail_height}" rx="8" fill="#FFFFFF" stroke="#D0D3D8"/>'
                    f'{_svg_full_text_block(detail_title, image_x + 14, screenshot_cursor + 22, 13, font_weight="700", fill="#1F2329")}'
                    )
                    detail_y = screenshot_cursor + 32 + len(detail_title) * 19
                    for depth, lines in detail_rows:
                        screenshot_nodes.append(_svg_full_text_block(lines, image_x + 18 + depth * 18, detail_y, 12, fill="#596273"))
                        detail_y += len(lines) * 17 + 6
                    screenshot_nodes.append("</g>")
                    screenshot_cursor += detail_height + 18
            if screenshot_index < len(screenshots) - 1 and screenshot_index < len(steps):
                step = steps[screenshot_index]
                step_lines = _page_copy_lines(step.get("label"), 20)
                center_x = image_x + image_width // 2
                edge_end = screenshot_cursor + 36
                screenshot_nodes.append(
                    f'<g data-edge-kind="page-subflow-step" data-step-id="{escape(str(step.get("id") or ""), quote=True)}">'
                    f'<line x1="{center_x}" y1="{image_bottom_y + 4}" x2="{center_x}" y2="{edge_end}" stroke="#3370FF" stroke-width="2" marker-end="url(#arrow-muted)"/>'
                    f'{_svg_full_text_block(step_lines, center_x + 12, image_bottom_y + 22, 12, fill="#646A73")}</g>'
                )
                screenshot_cursor = edge_end + 14
            if frame_id in evidence and frame_id not in {item.frame_id for item in selected}:
                selected.append(evidence[frame_id])
        screenshot_height = max(154, screenshot_cursor - content_top - 18)

        right_height = copy_height + (16 + notes_height if note_blocks else 0)
        page_height = max(screenshot_height, right_height) + (content_top - y) + 24
        page_id_raw = str(page.get("id") or "")
        page_id = escape(page_id_raw, quote=True)
        sections.append(
            f'<g data-node-kind="page-spec" data-page-id="{page_id}"><rect x="{page_x}" y="{y}" width="{page_width}" '
            f'height="{page_height}" rx="16" fill="#F5F6F7" stroke="#8F959E"/>'
            f'{_svg_full_text_block(outer_title_lines, page_x + 24, y + 38, 20, font_weight="700", fill="#1F2329")}'
            f'<rect x="{copy_x}" y="{content_top}" width="{copy_width}" height="{copy_height}" rx="10" fill="#FFFFFF" stroke="#D0D3D8"/>'
            f'<rect x="{copy_x}" y="{content_top}" width="{copy_width}" height="{copy_header_height}" rx="10" fill="#FFF3BF"/>'
            f'{_svg_full_text_block(copy_title_lines, copy_x + 16, content_top + 27, 15, font_weight="700", fill="#594A00")}'
            f'<g data-node-kind="page-copy" data-page-id="{page_id}">'
        )
        copy_y = content_top + copy_header_height + 24
        for group_index, (group_title_lines, rows) in enumerate(group_blocks):
            sections.append(
                f'<g data-node-kind="page-group" data-group-index="{group_index}">'
                f'{_svg_full_text_block(group_title_lines, copy_x + 16, copy_y, 14, font_weight="700", fill="#1F2329")}'
            )
            copy_y += len(group_title_lines) * 21 + 5
            for depth, lines in rows:
                item_x = copy_x + 30 + depth * 24
                sections.append(
                    f'<g data-node-kind="page-copy-item" data-depth="{depth}">'
                    f'{_svg_full_text_block(lines, item_x, copy_y, 13, fill="#3A3F47")}</g>'
                )
                copy_y += len(lines) * 19 + 6
            sections.append("</g>")
            copy_y += 7
        if detail_crops:
            sections.append(
                f'<g data-node-kind="page-detail-crops">'
                f'{_svg_full_text_block(["局部细节"], copy_x + 16, copy_y + 2, 14, font_weight="700", fill="#1F2329")}'
            )
            copy_y += 28
            screenshot_by_frame = {str(item.get("frameId") or ""): item for item in page.get("screenshots") or []}
            crop_cursor = copy_y
            for crop_index, crop in enumerate(detail_crops):
                crop_x = copy_x + 16
                crop_y = crop_cursor
                crop_width, crop_height = copy_width - 32, 176
                bounds = crop.get("bounds") if isinstance(crop.get("bounds"), dict) else {}
                source_width, source_height = int(crop.get("sourceWidth") or 0), int(crop.get("sourceHeight") or 0)
                view_x = round(float(bounds.get("x", 0)) * source_width)
                view_y = round(float(bounds.get("y", 0)) * source_height)
                view_width = round(float(bounds.get("width", 1)) * source_width)
                view_height = round(float(bounds.get("height", 1)) * source_height)
                view_box = f"{view_x} {view_y} {view_width} {view_height}"
                frame_id = str(crop.get("frameId") or "")
                href = _screenshot_href(screenshot_by_frame.get(frame_id, {}), job, job_dir, frame_paths)
                crop_id = escape(str(crop.get("id") or crop_index + 1), quote=True)
                title_lines, description_lines = crop_blocks[crop_index]
                sections.append(
                    f'<g data-node-kind="page-detail-crop" data-crop-id="{crop_id}" data-source-frame-id="{escape(frame_id, quote=True)}" '
                    f'data-source-view-box="{view_box}">'
                    f'{_svg_full_text_block(title_lines, crop_x, crop_y + 16, 12, font_weight="700", fill="#3A3F47")}'
                )
                description_top = crop_y + max(1, len(title_lines)) * 18 + 8
                if description_lines:
                    sections.append(_svg_full_text_block(description_lines, crop_x, description_top, 12, fill="#646A73"))
                image_top = description_top + len(description_lines) * 18 + 12
                if href and source_width > 0 and source_height > 0 and view_width > 0 and view_height > 0:
                    sections.append(
                        f'<svg x="{crop_x}" y="{image_top}" width="{crop_width}" height="{crop_height}" viewBox="{view_box}" preserveAspectRatio="xMidYMid meet">'
                        f'<image x="0" y="0" width="{source_width}" height="{source_height}" href="{escape(href, quote=True)}"/></svg>'
                    )
                else:
                    sections.append(
                        f'<rect x="{crop_x}" y="{image_top}" width="{crop_width}" height="{crop_height}" rx="7" fill="#ECEEF2" stroke="#B8BDC7"/>'
                    )
                sections.append("</g>")
                crop_cursor = image_top + crop_height + 18
            copy_y = crop_cursor
            sections.append("</g>")
        sections.append("</g>")

        note_y = content_top + copy_height + 16
        for note_index, lines in enumerate(note_blocks):
            note_height = 14 + len(lines) * 20
            sections.append(
                f'<g data-node-kind="page-note" data-note-index="{note_index}"><rect x="{copy_x}" y="{note_y}" '
                f'width="{copy_width}" height="{note_height}" rx="9" fill="#FFF3BF" stroke="#F5C842"/>'
                f'{_svg_full_text_block(lines, copy_x + 16, note_y + 24, 13, fill="#594A00")}</g>'
            )
            note_y += note_height + 10
        sections.append("".join(screenshot_nodes) + "</g>")
        page_layout[page_id_raw] = (page_x, y, page_height)
        if tree_mode:
            depth_max_height = max(depth_max_height, page_height)
        else:
            grid_row_max_height = max(grid_row_max_height, page_height)
            if page_index % 2 == 1 or page_index == len(pages) - 1:
                grid_row_y += grid_row_max_height + 82
                grid_row_max_height = 0
            y = grid_row_y

    if tree_mode:
        y = depth_y + depth_max_height + 120
        page_x = base_page_x

    global_notes = [
        note for note in board.get("notes") or []
        if isinstance(note, dict) and not str(note.get("pageId") or "")
    ]
    for note_index, note in enumerate(global_notes, 1):
        lines = _page_copy_lines(note.get("text"), 72)
        note_height = 28 + len(lines) * 20
        sections.append(
            f'<g data-node-kind="board-note" data-note-index="{note_index}">'
            f'<rect x="{page_x}" y="{y}" width="{page_width}" height="{note_height}" rx="10" '
            f'fill="#FFF3BF" stroke="#F5C842"/>'
            f'{_svg_full_text_block(lines, page_x + 18, y + 29, 14, fill="#594A00")}</g>'
        )
        y += note_height + 16

    incidents: dict[str, list[int]] = {page_id: [] for page_id in page_layout}
    for relation_index, record in enumerate(route_records):
        relation = record["relation"]
        incidents[str(relation.get("sourcePageId"))].append(relation_index)
        incidents[str(relation.get("targetPageId"))].append(relation_index)
    anchors: dict[tuple[str, int], int] = {}
    for page_id, relation_indexes in incidents.items():
        _, page_y, page_height = page_layout[page_id]
        for slot, relation_index in enumerate(relation_indexes, 1):
            anchors[(page_id, relation_index)] = page_y + round(page_height * slot / (len(relation_indexes) + 1))

    relation_nodes: list[str] = []
    label_rights: list[int] = []
    for relation_index, record in enumerate(route_records):
        relation = record["relation"]
        source_id, target_id = str(relation.get("sourcePageId")), str(relation.get("targetPageId"))
        side, slot = record["side"], record["slot"]
        lane_x = (
            page_x - 34 - slot * lane_spacing["left"]
            if side == "left"
            else page_x + page_width + 34 + slot * lane_spacing["right"]
        )
        start_y, end_y = anchors[(source_id, relation_index)], anchors[(target_id, relation_index)]
        dashed = ' stroke-dasharray="10 8"' if relation.get("lineStyle") == "dashed" else ""
        label_lines, label_width = record["labelLines"], record["labelWidth"]
        label_x = lane_x - label_width - 8 if side == "left" else lane_x + 8
        label_right = label_x + label_width
        label_rights.append(label_right)
        label_y = min(start_y, end_y) + 18
        page_edge = page_x if side == "left" else page_x + page_width
        path_data = f"M {page_edge} {start_y} L {lane_x} {start_y} L {lane_x} {end_y} L {page_edge} {end_y}"
        relation_nodes.append(
            f'<g data-edge-kind="page-relation" data-lane-index="{relation_index}" data-route-side="{side}" '
            f'data-lane-x="{lane_x}" data-label-x="{label_x}" data-label-right="{label_right}">'
            f'<path data-route-layer="gap" data-bridge="true" d="{path_data}" fill="none" stroke="#FFFFFF" '
            f'stroke-width="10" stroke-linejoin="round"/>'
            f'<path data-route-layer="line" data-edge-id="{escape(str(relation.get("id") or ""), quote=True)}" data-route="page-gutter" '
            f'data-line-style="{escape(str(relation.get("lineStyle") or "solid"), quote=True)}" '
            f'd="{path_data}" '
            f'fill="none" stroke="#646A73" stroke-width="2"{dashed} marker-end="url(#arrow-muted)"/>'
            f'{_svg_full_text_block(label_lines, label_x, label_y, 12, fill="#646A73")}</g>'
        )
    if tree_mode:
        for relation_index, (_, relation) in enumerate(tree_candidates):
            source_id, target_id = str(relation.get("sourcePageId") or ""), str(relation.get("targetPageId") or "")
            if source_id not in page_layout or target_id not in page_layout:
                continue
            source_x, source_y, source_height = page_layout[source_id]
            target_x, target_y, _ = page_layout[target_id]
            start_x, start_y = source_x + page_width // 2, source_y + source_height
            end_x, end_y = target_x + page_width // 2, target_y
            middle_y = start_y + max(34, (end_y - start_y) // 2)
            path_data = f"M {start_x} {start_y} L {start_x} {middle_y} L {end_x} {middle_y} L {end_x} {end_y}"
            dashed = ' stroke-dasharray="10 8"' if relation.get("lineStyle") == "dashed" else ""
            label_lines = _page_copy_lines(relation.get("label"), 18)
            label_x = round((start_x + end_x) / 2) + 10
            label_y = middle_y - 8
            relation_nodes.append(
                f'<g data-edge-kind="page-relation" data-route="tree-branch" data-line-style="{escape(str(relation.get("lineStyle") or "solid"), quote=True)}">'
                f'<path data-route="tree-branch" data-edge-id="{escape(str(relation.get("id") or relation_index + 1), quote=True)}" '
                f'd="{path_data}" fill="none" stroke="#3370FF" stroke-width="2"{dashed} marker-end="url(#arrow-muted)"/>'
                f'{_svg_full_text_block(label_lines, label_x, label_y, 12, fill="#646A73")}</g>'
            )
    right_lane_extent = max(
        (page_x + page_width + 34 + record["slot"] * lane_spacing["right"] + 8 + record["labelWidth"]
         for record in route_records if record["side"] == "right"),
        default=page_x + page_width,
    )
    page_right_extent = max((layout[0] + page_width for layout in page_layout.values()), default=page_x + page_width)
    width = max(page_right_extent + 50, right_lane_extent + 40, max(label_rights, default=0) + 40)
    height = max(700, y)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><defs>'
        '<marker id="arrow-muted" markerWidth="10" markerHeight="10" refX="9" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#646A73"/></marker>'
        f'</defs>{"".join(relation_nodes)}{"".join(sections)}</svg>'
    )
    return svg, tuple(selected)


def _evidence_images(job: dict[str, Any], job_dir: Path) -> tuple[EvidenceImage, ...]:
    result = []
    for frame in job.get("frames") or []:
        image_path = frame.get("imagePath")
        image_url = str(frame.get("imageUrl") or "")
        artifact_prefix = f"/artifacts/{job.get('id')}/"
        if not image_path and image_url.startswith(artifact_prefix):
            image_path = image_url[len(artifact_prefix):]
        relative = Path(str(image_path or f"frames/{frame.get('id', '')}.jpg"))
        if relative.is_absolute() or ".." in relative.parts:
            continue
        timestamp = float(frame.get("timestamp") or 0)
        minutes, seconds = divmod(timestamp, 60)
        locator = f"{int(minutes):02d}:{seconds:06.3f}"
        frame_id = str(frame.get("id") or "")
        anchor = f"参考画面 {frame_id}｜{locator}"
        result.append(EvidenceImage(frame_id, job_dir / relative, anchor, anchor))
    return tuple(result)


def _region_cards(job: dict[str, Any]) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for frame in job.get("frames") or []:
        frame_id = str(frame.get("id") or "")
        for card in frame.get("regionCards") or []:
            if not isinstance(card, dict):
                continue
            name = _text(card.get("name"))
            key = (frame_id, name)
            if key in seen:
                continue
            seen.add(key)
            item = dict(card)
            item["frameId"] = frame_id
            cards.append(item)
    return cards


def _render_region_cards_table(job: dict[str, Any]) -> str:
    cards = _region_cards(job)
    if not cards:
        return ""
    rows = []
    for card in cards:
        visible = _text(card.get("visibleContent"))
        condition = _text(card.get("condition"))
        feedback = _text(card.get("feedback"))
        result_state = _text(card.get("resultState"))
        unknowns = _text(card.get("unknowns"))
        rule = f"可操作条件：{condition}\n点击后反馈：{feedback}\n结果状态：{result_state}\n未展示项：{unknowns}"
        rows.append(
            "<tr>"
            f"<td>{escape(_text(card.get('name')))}</td>"
            f"<td>{escape(visible)}</td>"
            f"<td>{escape(rule)}</td>"
            "</tr>"
        )
    return (
        "<h2>区域显示与交互规则</h2>"
        "<table><thead><tr>"
        "<th>区域</th><th>可见内容</th><th>交互规则</th>"
        "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _render_confirmed_review_tables(job: dict[str, Any], model: dict[str, Any]) -> str:
    review = job.get("reviewModel") or {}
    stages = sorted(
        (stage for stage in review.get("stages") or [] if (stage.get("confirmation") or {}).get("confirmed")),
        key=lambda stage: (stage.get("order", 0), stage.get("id", "")),
    )
    if not stages:
        return ""
    stage_by_id = {str(stage.get("id")): stage for stage in stages}
    loop_rows = []
    for stage in stages:
        loop = stage.get("smallLoop") or {}
        loop_rows.append(
            "<tr>"
            f"<td>{escape(_confirmed_text(stage.get('name')))}</td>"
            f"<td>{escape(_confirmed_text(stage.get('entryCondition')))}</td>"
            f"<td>{escape(_confirmed_text(loop.get('trigger')))}</td>"
            f"<td>{escape(_confirmed_text(loop.get('feedback')))}</td>"
            f"<td>{escape(_confirmed_text(loop.get('result')))}</td>"
            f"<td>{escape(_confirmed_text(stage.get('entryCondition')))}</td>"
            f"<td>{escape(_confirmed_text(stage.get('exitCondition')))}</td>"
            "</tr>"
        )
    parts = [
        "<h2>阶段完整事件链</h2><table><thead><tr>"
        "<th>阶段</th><th>进入前状态</th><th>操作/触发</th><th>系统响应</th><th>操作后状态</th><th>条件</th><th>结果</th>"
        "</tr></thead><tbody>" + "".join(loop_rows) + "</tbody></table>"
    ]
    transition_rows = []
    for transition in sorted(review.get("transitions") or [], key=lambda item: item.get("id", "")):
        if not transition.get("included") or not (transition.get("confirmation") or {}).get("confirmed"):
            continue
        source = stage_by_id.get(str(transition.get("sourceStageId"))) or {}
        target = stage_by_id.get(str(transition.get("targetStageId"))) or {}
        transition_rows.append(
            "<tr>"
            f"<td>{escape(_confirmed_text(transition.get('triggerLabel') or transition.get('id')))}</td>"
            f"<td>{escape(_confirmed_text(source.get('name')))}</td>"
            f"<td>{escape(_confirmed_text(transition.get('triggerLabel')))}</td>"
            f"<td>{escape(_confirmed_text(transition.get('response')))}</td>"
            f"<td>{escape(_confirmed_text(transition.get('resultState')))}</td>"
            f"<td>{escape(_confirmed_text(transition.get('condition')))}</td>"
            f"<td>{escape(_confirmed_text(target.get('name') or transition.get('resultState')))}</td>"
            "</tr>"
        )
    if transition_rows:
        parts.append(
            "<h2>已确认转换链</h2><table><thead><tr>"
            "<th>转换</th><th>进入前状态</th><th>操作/触发</th><th>系统响应</th><th>操作后状态</th><th>条件</th><th>结果</th>"
            "</tr></thead><tbody>" + "".join(transition_rows) + "</tbody></table>"
        )

    component_by_id = {
        str(component.get("id")): component
        for component in (review.get("components") or model.get("components") or [])
        if str(component.get("stageId")) in stage_by_id
    }
    states = review.get("componentStates") or ((model.get("interaction") or {}).get("componentStates") or [])
    state_columns = (
        ("default", "默认"), ("pressed", "按下"), ("selected", "选中"), ("disabled", "禁用"),
        ("loading", "加载"), ("success", "成功"), ("error", "错误"), ("exhausted", "次数耗尽"),
        ("condition_unmet", "条件不满足"),
    )
    state_by_component_id = {str(state.get("componentId")): state for state in states}
    state_rows = []
    acceptance_rows = []
    for component in component_by_id.values():
        state = state_by_component_id.get(str(component.get("id"))) or {}
        values = state.get("states") or component.get("states") or {}
        state_cells = "".join(f"<td>{escape(_confirmed_text(values.get(key)))}</td>" for key, _ in state_columns)
        state_rows.append(
            "<tr>"
            f"<td>{escape(_confirmed_text(component.get('name')))}</td>{state_cells}"
            "</tr>"
        )
        acceptance_rows.append(
            "<tr>"
            f"<td>组件：{escape(_confirmed_text(component.get('name')))}</td>"
            f"<td>按状态逐项验证：{'；'.join(f'{label}：{_confirmed_text(values.get(key))}' for key, label in state_columns)}</td>"
            "</tr>"
        )
    if state_rows:
        parts.append(
            "<h2>组件状态矩阵</h2><table><thead><tr>"
            "<th>组件</th>" + "".join(f"<th>{label}</th>" for _, label in state_columns) +
            "</tr></thead><tbody>" + "".join(state_rows) + "</tbody></table>"
        )
    for stage in stages:
        loop = stage.get("smallLoop") or {}
        acceptance_rows.append(
            "<tr>"
            f"<td>阶段：{escape(_confirmed_text(stage.get('name')))}</td>"
            f"<td>在{escape(_confirmed_text(stage.get('entryCondition')))}时，确认展示{escape(_confirmed_text(loop.get('display')))}；"
            f"触发{escape(_confirmed_text(loop.get('trigger')))}后，系统响应{escape(_confirmed_text(loop.get('feedback')))}，"
            f"结果为{escape(_confirmed_text(loop.get('result')))}。</td>"
            "</tr>",
        )
    if acceptance_rows:
        parts.append(
            "<h2>可执行验收项</h2><table><thead><tr><th>对象</th><th>验收标准</th>"
            "</tr></thead><tbody>" + "".join(acceptance_rows) + "</tbody></table>"
        )
    return "".join(parts)


_PENDING_RULE_DOMAIN = "<p>本次素材未展示，待确认</p>"


def _ordered(items: Any) -> list[dict[str, Any]]:
    values = [item for item in items if isinstance(item, dict)] if isinstance(items, list) else []
    return [item for _, item in sorted(enumerate(values), key=lambda pair: (pair[1]["order"] if type(pair[1].get("order")) is int else pair[0] + 1, pair[0]))]


def _component_names(job: dict[str, Any], model: dict[str, Any]) -> dict[str, str]:
    review = job.get("reviewModel") if isinstance(job.get("reviewModel"), dict) else {}
    review_components = review.get("components") if isinstance(review.get("components"), list) else []
    model_components = model.get("components") if isinstance(model.get("components"), list) else []
    components = [item for item in [*review_components, *model_components] if isinstance(item, dict)]
    return {str(component.get("id")): _text(component.get("name")) for component in components if component.get("id")}


def _component_name(item: dict[str, Any], components: dict[str, str]) -> str:
    return components.get(str(item.get("componentId") or ""), "待确认")


def _render_narrative(domains: dict[str, Any]) -> str:
    items = _ordered(domains.get("narrative"))
    if not items:
        return _PENDING_RULE_DOMAIN
    return "".join(
        "<h2>{}</h2><p><b>触发场景：</b>{}</p><p><b>触发节点：</b>{}</p><p><b>呈现：</b>{}</p><p><b>后续流转：</b>{}</p>".format(
            escape(_text(item.get("title"))), escape(_text(item.get("triggerScene"))), escape(_text(item.get("triggerNode"))),
            escape(_text(item.get("presentation"))), escape(_text(item.get("continuation"))),
        ) for item in items
    )


def _render_guidance(domains: dict[str, Any], components: dict[str, str]) -> str:
    items = _ordered(domains.get("guidance"))
    if not items:
        return _PENDING_RULE_DOMAIN
    parts = []
    for item in items:
        steps = "".join(
            "<li>{}：{}；提示：{}</li>".format(escape(_text(step.get("action"))), escape(_component_name(step, components)), escape(_text(step.get("prompt"))))
            for step in _ordered(item.get("steps"))
        )
        parts.append("<h2>{}</h2><p><b>引导范围：</b>{}</p><p><b>前置条件：</b>{}</p><ol>{}</ol><p><b>完成去向：</b>{}</p>".format(
            escape(_text(item.get("title"))), escape(_text(item.get("scopeCount"))), escape(_text(item.get("prerequisite"))), steps,
            escape(_text(item.get("destination"))),
        ))
    return "".join(parts)


def _render_red_dots(domains: dict[str, Any], components: dict[str, str]) -> str:
    items = _ordered(domains.get("redDots"))
    if not items:
        return _PENDING_RULE_DOMAIN
    parts = []
    for item in items:
        path = "".join("<li>{}：{}</li>".format(escape(_text(step.get("action"))), escape(_component_name(step, components))) for step in _ordered(item.get("path")))
        parts.append("<h2>{}</h2><p><b>显示条件：</b>{}</p><p><b>消去条件：</b>{}</p><p><b>穿透路径：</b></p><ol>{}</ol>".format(
            escape(_text(item.get("title"))), escape(_text(item.get("showCondition"))), escape(_text(item.get("clearCondition"))), path,
        ))
    return "".join(parts)


def _native_ordered_title_index(body_xml: str) -> str:
    """Build an editable Feishu-native numbered outline from real headings.

    Heading text remains unnumbered and continues to power document navigation;
    the ordered blocks own the visible numbering and automatically renumber when
    the generated chapter order changes.
    """
    headings = [
        (int(level), re.sub(r"<[^>]+>", "", text).strip())
        for level, text in re.findall(r"<h([1-9])(?:\s[^>]*)?>(.*?)</h\1>", body_xml, re.S)
        if re.sub(r"<[^>]+>", "", text).strip()
    ]
    if not headings:
        return ""
    roots: list[dict[str, Any]] = []
    stack: list[tuple[int, dict[str, Any]]] = []
    for level, title_text in headings:
        node: dict[str, Any] = {"title": title_text, "children": []}
        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            roots.append(node)
        stack.append((level, node))

    def render_nodes(nodes: list[dict[str, Any]]) -> str:
        return "<ol>" + "".join(
            '<li seq="auto"><b>{}</b>{}</li>'.format(
                escape(str(node["title"])),
                render_nodes(node["children"]) if node["children"] else "",
            )
            for node in nodes
        ) + "</ol>"

    return render_nodes(roots)


def _native_numbered_chapter_body(body_xml: str) -> str:
    """Put the real H2 chapter bodies in one Feishu-native ordered list.

    This is intentionally not a detached table of contents: each numbered item
    owns the chapter heading and all of its actual paragraphs, diagrams and
    tables up to the next H2.
    """
    matches = list(re.finditer(r"<h2>(.*?)</h2>", body_xml, flags=re.S))
    if not matches:
        return body_xml
    prefix = body_xml[:matches[0].start()]
    items: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body_xml)
        section = body_xml[match.end():end]
        items.append(
            f'<li seq="auto"><h2>{match.group(1)}</h2>{section}</li>'
        )
    return prefix + '<ol class="accepted-chapter-sections">' + "".join(items) + "</ol>"


def render_feishu_document(job: dict[str, Any], job_dir: Path) -> RenderedFeishuDocument:
    model = job["planningModel"]
    gameplay = model.get("mode") == "gameplay"
    project = model.get("project") or {}
    project_name = _text(project.get("name") or job.get("metadata", {}).get("projectName") or "未命名项目")
    kind = "玩法" if gameplay else "交互"
    title = f"{project_name}｜{kind}策划案｜{date.today().isoformat()}"
    mermaid = render_ue_flow(model)
    board_svg, _ = render_ue_board_svg(job, job_dir)
    gameplay_review = job.get("gameplayReviewModel")
    native_boards = (
        compile_gve16_delivery_whiteboards(job, job_dir)
        if isinstance(gameplay_review, dict)
        else compile_gve16_whiteboards(job, job_dir)
    )
    accepted_publication = job.get("acceptedPublication")
    if isinstance(accepted_publication, dict):
        from .accepted_publication import markdown_to_feishu_xml, p6_table_to_feishu_xml, p6_tables_to_feishu_xml

        native_boards = compile_accepted_delivery_whiteboards(job, job_dir)
        title = f"{project_name}｜完整策划案｜{date.today().isoformat()}"
        accepted = markdown_to_feishu_xml(_text(accepted_publication.get("markdown")))
        diagrams = [
            item for item in accepted_publication.get("p5Diagrams") or []
            if isinstance(item, dict) and item.get("status") == "reviewed" and item.get("svg")
        ]
        p6_tables = [item for item in accepted_publication.get("p6Tables") or [] if isinstance(item, dict)]
        diagram_by_id = {str(item.get("id") or ""): item for item in diagrams}
        table_by_id = {str(item.get("id") or ""): item for item in p6_tables if item.get("status") == "reviewed"}
        board_by_key = {named.key: named for named in native_boards}
        used_diagram_ids: list[str] = []
        used_table_ids: list[str] = []
        used_board_keys: list[str] = []
        embedded_in_body: list[tuple[str, str]] = []

        def replace_embed(match: re.Match[str]) -> str:
            kind, artifact_id = match.group(1), match.group(2)
            if kind == "P5":
                diagram = diagram_by_id.get(artifact_id)
                if not diagram:
                    raise ValueError(f"accepted body references missing reviewed diagram: {artifact_id}")
                used_diagram_ids.append(artifact_id)
                diagram_title = _text(diagram.get("title")) or "玩法图解"
                embedded_in_body.append((diagram_title, str(diagram.get("svg"))))
                return f"<h4>{escape('图示：' + diagram_title)}</h4><whiteboard type=\"blank\"></whiteboard>"
            if kind == "BOARD":
                named = board_by_key.get(artifact_id)
                if not named:
                    if artifact_id in {"ue", "competitor", "ux"}:
                        return ""
                    raise ValueError(f"accepted body references missing native board: {artifact_id}")
                if artifact_id in used_board_keys:
                    raise ValueError(f"accepted body references native board more than once: {artifact_id}")
                used_board_keys.append(artifact_id)
                return f"<h4>{escape('图示：' + named.title)}</h4><whiteboard type=\"blank\"></whiteboard>"
            table = table_by_id.get(artifact_id)
            if not table:
                raise ValueError(f"accepted body references missing reviewed table: {artifact_id}")
            used_table_ids.append(artifact_id)
            return p6_table_to_feishu_xml(table, heading_level=4)

        accepted_body = re.sub(
            r"<p>__GVE16_EMBED_(P5|P6|BOARD)_([A-Za-z0-9-]+)__</p>",
            replace_embed,
            accepted.body_xml,
        )
        if "__GVE16_EMBED_" in accepted_body:
            raise ValueError("unresolved accepted publication embed directive")
        expected_board_keys = [named.key for named in native_boards]
        if used_board_keys != expected_board_keys:
            raise ValueError(
                f"accepted body must embed native boards once in canonical order: {expected_board_keys}"
            )
        unmatched_diagrams = [item for item in diagrams if str(item.get("id") or "") not in used_diagram_ids]
        unmatched_tables = [item for item in p6_tables if item.get("status") == "reviewed" and str(item.get("id") or "") not in used_table_ids]
        content_parts: list[str] = [accepted_body]
        if unmatched_diagrams:
            content_parts.append("<h1>必要图解</h1>")
            for diagram in unmatched_diagrams:
                diagram_title = _text(diagram.get("title")) or "玩法图解"
                content_parts.extend([f"<h2>{escape(diagram_title)}</h2>", '<whiteboard type="blank"></whiteboard>'])
                embedded_in_body.append((diagram_title, str(diagram.get("svg"))))
        if unmatched_tables:
            content_parts.append(p6_tables_to_feishu_xml(unmatched_tables))
        content_xml = _native_numbered_chapter_body("\n".join(content_parts))
        parts = [f"<title>{escape(title)}</title>", content_xml]
        xml = "\n".join(parts)
        board_manifest = [
            {
                "key": named.key,
                "structure": named.board.structure,
                "overlay": named.board.overlay,
                "images": [
                    {"frameId": image.frame_id, "path": image.image_path, "node": image.node}
                    for image in named.board.images
                ],
            }
            for named in native_boards
        ]
        fingerprint_source = "accepted-publication-v1\n" + xml + "\n" + json.dumps(board_manifest, ensure_ascii=False, sort_keys=True)
        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        embedded = tuple(embedded_in_body)
        preview_order = (
            {"type": "title", "title": title},
            *accepted.order,
            *({"type": "gameplay_diagram", "title": title} for title, _ in embedded),
            {"type": "reviewed_tables", "title": "参数配置表", "count": len(accepted_publication.get("p6Tables") or [])},
        )
        preview_board_svgs = tuple(
            (named.key, render_native_whiteboard_svg(named.board, job_dir))
            for named in native_boards
        )
        ue_svg = dict(preview_board_svgs).get("planning", "")
        return RenderedFeishuDocument(
            title, xml, mermaid, ue_svg, "svg", (), fingerprint, native_boards,
            len(embedded), preview_order, embedded, preview_board_svgs,
        )
    if isinstance(gameplay_review, dict):
        from .gameplay_render import render_gameplay_document_sections

        title = f"{project_name}｜完整策划案｜{date.today().isoformat()}"
        gameplay_render = render_gameplay_document_sections(job)
        available_evidence = {item.frame_id: item for item in _evidence_images(job, job_dir)}
        inline_evidence: list[EvidenceImage] = []
        for chapter in (gameplay_review.get("chapters") or []):
            for figure in chapter.get("inlineFigures") or []:
                if not isinstance(figure, dict):
                    continue
                frame_id = str(figure.get("frameId") or "")
                source = available_evidence.get(frame_id)
                if source is None or not source.path.is_file():
                    raise ValueError(f"INLINE_FIGURE_MISSING:{frame_id or 'UNKNOWN'}")
                inline_evidence.append(EvidenceImage(
                    frame_id, source.path, source.anchor_text,
                    str(figure.get("caption") or source.caption),
                ))
        gameplay_body_xml = gameplay_render.body_xml
        for image in inline_evidence:
            try:
                media_path = image.path.resolve().relative_to(Path.cwd().resolve()).as_posix()
            except ValueError as exc:
                raise ValueError(f"INLINE_FIGURE_OUTSIDE_PROJECT:{image.frame_id}") from exc
            pattern = rf'(<img\s+name="inline-figure-{re.escape(image.frame_id)}"\s+caption="[^"]*")\s*/>'
            gameplay_body_xml, count = re.subn(pattern, rf'\1 path="{media_path}"/>', gameplay_body_xml, count=1)
            if count != 1:
                raise ValueError(f"INLINE_FIGURE_ANCHOR_MISSING:{image.frame_id}")
        analysis_note = _text(project.get("scope"))
        parts = [
            f"<title>{escape(title)}</title>",
            "<h1>文档概述</h1>",
            f"<p>{escape(analysis_note)}</p>",
            gameplay_render.overview_xml,
        ]
        for named in native_boards:
            parts.extend([f"<h1>{escape(named.title)}</h1>", '<whiteboard type="blank"></whiteboard>'])
        parts.append(gameplay_body_xml)
        xml = "\n".join(parts)
        preview_board_svgs = (("planning", board_svg),)
        board_manifest = [
            {
                "key": named.key,
                "structure": named.board.structure,
                "overlay": named.board.overlay,
                "images": [
                    {"frameId": image.frame_id, "path": image.image_path, "node": image.node}
                    for image in named.board.images
                ],
            }
            for named in native_boards
        ]
        fingerprint_source = "feishu-delivery-v5-preview-parity\n" + xml + "\n" + json.dumps(board_manifest, ensure_ascii=False, sort_keys=True) + "\n" + json.dumps(preview_board_svgs, ensure_ascii=False)
        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        preview_order = (
            {"type": "title", "title": title},
            {"type": "document_overview", "title": "文档概述", "text": analysis_note},
            *gameplay_render.overview_order,
            *({"type": "ue_board", "key": named.key, "title": named.title} for named in native_boards),
            *gameplay_render.body_order,
        )
        return RenderedFeishuDocument(
            title, xml, mermaid, board_svg, "svg", tuple(inline_evidence), fingerprint, native_boards,
            gameplay_render.embedded_whiteboard_count, preview_order, gameplay_render.embedded_whiteboards,
            preview_board_svgs,
        )
    section_title = "玩法目标与核心机制" if gameplay else "页面与组件说明"
    events_title = "玩法流程与规则" if gameplay else "交互流程与状态"
    review_constraints = (job.get("reviewModel") or {}).get("crossStateConstraints") or []
    constraints = review_constraints or (model.get("extensions") or {}).get("crossStateConstraints") or []
    parts = [
        f"<title>{escape(title)}</title>",
        "<h1>项目说明</h1>",
        f"<p>{escape(_text(project.get('scope')))}</p>",
        f"<h1>{section_title}</h1>",
    ]
    for scene in model.get("scenes") or []:
        parts.append(f"<h2>{escape(_text(scene.get('title')))}</h2>")
        parts.append(f"<p><b>目标：</b>{escape(_text(scene.get('objective')))}</p>")
        condition = "进入条件" if gameplay else "显示条件"
        parts.append(f"<p><b>{condition}：</b>{escape(_text(scene.get('entryCondition')))}</p>")
        parts.append(f"<p><b>结束条件：</b>{escape(_text(scene.get('exitCondition')))}</p>")
    review_tables = _render_confirmed_review_tables(job, model)
    if review_tables:
        parts.append(review_tables)
    if not gameplay:
        region_table = _render_region_cards_table(job)
        if region_table:
            parts.append(region_table)
    parts.append(f"<h1>{events_title}</h1>")
    for index, event in enumerate(model.get("events") or [], 1):
        parts.append(f"<h2>事件 {index}</h2>")
        parts.append(f"<p><b>{'玩家操作' if gameplay else '用户输入'}：</b>{escape(_text(event.get('action')))}</p>")
        parts.append(f"<p><b>系统响应：</b>{escape(_text(event.get('response')))}</p>")
    if constraints:
        parts.append("<h2>跨状态约束</h2><ul>" + "".join(
            f"<li>{escape(_confirmed_text(item.get('text') or item.get('id')))}（{escape(_confirmed_text(item.get('status')))}）</li>"
            for item in constraints
        ) + "</ul>")
        pending = [item for item in constraints if _confirmed_text(item.get("status")) == "待确认"]
        if pending:
            parts.append("<h2>待确认项</h2><ul>" + "".join(
                f"<li>{escape(_confirmed_text(item.get('text') or item.get('id')))}</li>" for item in pending
            ) + "</ul>")
    if gameplay:
        review = job.get("reviewModel") if isinstance(job.get("reviewModel"), dict) else {}
        domains = review.get("ruleDomains") if isinstance(review.get("ruleDomains"), dict) else {}
        components = _component_names(job, model)
        parts.extend([
            "<h1>9. 叙事</h1>", _render_narrative(domains),
            "<h1>11. 引导</h1>", _render_guidance(domains, components),
            "<h1>12. 红点提示</h1>", _render_red_dots(domains, components),
        ])
    parts.extend(["<h1>策划草图</h1>", '<whiteboard type="blank"></whiteboard>'])
    xml = "\n".join(parts)
    fingerprint = hashlib.sha256(xml.encode("utf-8")).hexdigest()
    return RenderedFeishuDocument(title, xml, mermaid, board_svg, "svg", (), fingerprint, native_boards)
