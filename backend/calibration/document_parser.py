from __future__ import annotations

import re
from typing import Any

from .models import make_source_ref


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
WHITEBOARD_RE = re.compile(r'<whiteboard\s+token="([^"]+)"')


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_document(content: str, source_id: str = "gve16") -> dict[str, Any]:
    lines = content.replace("\r\n", "\n").splitlines()
    chapters: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    rules: list[dict[str, Any]] = []
    media: list[dict[str, str]] = []
    path: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        heading = HEADING_RE.match(line)
        if heading:
            level, title = len(heading.group(1)), heading.group(2).strip()
            path = path[: level - 1] + [title]
            chapters.append({"level": level, "title": title, "path": list(path), "line": index + 1})
            index += 1
            continue
        board = WHITEBOARD_RE.search(line)
        if board:
            media.append({"type": "whiteboard", "token": board.group(1), "locator": " / ".join(path)})
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|?[\s|:-]+\|?$", lines[index + 1].strip()):
            headers = _cells(line)
            rows: list[dict[str, str]] = []
            index += 2
            row_number = 0
            while index < len(lines) and lines[index].strip().startswith("|"):
                values = _cells(lines[index])
                rows.append(dict(zip(headers, values + [""] * max(0, len(headers) - len(values)))))
                row_number += 1
                index += 1
            tables.append({"headers": headers, "rows": rows, "locator": " / ".join(path)})
            continue
        clean = re.sub(r"^[-*+]\s+", "", line).strip()
        if clean and not clean.startswith(("<title>", "</title>")):
            rules.append({
                "text": clean,
                "chapterPath": list(path),
                "sourceRef": make_source_ref("document", source_id, f"line:{index + 1}"),
            })
        index += 1
    return {"chapters": chapters, "tables": tables, "rules": rules, "media": media}

