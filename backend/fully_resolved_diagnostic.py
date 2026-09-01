from __future__ import annotations

from typing import Any


def apply_temporary_review_overrides(markdown: str,
                                     overrides: list[dict[str, Any]]) -> str:
    lines = markdown.splitlines()
    for override in overrides:
        matches = override.get("matchLines", [])
        replacement = override.get("replacementLines", [])
        positions = []
        for match in matches:
            found = [index for index, line in enumerate(lines) if line == match]
            if len(found) != 1:
                raise ValueError(f"diagnostic override expected one exact match for {match!r}, got {len(found)}")
            positions.append(found[0])
        first = min(positions)
        for index in sorted(positions, reverse=True):
            del lines[index]
        lines[first:first] = replacement
    lines = [line for line in lines if line != "待确认："]
    if any("待确认" in line for line in lines):
        raise ValueError("diagnostic override left unresolved review text in preview")
    compact = []
    for line in lines:
        if line == "" and compact and compact[-1] == "":
            continue
        compact.append(line)
    return "\n".join(compact).rstrip() + "\n"


def count_diagnostic_carriers(markdown: str) -> dict[str, int]:
    lines = markdown.splitlines()
    table_rows = sum(line.startswith("|") and "---" not in line and "词条 | 作用对象" not in line
                     for line in lines)
    bullets = sum(line.startswith("- ") or line.startswith("   - ") for line in lines)
    ordered_items = sum(len(line) > 3 and line[0].isdigit() and line[1:3] == ". " for line in lines)
    effective = bullets + ordered_items + table_rows
    return {"effectiveExecutionRuleCount": effective,
            "ruleGroups": sum(line.startswith("### ") for line in lines),
            "tables": int(any(line.startswith("| 词条 |") for line in lines)),
            "orderedProcesses": int(ordered_items > 0),
            "formulae": sum("=" in line and "÷" in line for line in lines)}
