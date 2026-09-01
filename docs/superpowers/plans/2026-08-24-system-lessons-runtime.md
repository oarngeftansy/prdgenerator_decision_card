# System Lessons Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 12 条已验证 Planner Feedback 抽象为 11 条项目无关 System Lesson，并让现有分析策略在运行时受 approved Lesson 激活控制。

**Architecture:** `system-lessons-v1.json` 是 Lesson 权威声明，`SystemLessonRegistry` 负责校验、索引和策略启用判断。现有 Rule Intelligence、Recovery、Dependency、Temporal 与 Reconstruction 继续保留各自算法，只在策略入口消费 Registry，不让 Lesson 创建项目事实。

**Tech Stack:** Python 3.11、JSON、pytest、现有 Rule Intelligence/Temporal/Mechanic Reconstruction 模块。

## Global Constraints

- 继续采用“声明式 JSON 知识图谱 + 通用引擎”，禁止玩法专用 if/else。
- Lesson 不得创建 Approved Rule、批准 Fact、关闭 Gap 或直接渲染正文。
- Lesson 不得包含《一路狂飙》名称、专用实体、文案、Rule ID 或项目答案。
- 只有 `status=approved` 的 Lesson 可以激活 runtime policy。
- 删除、降级或解绑 Lesson 必须改变对应测试行为。
- 原 12 条 Feedback Regression Baseline 必须保持 12 fully_reflected / 0 regressed。

---

### Task 1: System Lesson 声明与 Registry

**Files:**
- Create: `data/planner_knowledge/system-lessons-v1.json`
- Create: `backend/system_lesson_registry.py`
- Create: `tests/test_system_lesson_registry.py`

**Interfaces:**
- Produces: `SystemLessonRegistry.from_payload(payload, project_root=None)`、`load_system_lesson_registry(path=None)`、`registry.is_policy_enabled(policy_ref, stage, scope=None)`、`registry.feedback_policy_test_matrix()`。
- Consumes: 版本化 JSON 和 `path::test_function` 测试引用。

- [ ] **Step 1: 写 Registry 红测试**

```python
def test_only_approved_lesson_enables_policy():
    approved = _payload(status="approved")
    candidate = _payload(status="candidate")
    assert SystemLessonRegistry.from_payload(approved).is_policy_enabled("guard.pattern_formula", "evidence_guard")
    assert not SystemLessonRegistry.from_payload(candidate).is_policy_enabled("guard.pattern_formula", "evidence_guard")

def test_lessons_are_project_independent_and_cover_twelve_feedback_items():
    registry = load_system_lesson_registry()
    assert len(registry.feedback_ids) == 12
    assert "一路狂飙" not in json.dumps(registry.payload, ensure_ascii=False)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/test_system_lesson_registry.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-red`

Expected: FAIL，模块或 JSON 尚不存在。

- [ ] **Step 3: 实现 Registry 与 11 条 Lesson**

```python
@dataclass(frozen=True)
class SystemLessonRegistry:
    payload: dict[str, Any]
    lessons_by_id: dict[str, dict[str, Any]]
    policy_to_lessons: dict[str, tuple[str, ...]]

    def is_policy_enabled(self, policy_ref: str, stage: str, scope: str | None = None) -> bool:
        for lesson_id in self.policy_to_lessons.get(policy_ref, ()):
            lesson = self.lessons_by_id[lesson_id]
            if lesson["status"] != "approved" or stage not in lesson["affectedPipelineStages"]:
                continue
            if scope and scope in lesson.get("nonApplicableScope", []):
                continue
            return True
        return False
```

Registry 校验所有必填字段、状态枚举、唯一 ID、12 条 Feedback 覆盖和项目专用内容禁令。

- [ ] **Step 4: 运行 Registry 测试**

Run: `python -m pytest tests/test_system_lesson_registry.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-green`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add data/planner_knowledge/system-lessons-v1.json backend/system_lesson_registry.py tests/test_system_lesson_registry.py
git commit -m "Add declarative system lesson registry"
```

### Task 2: Rule Intent、Evidence Authority 与 CandidateType 消费 Lesson

**Files:**
- Modify: `backend/rule_intelligence_pipeline.py`
- Modify: `backend/approved_information_recovery.py`
- Modify: `backend/mechanic_reconstruction.py`
- Modify: `data/planner_knowledge/approved-narrative-recovery-policies-v1.json`
- Modify: `data/planner_knowledge/mechanic-reconstruction-policies-v1.json`
- Test: `tests/test_system_lesson_runtime.py`

**Interfaces:**
- Consumes: `SystemLessonRegistry.is_policy_enabled`。
- Produces: `build_rule_intelligence_projection(..., lesson_registry=None)`、`recover_approved_information(..., lesson_registry=None)`、`reconstruct_mechanics(..., lesson_registry=None)` 的可注入门禁。

- [ ] **Step 1: 写跨项目红测试**

```python
def test_attack_responsibility_and_parameter_guards_depend_on_approved_lessons():
    projection = build_rule_intelligence_projection(_neutral_turret_rules())
    assert _intent(projection, "朝目标旋转") == "AttackDirection"
    assert _intent(projection, "每2秒攻击") == "AttackInterval"
    assert not projection["publication"]["formulae"]

