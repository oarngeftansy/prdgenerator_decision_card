from __future__ import annotations

from pathlib import Path
from typing import Mapping


PROFILES = {
    "qwen": {
        "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-vl-plus",
    },
    "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "model": "gpt-4.1-mini",
    },
}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def resolve_provider(env: Mapping[str, str]) -> dict[str, str]:
    key = str(env.get("VISION_API_KEY") or "").strip()
    if not key:
        raise ValueError("VISION_API_KEY is required")
    provider = str(env.get("VISION_PROVIDER") or "qwen").strip().lower()
    profile = PROFILES.get(provider, {})
    base_url = str(env.get("VISION_API_BASE") or profile.get("baseUrl") or "").rstrip("/")
    model = str(env.get("VISION_MODEL") or profile.get("model") or "").strip()
    if not base_url:
        raise ValueError("VISION_API_BASE is required for custom provider")
    if not model:
        raise ValueError("VISION_MODEL is required for custom provider")
    return {"provider": provider, "baseUrl": base_url, "model": model, "apiKey": key}
