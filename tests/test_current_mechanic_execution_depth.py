import hashlib
import json
from pathlib import Path

from scripts.generate_mechanic_execution_depth_benchmark import build_benchmark_inputs, main


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/mechanic-execution-depth-2026-08-19"
JOB = ROOT / "data/jobs/8312a91c89e144e6a59f81b982f14c06/job.json"
FINAL = ROOT / "artifacts/mechanic-requirement-closure-publication-2026-08-18/human-planning-preview.md"
HIERARCHY = ROOT / "artifacts/mechanic-design-synthesis-2026-08-18/planning-hierarchy.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_seven_profiles_are_stable_answer_free_and_repeat_is_signal_gated():
    profiles, rules, proposals = build_benchmark_inputs(ROOT)
    assert len(profiles) == 7
    assert len({p["mechanicDesignId"] for p in profiles}) == 7
    dimensions = [d for p in profiles for d in p["dimensions"]]
    assert len({d["depthDimensionId"] for d in dimensions}) == len(dimensions)
    assert all(d["satisfactionContract"]["requiredSemantics"] for d in dimensions)
    assert all("answer" not in d and "proposalText" not in d for d in dimensions)
    repeats = [d for d in dimensions if d["dimensionFamily"] == "repeat_timing"]
    assert repeats
    assert all(d["dimensionRole"] == "conditional" for d in repeats)
    assert all(d["applicability"]["status"] != "active" or d["applicability"]["signals"] for d in repeats)
    assert all(rule.get("ruleType") != "presentation" for rule in rules)
    assert {"RULE-6D655A0E67FF", "RULE-A87C8D4C1A10", "RULE-0D847899C3A9"} <= {
        rule["ruleId"] for rule in rules
    }
    assert all(p["proposalText"] not in {"开始时开始统计。", "满足条件后执行。"} for p in proposals)


def test_generator_writes_review_only_outputs_without_mutating_frozen_files():
    frozen = [path for path in (JOB, FINAL, HIERARCHY) if path.exists()]
    assert HIERARCHY in frozen
    before = {path: sha(path) for path in frozen}
    main(ROOT)
    assert before == {path: sha(path) for path in before}
    names = {
        "execution-depth-profiles.json", "execution-depth-coverage.json",
        "execution-depth-expansion-preview.md", "execution-depth-lineage.json",
        "execution-depth-quality-gate.json",
    }
    assert names == {path.name for path in OUT.iterdir() if path.is_file()}
    coverage = json.loads((OUT / "execution-depth-coverage.json").read_text(encoding="utf-8"))
    assert coverage["metrics"]["projectedConservativeCoverage"] <= coverage["metrics"]["projectedDesignCoverage"]
    assert all("depthReady" in item for item in coverage["profiles"])
    gate = json.loads((OUT / "execution-depth-quality-gate.json").read_text(encoding="utf-8"))
    assert gate["goldSetAccessCount"] == 0
    assert gate["prohibitedMutationCount"] == 0
    preview = (OUT / "execution-depth-expansion-preview.md").read_text(encoding="utf-8")
    assert "AI方案：" in preview
    assert "推荐方案：已有同武器转为强化" in preview
    assert "备选方案 B：满栏后只生成已有武器强化结果" in preview
