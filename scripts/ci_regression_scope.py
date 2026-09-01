from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = ROOT / "tests"

# These modules are historical workspace audits. They consume frozen artifacts
# or job snapshots that were intentionally not imported into this Git repo.
# Keeping an explicit manifest prevents transitive script dependencies from
# being misclassified as reproducible product regressions.
HISTORICAL_EXPLICIT = {
    "test_accepted_planning_preview_web.py",
    "test_alignment_closure_matrix.py",
    "test_approved_mechanic_publication.py",
    "test_closure_taxonomy_correction.py",
    "test_current_ai_rule_proposals.py",
    "test_current_full_mechanic_reconstruction.py",
    "test_current_job_prd_depth_migration.py",
    "test_current_mechanic_design_synthesis.py",
    "test_current_mechanic_execution_depth.py",
    "test_current_native_whiteboard_delivery.py",
    "test_current_requirement_probe_artifact.py",
    "test_execution_rule_closure_audit.py",
    "test_final_alignment_reaudit.py",
    "test_feishu_publish.py",
    "test_full_mechanic_acceptance.py",
    "test_full_mechanic_accepted_publication.py",
    "test_full_mechanic_review_web.py",
    "test_fully_resolved_diagnostic_preview.py",
    "test_game_rule_reconstruction.py",
    "test_gve16_carrier_selection.py",
    "test_gve16_chapter_assembly.py",
    "test_gve16_delivery_alignment_regression.py",
    "test_gve16_hierarchy_flattening.py",
    "test_gve16_native_planning_language.py",
    "test_instance_value_semantic_gate.py",
    "test_mechanic_rule_structuring.py",
    "test_mechanic_scope_inference.py",
    "test_phase42_reference_samples.py",
    "test_phase43_reference_samples.py",
    "test_phase51_delivery_separation.py",
    "test_phase51_evaluator_baseline.py",
    "test_phase531_generation.py",
    "test_phase532_generation.py",
    "test_phase53_mechanic_reconstruction.py",
    "test_phase53_planning_reasoning_reconstruction.py",
    "test_phase541_generation.py",
    "test_phase54_generation.py",
    "test_phase55_generation.py",
    "test_phase56_generation.py",
    "test_phase57_generation.py",
    "test_phase58_generation.py",
    "test_phase5_entity_graph.py",
    "test_planner_decision_compression.py",
    "test_planner_gap_routing.py",
    "test_planning_style_profile.py",
    "test_ue_flow_wireframe.py",
}

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

# These assertions encode superseded authority contracts. Each one has a
# replacement regression against the new Master Planner authority.
SUPERSEDED_NODEIDS = (
    "tests/test_final_mechanic_reconstruction.py::"
    "test_final_suppresses_schema_question_and_technical_gap_but_keeps_specific_planning_gap",
    "tests/test_review_preview.py::test_stale_preview_blocks_publish",
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
