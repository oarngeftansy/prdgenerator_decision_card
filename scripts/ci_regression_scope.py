from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"

# These tests are useful historical audits, but they depend on workspace-local
# snapshots that were intentionally not imported into the Git repository.
# They must not masquerade as product regressions when those snapshots are
# absent from a clean checkout.
HISTORICAL_SOURCE_MARKERS = (
    'ROOT / "artifacts"',
    "ROOT / 'artifacts'",
    'Path("artifacts',
    "Path('artifacts",
    '"artifacts/',
    "'artifacts/",
    'ROOT / "data" / "jobs"',
    "ROOT / 'data' / 'jobs'",
    '"data/jobs/',
    "'data/jobs/",
)
HISTORICAL_EXPLICIT = {
    "test_accepted_planning_preview_web.py",  # endpoint is itself a frozen publication browser
}

# This single assertion belongs to the superseded pre-Master-Planner contract:
# it expected an unresolved design question to be printed in Final. The new
# canonical Final explicitly forbids question leakage; the replacement policy
# is covered by test_master_final_question_policy.py.
SUPERSEDED_NODEIDS = (
    "tests/test_final_mechanic_reconstruction.py::"
    "test_final_suppresses_schema_question_and_technical_gap_but_keeps_specific_planning_gap",
)


def classify() -> tuple[list[Path], list[Path]]:
    core: list[Path] = []
    historical: list[Path] = []
    for path in sorted(TEST_ROOT.glob("test_*.py")):
        text = path.read_text(encoding="utf-8", errors="replace")
        is_historical = path.name in HISTORICAL_EXPLICIT or any(
            marker in text for marker in HISTORICAL_SOURCE_MARKERS
        )
        (historical if is_historical else core).append(path)
    return core, historical


def relative(paths: list[Path]) -> list[str]:
    return [str(path.relative_to(ROOT)).replace("\\", "/") for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("core", "historical", "list"))
    args = parser.parse_args()
    core, historical = classify()

    if args.mode == "list":
        print(f"core={len(core)} historical={len(historical)}")
        print("[historical]")
        print("\n".join(relative(historical)))
        return 0

    if args.mode == "historical":
        print(f"Historical audit modules: {len(historical)}")
        if not (ROOT / "artifacts").exists():
            print("Historical workspace snapshots are not present in this Git checkout; audit is unavailable, not passed.")
            return 0
        command = [sys.executable, "-m", "pytest", "-q", *relative(historical)]
        return subprocess.call(command, cwd=ROOT)

    print(f"Running reproducible core regression modules: {len(core)}")
    command = [sys.executable, "-m", "pytest", "-q", *relative(core)]
    for nodeid in SUPERSEDED_NODEIDS:
        command.extend(("--deselect", nodeid))
    return subprocess.call(command, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
