from __future__ import annotations

from copy import deepcopy
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


def load_gve16_mechanic_structure_corpus(path: str | Path) -> Mapping[str, Any]:
    """Load an anonymous, content-free and immutable structure corpus."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("contentAuthority") != "none" or not data.get("provisional"):
        raise ValueError("MechanicStructureCorpus must be provisional and have no content authority")
    for pattern in data.get("patterns", []):
        if not str(pattern.get("evidenceSourceRef", "")).startswith("GVE16/ANON-"):
            raise ValueError("Corpus evidence references must be anonymous")
        if not pattern.get("nodeTypes") or not pattern.get("edgePatterns"):
            raise ValueError("Each corpus pattern must contain nodes and directed edges")
    return _freeze(deepcopy(data))
