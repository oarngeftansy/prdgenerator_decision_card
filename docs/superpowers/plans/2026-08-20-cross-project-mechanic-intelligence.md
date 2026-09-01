# Cross-Project Mechanic Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect and compose multiple evidence-backed mechanics for arbitrary projects using declarative JSON and one generic graph engine.

**Architecture:** A versioned JSON graph stores taxonomy, patterns, signals, shared concepts and responsibility profiles. `backend/mechanic_knowledge_graph.py` validates and queries that graph; recognition and activation consume normalized project evidence without mechanic-specific Python branches.

**Tech Stack:** Python 3.12, JSON, pytest.

## Global Constraints

- Pattern data has `contentAuthority=none` and contains no current-project answers.
- Genre labels never activate mechanics.
- A feature may detect any number of patterns.
- Responsibilities activate dynamically from Evidence, current Rule and cross-system relationships.
- Existing Evidence/Fact/Approved Rule authority and pipeline phases remain unchanged.

---

### Task 1: Graph contract and loader

**Files:**
- Create: `data/planner_knowledge/mechanic-knowledge-graph-v1.json`
- Create: `backend/mechanic_knowledge_graph.py`
- Create: `tests/test_mechanic_knowledge_graph.py`

**Interfaces:**
- Produces: `load_mechanic_graph(path)`, `validate_mechanic_graph(graph)`, `MechanicKnowledgeGraph`.

- [ ] Write tests that reject dangling edges, project answers and invalid levels.
- [ ] Run the tests and observe contract failures.
- [ ] Implement generic loading, indexing and validation.
- [ ] Run the tests and commit the graph contract.

### Task 2: Evidence-driven multi-pattern recognition

**Files:**
- Modify: `backend/mechanic_knowledge_graph.py`
- Modify: `tests/test_mechanic_knowledge_graph.py`

**Interfaces:**
- Consumes: normalized evidence records with `evidenceId`, `signalIds`, `entityIds`.
- Produces: `detect_mechanics(evidence, context)`.

- [ ] Write a failing test detecting dash, lock-on, melee combo, parry, boss encounter and boss phase together.
- [ ] Verify genre-only input detects nothing.
- [ ] Implement declarative any/all/minimum signal evaluation and evidence provenance.
- [ ] Run focused tests and commit recognition.

### Task 3: Dynamic responsibility activation and composition

**Files:**
- Modify: `backend/mechanic_knowledge_graph.py`
- Modify: `tests/test_mechanic_knowledge_graph.py`

**Interfaces:**
- Produces: `activate_responsibilities(...)`, `compose_project_graph(...)`, `discover_missing_requirements(...)`.

- [ ] Write failing tests for optional penetration, shop refresh cost and shared resource/event flow.
- [ ] Implement declarative activation contracts and shared-concept composition.
- [ ] Verify unsupported responsibilities remain dormant and do not become gaps.
- [ ] Commit composition.

### Task 4: Cross-project migration benchmark

**Files:**
- Create: `tests/fixtures/cross-project-mechanic-cases-v1.json`
- Create: `tests/test_cross_project_mechanic_benchmark.py`

**Interfaces:**
- Consumes: brief gameplay descriptions expressed as sparse screenshot/video/parameter facts.
- Produces: per-case recall, precision and planning-coverage assertions.

- [ ] Add at least 25 system, gameplay and hybrid cases.
- [ ] Assert expected and forbidden patterns plus required responsibilities.
- [ ] Run the complete benchmark and relevant regression tests.
- [ ] Commit the benchmark.
