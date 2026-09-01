from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.gameplay_copy import migrate_gameplay_presentation
from backend.gameplay_rule_copy import migrate_gameplay_rule_copy
from backend.lead_planner_gate import lead_planner_output_audit, lead_planner_preflight
from backend.granularity_audit import granularity_audit_report
from backend.feishu_language_quality import language_quality_report
from backend.sample_alignment import sample_alignment_report


def main() -> int:
    parser = argparse.ArgumentParser(description="生成前后主策视角强制检查")
    parser.add_argument("job", type=Path, help="任务 job.json 路径")
    parser.add_argument("--phase", choices=("structure", "details", "publish"), default="publish")
    parser.add_argument("--write-migrations", action="store_true", help="保存安全的策划文案迁移结果")
    args = parser.parse_args()
    job = json.loads(args.job.read_text(encoding="utf-8"))
    model = job.get("gameplayReviewModel") or {}
    preflight_phase = "details" if args.phase in {"details", "publish"} else "structure"
    errors = lead_planner_preflight(job, preflight_phase, model if preflight_phase == "details" else None)
    if model:
        migrate_gameplay_presentation(job)
        migrate_gameplay_rule_copy(job)
        errors.extend(lead_planner_output_audit(job["gameplayReviewModel"], "details" if args.phase != "structure" else "structure"))
    if args.write_migrations and model:
        backup = args.job.with_name("job.before-lead-planner-copy.json")
        if not backup.exists():
            shutil.copy2(args.job, backup)
        temporary = args.job.with_suffix(".lead-planner.tmp")
        temporary.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(args.job)
    granularity = granularity_audit_report(job.get("gameplayReviewModel") or {})
    language = language_quality_report(job.get("gameplayReviewModel") or {})
    alignment = sample_alignment_report(job.get("gameplayReviewModel") or {})
    report = {
        "passed": not errors,
        "phase": args.phase,
        "errors": list(dict.fromkeys(errors)),
        "granularity": granularity,
        "language": language,
        "sampleAlignment": alignment,
        "plannerMessages": [item["message"] for item in granularity["findings"]],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
