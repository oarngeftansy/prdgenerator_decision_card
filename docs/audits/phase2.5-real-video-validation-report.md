# Phase 2.5 Real-video Validation Report

## Outcome

Phase 2.5 is **blocked** and Phase 3 is **not allowed**.

The real sample reaches screenshot/video persistence and the existing gameplay review model, but the production runtime does not execute the Phase 2 chain:

`Gap → TargetedTemporalProbe → Temporal AtomicFact → Review Candidate`

This is not a Recall miss and is not a VLM-quality issue. It is a `gap_probe_mapping_failure`: the Phase 2 domain functions exist, but no production API or job-processing path calls them.

## 1. Test material

- Baseline: `e70f5ac5af9b0b0bed02d24b528f2f2fc7608800`
- Current-HEAD server: isolated port `8011`; the pre-existing port `8000` process was not stopped.
- Real audited project: `一路狂飙交互与玩法策划案`
- Existing real job: `4180cd72eeaa4819be41db50bb4c5011`
- Primary evidence: 15 ordered screenshots
- Auxiliary video: `飞书20260803-151413.mp4`, 69,801,775 bytes
- Existing formal audit evidence includes vehicle progression, normal enemies, repeated combat, boss appearance/death, and settlement windows.

The working tree already contained user-owned changes and numerous untracked audit/test artifacts. None were overwritten, reset, stashed, or committed.

## 2. Gold Temporal Responsibilities

The machine-readable ledger defines 15 responsibilities covering:

- vehicle visual displacement, movement candidate, and unknown movement driver;
- normal-enemy first appearance versus unsupported spawn interval/source;
- observed attack timestamps versus configured attack interval;
- boss first appearance, death, post-death timing, and hidden victory condition;
- candidate probability, replacement, weight, and guarantee as video-ineligible mechanisms.

## 3. Actual generated probes

Zero.

On current HEAD, the normalized review response contains empty `temporalProbeRequests` and empty `temporalEvidence`. The auxiliary video remains persisted with status `pending` in the historical real task.

Static call-lineage evidence:

- `backend/requirement_temporal_probe.py` defines `build_targeted_probe_requests` and `run_targeted_temporal_probe`.
- `backend/gameplay_review_service.py` defines `add_targeted_temporal_probe_result`.
- All invocations of these functions are in tests.
- `backend/server.py` neither invokes them nor exposes a temporal-probe endpoint.

Therefore UI upload/reopen cannot reach a real Probe, VLM call, Temporal Fact, or Review Candidate without bypassing the product workflow.

## 4. Evidence lineage

The lineage stops here:

`screenshots + auxiliary video → persisted job → existing screenshot analysis/review model → STOP`

The requested lineage does not occur:

`Schema Gap → Probe Request → candidate windows → VLM observation → Temporal Fact`

No per-Probe lineage is claimed. The ledger records one blocking row with `VLMCalls=0` and `finalOutcome=blocked_before_probe_creation`.

## 5. Planner Review result

Not testable end to end. The UI can render a pre-populated temporal candidate and route its decision through the existing review action, as covered by integration tests, but the real runtime never populates such a candidate.

Using an internal helper to inject a candidate would violate the Phase 2.5 requirement and was not used as acceptance evidence.

## 6–9. Quality metrics

- Detection Recall: **not measurable**
- Candidate Precision: **not measurable**
- Over-inference Rate: **not measurable**
- Unsupported Final Rule Count: **not measurable for the requested E2E chain**

Zero generated candidates must not be reported as zero unsupported rules: the authority path was never exercised.

## 10. Probe exhaustion

Not testable in the real workflow because no Probe is created. Unit tests cover the state machine, but that is insufficient for this phase.

## 11. Identity / Reference Frame cases

Not testable in the real workflow. No candidate windows, tracks, identity grade, or reference-frame status are produced at runtime.

## 12. UX Gap

The most severe UX gap is absence rather than wording: the planner has no real temporal candidate to inspect or approve. Consequently the UI cannot show source Gap, candidate window, before/after evidence, identity uncertainty, or reference-frame uncertainty for an uploaded video.

## 13. Failure Taxonomy

| Taxonomy | Count | Evidence |
|---|---:|---|
| `gap_probe_mapping_failure` | 1 blocker | no production caller/route for Phase 2 probe creation and execution |
| `review_projection_failure` | 0 proven | projection accepts injected data, but runtime never supplies it |
| `authority_leak` | 0 observed | no temporal data entered authority at all |
| `false_rule_promotion` | 0 observed | no temporal candidate was produced |
| other temporal failure classes | not assessable | blocked upstream |

## 14. Architecture Regression

Yes—relative to the declared Phase 2 closure contract, the real product chain is missing its production seam. The implementation is complete only at domain/unit/integration level, not at uploaded-video E2E level.

This finding should be corrected before repeating Phase 2.5. It must be solved generically; adding gameplay-specific prompts or injecting fixture candidates would not satisfy the gate.

## 15. Phase 3 decision

**Do not enter Phase 3.**

The gate fails because `Temporal review chain works end-to-end` is false. Precision/authority safety still takes priority over Recall, but safety cannot be certified until a real candidate traverses Review → Guard → Publication → Final.

Required next action is a narrowly scoped Phase 2 closure repair: connect the existing domain functions to the real job/review runtime, retain unreviewed authority boundaries, expose generated candidates in the existing review UI, and then rerun this exact validation without internal injection.
