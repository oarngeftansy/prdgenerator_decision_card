# Phase 1 Closure / Regression Baseline Report

## Baseline and isolation

- Audited baseline: `95e89483261846c8c133812c038c5d8dc9287cde`.
- The original working-tree JUnit contained 70 failures. The ledger also retains the one exact-key auxiliary-video failure fixed by `95e8948`, producing the requested original total of 71.
- A clean archive of HEAD was also attempted, but ignored fixtures, job snapshots, and contact sheets are not present in a Git archive. Its 84 failures are therefore not a valid product baseline and are excluded from the ledger.
- `scripts/publish_current_alignment_to_feishu.py` is a pre-existing user modification and is excluded from the closure commit.
- The two modified files under `artifacts/gve16-complete-delivery-gap-audit-2026-08-19/` are test-generated drift and are excluded from the closure commit.

## Original 71 failures

The assertion-level source of truth is `docs/audits/phase1-closure-failure-ledger.json`.

| Classification | Count |
| --- | ---: |
| `real_regression` | 26 |
| `obsolete_expectation` | 14 |
| `implementation_coupled_test` | 30 |
| `workspace_contamination` | 1 |
| `flaky_environment` | 0 |
| `unknown` | 0 |
| **Total** | **71** |

The 26 regression assertions do not represent 26 independent defects: 24 assertions cascaded from one missing approved-rule projection; two assertions exposed a stale UE-flow UI contract.

## Real regressions fixed

1. The formal publication generator omitted the approved L-15/PR-19 failure/result rule while reorganizing canonical ownership. The rule now projects once under its canonical `关卡结算` owner.
2. The review UI still exposed the retired UE-flow sub-step and legacy 2.1/2.2 numbering. The active flow now goes directly to the planning-sketch preview.
3. A newly strengthened closure test found that v2 review operations could persist a stale `ruleIntelligenceProjection`; undo/redo could therefore disagree with Rule confirmation. The service now rebuilds the projection after each material operation.
4. A newly strengthened same-source test found that delivery alignment stringified structured flow dictionaries while the renderer consumed their `text` fields. Canonical Web/Feishu contract extraction now uses the same textual projection.

## Retired contracts and replacements

The retired contract required UE, planning, and competitor boards in Final/publication and kept UE/competitor confirmation checkpoints alive. The current product contract is unique: Final permits only the planning sketch; UE, competitor, and presentation-only carriers must have zero Final presence.

Old positive assertions were replaced, not merely deleted:

- planning board remains publishable;
- UE board does not enter Final;
- competitor board does not enter Final;
- presentation-only evidence does not enter Final;
- retry/resume cannot restore legacy boards;
- native delivery exports only the planning board;
- review navigation has no UE-flow confirmation step.

Tests coupled to a fixed two-board FakeCli, a fixed three-chain set, exact response-key sets, or byte equality between independently evolved historical snapshots were rewritten around their product-level contract. No test was deleted solely to make the suite green.

## Phase 1 authority and guard closure

The retained regression suite covers:

1. Rule Intent separation.
2. Spawn Gap closure.
3. visual position change as Movement Candidate/Gap.
4. inferred pattern not becoming formula.
5. random not implying equal probability or sampling without replacement.
6. canonical owner uniqueness.
7. schema closure.
8. Review/Final consistency, including revision and undo/redo confirmation.
9. visual movement not becoming a confirmed movement rule.
10. similar rules with different conditions remaining distinct.
11. presentation/UE/competitor Final pollution equal to zero.
12. Web and Feishu consuming the same PublicationProjection contract.

The final contamination audit is recorded in `docs/audits/phase1-final-contamination-audit.json`; every prohibited category is zero.

## Final verification

```text
1449 passed, 0 failed, 4 warnings in 17.89s
```

The warnings are deprecation/cache warnings and do not change test outcomes. A first run without an explicit repository-local `--basetemp` hit Windows permission errors under `%TEMP%`; the authoritative run used an isolated repository-local pytest base directory.

Phase 1 is closed when this report, ledger, tests, and fixes are committed together, while the user-owned Feishu script and generated artifact drift remain unstaged.
