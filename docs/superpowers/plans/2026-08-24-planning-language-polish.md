# Planning Language Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从冻结的 v2 Final Document 生成只改变可读文本的 v3，并证明结构化 Projection 与 FeedbackTrace 完全未变。

**Architecture:** 在新的 Final Renderer 辅助模块中实现纯函数文本润色；独立生成脚本读取 v2 产物、执行完整性门禁、输出 v3 与 unified diff。现有 Rule Intelligence 和 Reconstruction 模块完全不动。

**Tech Stack:** Python 3、pytest、`copy.deepcopy`、`difflib`、`hashlib`

## Global Constraints

- 只修改 Final Document 的 `sentence.text / proposal / question`。
- 不改变章节、机制、semantic group、句子和 Gap 顺序。
- 不新增、删除或改变事实。
- Projection 与 FeedbackTrace 前后 SHA-256 必须一致。
- Feedback Regression 必须保持 12 fully_reflected / 0 partial / 0 regressed。

---

### Task 1: Pure Final Text Polish

**Files:**
- Create: `backend/planning_language_polish.py`
- Create: `tests/test_planning_language_polish.py`

**Interfaces:**
- Consumes: assembled Final Document dictionary.
- Produces: `polish_final_document(document: dict[str, Any]) -> dict[str, Any]`.

- [ ] Write failing tests for repeated refresh wording, readable Gap questions, numeric-example labeling, stable ordering/provenance, and immutable input.
- [ ] Run the focused tests and verify semantic failures.
- [ ] Implement deterministic text-only transformations on a deep copy.
- [ ] Run focused tests and verify all pass.

### Task 2: Candidate v3 Export and Integrity Gate

**Files:**
- Create: `scripts/polish_yilu_final_delivery_v3.py`
- Create: `artifacts/yilu-kuangbiao-final-delivery-candidate-v3-2026-08-24/result-a-final.md`
- Create: `artifacts/yilu-kuangbiao-final-delivery-candidate-v3-2026-08-24/v2-to-v3.diff`
- Create: `artifacts/yilu-kuangbiao-final-delivery-candidate-v3-2026-08-24/planning-language-polish-audit.json`

**Interfaces:**
- Consumes: frozen v2 `result-a-final.json`, Projection and FeedbackTrace.
- Produces: v3 Final, diff, byte-identical structured-data copies and hash audit.

- [ ] Generate v3 and fail if structured hashes or feedback coverage violate the gate.
- [ ] Inspect the diff and confirm every change is language-only.
- [ ] Run the focused and complete test suites.
- [ ] Stage only files belonging to this polish task and commit as `Polish final planning language for planner review`.
