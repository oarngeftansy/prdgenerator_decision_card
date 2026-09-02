"""Runtime access to production planning skill contracts.

Historical skills remain in-repo only for audit/repro. New production stages must
load contracts exclusively from this manifest so legacy evidence-gating and
sample-specific instructions cannot silently regain authority.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PRODUCTION_SKILLS = {
    "gameplay_understanding": ROOT / "skills" / "gameplay-understanding-v1.2" / "SKILL.md",
    "execution_planning": ROOT / "skills" / "execution-planning-v2" / "SKILL.md",
    "interaction_planning": ROOT / "skills" / "interaction-planning-v2" / "SKILL.md",
    "quality_judge": ROOT / "skills" / "planner-quality-judge-v2" / "SKILL.md",
}


class PlanningSkillContractError(RuntimeError):
    pass


@lru_cache(maxsize=None)
def load_production_skill(name: str) -> str:
    path = PRODUCTION_SKILLS.get(name)
    if path is None:
        raise PlanningSkillContractError(f"unknown production planning skill: {name}")
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise PlanningSkillContractError(f"production planning skill unavailable: {name}") from exc
    if not text:
        raise PlanningSkillContractError(f"production planning skill is empty: {name}")
    return text


def production_skill_manifest() -> dict[str, str]:
    return {name: str(path.relative_to(ROOT)).replace("\\", "/") for name, path in PRODUCTION_SKILLS.items()}
