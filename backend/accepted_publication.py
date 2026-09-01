from __future__ import annotations

import re
from dataclasses import dataclass
from html import escape
from typing import Any


@dataclass(frozen=True)
class AcceptedPublicationRender:
    body_xml: str
    order: tuple[dict[str, Any], ...]


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _is_separator(line: str) -> bool:
    cells = _cells(line)
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells)


def _table_xml(lines: list[str]) -> str:
    rows = [_cells(line) for line in lines if not _is_separator(line)]
    if not rows:
        return ""
    head, *body = rows
    return "<table><tr>{}</tr>{}</table>".format(
        "".join(f"<th>{escape(cell)}</th>" for cell in head),
        "".join("<tr>{}</tr>".format("".join(f"<td>{escape(cell)}</td>" for cell in row)) for row in body),
    )


def markdown_to_feishu_xml(markdown: str) -> AcceptedPublicationRender:
    parts: list[str] = []
    order: list[dict[str, Any]] = []
    list_kind: str | None = None
    table_lines: list[str] = []

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            parts.append(f"</{list_kind}>")
            list_kind = None

    def close_table() -> None:
        if table_lines:
            parts.append(_table_xml(table_lines))
            table_lines.clear()

    for raw in markdown.splitlines():
        line = raw.strip()
        embed = re.fullmatch(r"<!--\s*EMBED:(P5|P6|BOARD):([A-Za-z0-9-]+)\s*-->", line)
        if embed:
            close_list()
            close_table()
            kind, artifact_id = embed.groups()
            parts.append(f"<p>__GVE16_EMBED_{kind}_{artifact_id}__</p>")
            order.append({"type": "accepted_embed", "kind": kind, "artifactId": artifact_id})
            continue
        if not line or line.startswith("<!--"):
            close_list()
            close_table()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            close_list()
            close_table()
            level = min(6, len(heading.group(1)))
            title = heading.group(2).strip()
            parts.append(f"<h{level}>{escape(title)}</h{level}>")
            order.append({"type": "accepted_heading", "title": title, "level": level})
            continue
        if line.startswith("|"):
            close_list()
            table_lines.append(line)
            continue
        close_table()
        bullet = re.match(r"^[-*]\s+(.+)$", line)
        numbered = re.match(r"^\d+[.)]\s+(.+)$", line)
        if bullet or numbered:
            wanted = "ul" if bullet else "ol"
            if list_kind != wanted:
                close_list()
                parts.append(f"<{wanted}>")
                list_kind = wanted
            text = (bullet or numbered).group(1).strip()
            seq = ' seq="auto"' if wanted == "ol" else ""
            parts.append(f"<li{seq}>{escape(text)}</li>")
            continue
        close_list()
        parts.append(f"<p>{escape(line)}</p>")
    close_list()
    close_table()
    return AcceptedPublicationRender("".join(parts), tuple(order))


def p6_tables_to_feishu_xml(tables: list[dict[str, Any]]) -> str:
    parts = ["<h1>参数配置表</h1>"]
    for table in tables:
        if not isinstance(table, dict) or table.get("status") != "reviewed":
            continue
        rows = table.get("publicationRows") or table.get("rows") or []
        columns = table.get("publicationColumns") or ["参数", "含义", "当前值"]
        public_rows = rows if table.get("publicationRows") else [
            [row[0], row[1], row[3]] for row in rows if isinstance(row, list) and len(row) >= 4
        ]
        parts.extend([
            f"<h2>{escape(str(table.get('title') or '参数表'))}</h2>",
            "<table><tr>{}</tr>{}</table>".format(
                "".join(f"<th>{escape(str(column))}</th>" for column in columns),
                "".join(
                    "<tr>{}</tr>".format("".join(f"<td>{escape(str(cell))}</td>" for cell in row))
                    for row in public_rows
                ),
            ),
        ])
    return "".join(parts)


def p6_table_to_feishu_xml(table: dict[str, Any], *, heading_level: int = 4) -> str:
    if not isinstance(table, dict) or table.get("status") != "reviewed":
        return ""
    rows = table.get("publicationRows") or table.get("rows") or []
    columns = table.get("publicationColumns") or ["参数", "含义", "当前值"]
    public_rows = rows if table.get("publicationRows") else [
        [row[0], row[1], row[3]] for row in rows if isinstance(row, list) and len(row) >= 4
    ]
    level = max(1, min(6, int(heading_level)))
    title = escape(str(table.get("title") or "参数表"))
    return "<h{level}>配置表：{title}</h{level}><table><tr>{head}</tr>{body}</table>".format(
        level=level,
        title=title,
        head="".join(f"<th>{escape(str(column))}</th>" for column in columns),
        body="".join(
            "<tr>{}</tr>".format("".join(f"<td>{escape(str(cell))}</td>" for cell in row))
            for row in public_rows
        ),
    )