def test_heterogeneous_candidate_types_do_not_share_rules_without_evidence():
    result = reconstruct_mechanics(_neutral_card_and_relic_projection())
    assert result["mechanicFlows"][0]["candidateTypes"] == ["Ability", "Relic"]
    assert result["audit"]["genericCandidateAbstractionsResolved"] > 0
```

再使用 Registry 内存副本将对应 Lesson 改为 candidate，断言上述策略不再激活。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/test_system_lesson_runtime.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-runtime-red`

Expected: FAIL，现有模块尚未消费 Registry。

- [ ] **Step 3: 最小接入**

为 intent correction、pattern/formula guard、random guard、CandidateType resolution 和 candidate rule-sharing policy 增加稳定 `policyId`、`lessonRefs`，并在执行前调用：

```python
if registry.is_policy_enabled(policy_id, stage):
    apply_existing_policy(...)
```

现有语义算法和 Rule Authority 不变。

- [ ] **Step 4: 运行聚焦回归**

Run: `python -m pytest tests/test_system_lesson_runtime.py tests/test_rule_intelligence_pipeline.py tests/test_final_mechanic_reconstruction.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-runtime-green`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/rule_intelligence_pipeline.py backend/approved_information_recovery.py backend/mechanic_reconstruction.py data/planner_knowledge/approved-narrative-recovery-policies-v1.json data/planner_knowledge/mechanic-reconstruction-policies-v1.json tests/test_system_lesson_runtime.py
git commit -m "Bind rule intelligence policies to system lessons"
```

### Task 3: Lifecycle、Recovery、Dependency 与 Rule Value 消费 Lesson

**Files:**
- Modify: `backend/approved_information_recovery.py`
- Modify: `backend/recovered_rule_dependency_closure.py`
- Modify: `backend/mechanic_reconstruction.py`
- Modify: `data/planner_knowledge/recovered-rule-dependency-policies-v1.json`
- Test: `tests/test_system_lesson_recovery_runtime.py`

**Interfaces:**
- Consumes: approved Registry policy refs。
- Produces: Lesson-gated approved narrative recovery、dependency closure、final gap classification、trivial clause suppression 和 run-specific suppression。

- [ ] **Step 1: 写通用 Recovery 红测试**

```python
def test_confirmed_arena_summary_recovers_result_rule_but_draft_summary_does_not():
    confirmed = recover_approved_information(_arena_data(confirmed=True), _arena_chapters())
    draft = recover_approved_information(_arena_data(confirmed=False), _arena_chapters())
    assert confirmed["rules"][0]["intent"] == "VictoryCondition"
    assert draft["rules"] == []

def test_recovered_result_dependencies_and_rule_value_are_lesson_gated():
    result = close_recovered_rule_dependencies(**_neutral_dependency_case())
    assert result["unresolvedMechanicReferences"] == []
    final = reconstruct_mechanics(_neutral_composite_death_case())
    assert "停止攻击" in _final_text(final)
    assert "不能被选择" not in _final_text(final)
```

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/test_system_lesson_recovery_runtime.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-recovery-red`

Expected: FAIL，函数尚无 Registry 注入和 policy gate。

- [ ] **Step 3: 接入既有算法**

```python
registry = lesson_registry or load_system_lesson_registry()
if not registry.is_policy_enabled("recovery.approved_narrative", "approved_information_recovery"):
    return {"rules": [], "rejectedUnreviewedSourceIds": [], "sourceCount": 0}
```

Dependency contract、Final Gap requirement、clause value 和 run-specific value 分别使用自身 policy ref；禁用一条 Lesson 只影响对应策略。

- [ ] **Step 4: 运行聚焦回归**

Run: `python -m pytest tests/test_system_lesson_recovery_runtime.py tests/test_final_mechanic_reconstruction.py tests/test_feedback_regression_baseline.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-recovery-green`

Expected: PASS，Feedback 仍为 12 fully_reflected。

