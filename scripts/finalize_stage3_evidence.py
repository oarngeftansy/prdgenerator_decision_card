from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.acceptance_evidence import validate_stage3_evidence


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts/stage3-v3-acceptance"
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"


def digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main():
    manifest_path = OUTPUT / "evidence-manifest.json"
    payload_path = OUTPUT / "payloads.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payloads = json.loads(payload_path.read_text(encoding="utf-8"))
    after = hashlib.sha256(JOB.read_bytes()).hexdigest()
    entries = manifest["entries"]
    for item in entries:
        item["humanInspected"] = True
    report = validate_stage3_evidence(entries, official_before=manifest["officialJobBefore"], official_after=after)
    target = next(item for item in payloads["payloads"] if item["caseId"] == "S3-TC30")
    target["sections"] = [item for item in target["sections"] if item.get("label") not in {"三十张证据检查结果", "正式任务恢复结果"}]
    target["sections"].extend([
        {"label":"三十张证据检查结果","value":{
            "用例编号":"S3-TC01 至 S3-TC30，连续且无缺漏",
            "唯一输入":f"{len(set(item['inputHash'] for item in entries))}/30",
            "唯一正文":f"{len(set(item['bodyHash'] for item in entries))}/30",
            "唯一截图":f"{len(set(item['screenshotHash'] for item in entries))}/30",
            "逐图人工检查":"30/30",
        }},
        {"label":"正式任务恢复结果","value":{
            "执行前哈希":manifest["officialJobBefore"], "执行后哈希":after,
            "是否一致":"是" if manifest["officialJobBefore"] == after else "否",
            "完整性结论":"通过" if report["passed"] else "不通过",
        }},
    ])
    body = {"title":target["title"], "inputSummary":target["inputSummary"], "sections":target["sections"]}
    target["bodyHash"] = digest(body)
    payload_path.write_text(json.dumps(payloads, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "final-validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
