from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from backend.gameplay_copy import migrate_gameplay_presentation
from backend.review_preview import build_final_review_preview


ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".migration.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    json.loads(temporary.read_text(encoding="utf-8"))
    temporary.replace(path)


def execute(path: Path, *, apply: bool = False) -> dict:
    original = json.loads(path.read_text(encoding="utf-8"))
    before_hash = sha256(path)
    dry_run = migrate_gameplay_presentation(original, dry_run=True)
    result = {"mode": "apply" if apply else "dry-run", "job": str(path.resolve()), "beforeHash": before_hash, "plan": dry_run}
    if not apply:
        return result
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = path.with_name(f"job.before-gameplay-migration-{stamp}.json")
    shutil.copy2(path, backup)
    backup_data = json.loads(backup.read_text(encoding="utf-8"))
    if backup_data.get("id") != original.get("id"):
        raise ValueError("backup job id mismatch")
    try:
        migrate_gameplay_presentation(original, rebuild_derived=True)
        preview = build_final_review_preview(original, path.parent)
        original["gameplayFinalPreview"] = preview
        original["gameplayMigration"].update({"backup": str(backup.resolve()), "beforeHash": before_hash})
        atomic_write(path, original)
    except Exception:
        shutil.copy2(backup, path)
        raise
    result.update({"backup": str(backup.resolve()), "afterHash": sha256(path), "report": original["gameplayMigration"], "preview": preview})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Safely migrate one gameplay planning job")
    parser.add_argument("job", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = execute(args.job.resolve(), apply=args.apply)
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
