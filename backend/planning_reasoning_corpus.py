from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def load_planning_reasoning_corpus(path: str | Path) -> Mapping[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("contentAuthority") != "none" or data.get("provisional") is not True:
        raise ValueError("Planning reasoning corpus must remain provisional and content-free")
    for name, template in data.get("templates", {}).items():
        if not template.get("sourceEvidence") or template.get("canGenerateRule") is not False:
            raise ValueError(f"invalid reasoning template boundary: {name}")
    return _freeze(data)
