from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.gameplay_rule_chain_reconstruction import attach_approved_requirement_rules


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chains", type=Path)
    parser.add_argument("approved_rules", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    chains = json.loads(args.chains.read_text(encoding="utf-8"))
    rules = json.loads(args.approved_rules.read_text(encoding="utf-8"))
    output = attach_approved_requirement_rules(chains, rules)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
