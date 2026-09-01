"""Render canonical Final documents without leaking provenance labels into copy."""

from __future__ import annotations

from html import escape
from typing import Any


_STATE_CLASS = {
    "confirmed": "publication-confirmed",
    "inferred": "publication-inferred",
    "proposed": "publication-proposed",
    "conflict": "publication-conflict",
}


def _state(sentence: dict[str, Any]) -> str:
    value = str(sentence.get("publicationState") or "confirmed").lower()
    return value if value in _STATE_CLASS else "confirmed"


def _inline_html(sentence: dict[str, Any]) -> str:
    state = _state(sentence)
    text = escape(str(sentence.get("text") or ""))
    if state in {"inferred", "proposed"}:
        return f'<span class="{_STATE_CLASS[state]}" data-publication-state="{state}">{text}</span>'
    if state == "conflict":
        return f'<span class="{_STATE_CLASS[state]}" data-publication-state="conflict">{text}</span>'
    return text


def final_document_to_html(document: dict[str, Any]) -> str:
    """HTML preview with yellow inferred/proposed and red explicit conflicts."""
    parts = [
        '<section class="master-planning-document">',
        '<style>.publication-inferred,.publication-proposed{background:#fff3b0;padding:0 .12em;border-radius:2px}.publication-conflict{background:#ffd6d6;color:#9b1c1c;padding:0 .12em;border-radius:2px}.master-planning-document li{margin:.35em 0}</style>',
        f'<h1>{escape(str(document.get("title") or "执行策划案"))}</h1>',
    ]
    for system in document.get("systems") or []:
        parts.append(f'<h2>{escape(str(system.get("title") or "未分类"))}</h2>')
        for obj in system.get("objects") or []:
            parts.append(f'<h3>{escape(str(obj.get("title") or "通用"))}</h3>')
            for chapter in obj.get("chapters") or []:
                if not chapter.get("foldIntoObject"):
                    parts.append(f'<h4>{escape(str(chapter.get("title") or "规则"))}</h4>')
                groups = chapter.get("groups") or []
                for group in groups:
                    if len(groups) > 1:
                        parts.append(f'<p><b>{escape(str(group.get("title") or "规则"))}</b></p>')
                    parts.append("<ul>")
                    for sentence in group.get("sentences") or []:
                        if sentence.get("text"):
                            parts.append(f'<li>{_inline_html(sentence)}</li>')
                    parts.append("</ul>")
    parts.append("</section>")
    return "".join(parts)


def _feishu_inline(sentence: dict[str, Any]) -> str:
    """Lark XML uses span background-color for native text highlighting."""
    state = _state(sentence)
    text = escape(str(sentence.get("text") or ""))
    if state in {"inferred", "proposed"}:
        return f'<span background-color="light-yellow">{text}</span>'
    if state == "conflict":
        return f'<span background-color="light-red" text-color="red">{text}</span>'
    return text


def final_document_to_feishu_xml(document: dict[str, Any], *, include_title: bool = True) -> str:
    """Render the exact semantic Final into lark-cli's supported XML subset.

    `span background-color="light-yellow"` is the native text-background syntax,
    so yellow remains presentation-only and the sentence itself stays decisive.
    """
    parts: list[str] = []
    if include_title:
        parts.append(f'<title>{escape(str(document.get("title") or "执行策划案"))}</title>')
    for system in document.get("systems") or []:
        parts.append(f'<h1>{escape(str(system.get("title") or "未分类"))}</h1>')
        for obj in system.get("objects") or []:
            parts.append(f'<h2>{escape(str(obj.get("title") or "通用"))}</h2>')
            for chapter in obj.get("chapters") or []:
                if not chapter.get("foldIntoObject"):
                    parts.append(f'<h3>{escape(str(chapter.get("title") or "规则"))}</h3>')
                groups = chapter.get("groups") or []
                for group in groups:
                    if len(groups) > 1:
                        parts.append(f'<p><b>{escape(str(group.get("title") or "规则"))}</b></p>')
                    parts.append("<ul>")
                    for sentence in group.get("sentences") or []:
                        if sentence.get("text"):
                            parts.append(f'<li>{_feishu_inline(sentence)}</li>')
                    parts.append("</ul>")
    return "".join(parts)
