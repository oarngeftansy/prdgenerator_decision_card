from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.mechanic_requirement_discovery import promote_candidates_to_evidence_facts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("candidates", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    promoted = promote_candidates_to_evidence_facts(payload.get("candidates", []))
    promoted["sourceCandidateArtifact"] = str(args.candidates)
    promoted["publicationEligible"] = False
    args.output.write_text(json.dumps(promoted, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
