from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping, TypeAlias


GVE16AlignmentCorpus: TypeAlias = Mapping[str, Any]


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def load_gve16_alignment_corpus(path: str | Path) -> GVE16AlignmentCorpus:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("corpusVersion") != "gve16-alignment-corpus-v1":
        raise ValueError("unsupported GVE16AlignmentCorpus version")
    if data.get("contentAuthority") != "none":
        raise ValueError("GVE16AlignmentCorpus cannot provide content authority")
    references = data.get("provisionalReferences")
    if not isinstance(references, dict) or not references:
        raise ValueError("provisional references are required")
    if any(item.get("provisional") is not True for item in references.values()):
        raise ValueError("all limited-corpus references must be provisional")
    serialized = json.dumps(data, ensure_ascii=False)
    forbidden_keys = ("rawSentences", "chapterTree", "projectFields", "projectValues", "projectRules", "gapAnswers")
    if any(key in serialized for key in forbidden_keys):
        raise ValueError("runtime corpus contains forbidden content-authority data")
    return _freeze(data)
