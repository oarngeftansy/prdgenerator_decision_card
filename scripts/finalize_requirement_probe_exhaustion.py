from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_requirement_discovery import finalize_requirement_after_probe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    parser.add_argument("facts", type=Path)
    parser.add_argument("exhaustion", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    fact_payload = json.loads(args.facts.read_text(encoding="utf-8"))
    exhaustion_records = json.loads(args.exhaustion.read_text(encoding="utf-8"))
    exhausted_ids = {
        item["requirementId"] for item in exhaustion_records
        if all(item.get(field) is True for field in (
            "fullSelectedSourceScanned", "allAnchorWindowsScanned",
            "allCandidateWindowsExpanded", "counterexamplesReviewed",
            "noNewCandidateWindows", "auditTrailRecorded",
        ))
    }
    registry["requirements"] = [
        finalize_requirement_after_probe(
            requirement, fact_payload.get("facts", []),
            probe_exhausted=requirement["requirementId"] in exhausted_ids,
        ) if requirement["requirementId"] in exhausted_ids else requirement
        for requirement in registry["requirements"]
    ]
    registry["probeExhaustion"] = exhaustion_records
    registry["publicationEligible"] = False
    args.output.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