- [ ] **Step 5: 提交**

```bash
git add backend/approved_information_recovery.py backend/recovered_rule_dependency_closure.py backend/mechanic_reconstruction.py data/planner_knowledge/recovered-rule-dependency-policies-v1.json tests/test_system_lesson_recovery_runtime.py
git commit -m "Gate recovery and publication value with lessons"
```

### Task 4: Temporal State 与 Narrative Ordering 消费 Lesson

**Files:**
- Modify: `backend/requirement_temporal_probe.py`
- Modify: `backend/temporal_probe_orchestration.py`
- Modify: `backend/mechanic_reconstruction.py`
- Test: `tests/test_system_lesson_temporal_ordering.py`

**Interfaces:**
- Consumes: `temporal.persistent_state` 和 `renderer.mechanic_narrative_order` policy refs。
- Produces: Lesson-gated SpeedChangeCandidate 和稳定语义排序。

- [ ] **Step 1: 写通用红测试**

```python
def test_rate_delta_creates_candidate_not_approved_rule():
    result = run_targeted_temporal_probe(_neutral_drone_rate_series())
    assert result["ruleCandidates"]
    assert result.get("approvedRules", []) == []

def test_selection_rules_render_in_semantic_order_not_input_order():
    result = reconstruct_mechanics(_shuffled_neutral_selection_rules())
    assert _groups(result) == ["trigger", "state_entry", "candidate_generation", "selection", "effect", "state_exit", "refresh", "numeric_examples"]
```

禁用相应 Lesson 后断言候选或语义重排不再发生。

- [ ] **Step 2: 运行测试并确认失败**

Run: `python -m pytest tests/test_system_lesson_temporal_ordering.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-temporal-red`

Expected: FAIL。

- [ ] **Step 3: 注入 Registry 并保留现有权威边界**

Temporal Lesson 只允许 Observation → unreviewed Fact → RuleCandidate；Ordering Lesson 只重排 Final sentence projection，不修改底层 Rule。

- [ ] **Step 4: 运行 Temporal 与 Final 回归**

Run: `python -m pytest tests/test_system_lesson_temporal_ordering.py tests/test_requirement_temporal_probe.py tests/test_temporal_probe_production_integration.py tests/test_final_mechanic_reconstruction.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-temporal-green`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add backend/requirement_temporal_probe.py backend/temporal_probe_orchestration.py backend/mechanic_reconstruction.py tests/test_system_lesson_temporal_ordering.py
git commit -m "Apply system lessons to temporal and narrative policies"
```

### Task 5: Feedback → Lesson → Runtime → Test 固定基线

**Files:**
- Create: `scripts/generate_system_lesson_traceability.py`
- Create: `artifacts/system-lessons-2026-08-24/feedback-system-lesson-matrix.json`
- Create: `artifacts/system-lessons-2026-08-24/FEEDBACK-SYSTEM-LESSON-MATRIX.md`
- Modify: `tests/test_feedback_regression_baseline.py`
- Test: `tests/test_system_lesson_traceability.py`

**Interfaces:**
- Consumes: Registry、现有 12 Feedback baseline、真实 test node ids。
- Produces: 机器可核对和人读映射，且验证每条 approved Lesson 至少一个 runtime policy 和 test。

- [ ] **Step 1: 写 traceability 红测试**

```python
def test_every_feedback_maps_to_active_lesson_runtime_policy_and_existing_test():
    matrix = build_system_lesson_traceability()
    assert len({fid for row in matrix for fid in row["sourceFeedbackIds"]}) == 12
    assert all(row["runtimePolicies"] and row["tests"] for row in matrix)
    assert all(row["verificationStatus"] == "verified" for row in matrix)
```

- [ ] **Step 2: 运行红测试**

Run: `python -m pytest tests/test_system_lesson_traceability.py -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-trace-red`

Expected: FAIL，生成器尚不存在。

- [ ] **Step 3: 实现生成器并生成产物**

Run: `python scripts/generate_system_lesson_traceability.py`

Expected: 输出 11 条 Lesson、12 条 Feedback、0 悬空 policy、0 悬空 test。

- [ ] **Step 4: 运行全量测试**

Run: `python -m pytest -q -p no:cacheprovider --basetemp .test-tmp/system-lessons-full`

Expected: 0 failed。

- [ ] **Step 5: 提交**

```bash
git add scripts/generate_system_lesson_traceability.py artifacts/system-lessons-2026-08-24 tests/test_feedback_regression_baseline.py tests/test_system_lesson_traceability.py
git commit -m "Lock planner feedback into system lesson baseline"
```

