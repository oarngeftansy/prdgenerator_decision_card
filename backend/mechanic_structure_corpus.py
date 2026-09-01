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


def load_mechanic_structure_corpus(path: str | Path) -> Mapping[str, Any]:
    """Load an immutable, content-free mechanism-structure corpus."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("contentAuthority") != "none":
        raise ValueError("MechanicStructureCorpus cannot be a content authority")
    if not data.get("provisional"):
        raise ValueError("single-document structure corpus must remain provisional")
    for mechanic_type, profile in data.get("mechanicTypes", {}).items():
        if profile.get("canCloseGap") is not False or not profile.get("sourceEvidence"):
            raise ValueError(f"invalid content boundary for mechanic type: {mechanic_type}")
    return _freeze(data)
