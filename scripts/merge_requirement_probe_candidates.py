from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_requirement_discovery import evaluate_probe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    candidate_payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    by_requirement: dict[str, list[dict]] = {}
    for candidate in candidate_payload.get("candidates", []):
        by_requirement.setdefault(candidate["requirementId"], []).append(candidate)
    for requirement in registry.get("requirements", []):
        candidates = by_requirement.get(requirement["requirementId"], [])
        if not candidates or requirement["status"] != "evidence_probe":
            continue
        result = evaluate_probe({"candidates": candidates})
        if result["status"] == "evidence_resolvable":
            requirement["status"] = "evidence_resolvable"
            requirement.setdefault("statusHistory", []).append("evidence_resolvable")
            requirement["evidenceCandidateIds"] = result["evidenceCandidateIds"]
    registry["evidenceCandidates"] = candidate_payload.get("candidates", [])
    registry["publicationEligible"] = False
    args.output.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
