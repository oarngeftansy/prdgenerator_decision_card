"""Canonical production API entrypoint.

`backend.server` remains the stable infrastructure host. `api_server` owns the
canonical Final/Feishu routes. This module additionally redirects the legacy
background gameplay-structure worker to Gameplay Understanding Skill v1.2 so the
actual production launch path starts with the new semantic authority.

The redirection is intentionally scoped to this entrypoint; importing backend
modules in tests/tools does not globally mutate gameplay-analysis behavior.
"""

from __future__ import annotations

import copy
from typing import Any

import api_server
from backend import server as server_module
from backend.gameplay_understanding_runtime import generate_gameplay_understanding


def _canonical_generate_gameplay_structure(job: dict, job_dir, runtime_config: dict, progress=lambda *_: None) -> dict:
    understanding, compatibility_model = generate_gameplay_understanding(
        job,
        job_dir,
        runtime_config,
        progress,
    )

    # Persist the first-class understanding independently from the compatibility
    # review model. The old worker will subsequently persist the compatibility
    # shell; downstream canonical stages prefer this first-class object.
    job_id = str(job.get("id") or "")
    if job_id:
        expected_generation = str((job.get("gameplayReviewGeneration") or {}).get("generationId") or "")

        def persist(current: dict[str, Any]) -> None:
            current_generation = str((current.get("gameplayReviewGeneration") or {}).get("generationId") or "")
            if expected_generation and current_generation and current_generation != expected_generation:
                return
            current["gameplayUnderstandingModel"] = copy.deepcopy(understanding)

        server_module.storage.mutate_job(job_id, persist)

    compatibility_model["gameplayUnderstandingModel"] = copy.deepcopy(understanding)
    compatibility_model["understandingDigest"] = understanding.get("digest")
    return compatibility_model


# Explicit compatibility redirection: the existing queue/timeout/retry worker
# remains stable, but its semantic generation owner is Gameplay Understanding
# v1.2 whenever the real production entrypoint is launched.
server_module.generate_gameplay_structure = _canonical_generate_gameplay_structure

app = api_server.app
