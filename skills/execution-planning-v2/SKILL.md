---
name: execution-planning-v2
description: Convert reconstructed gameplay into implementation-ready planning rules and close every applicable planning gap even when source evidence is incomplete.
---

# Execution Planning v2

## Objective

Produce a canonical execution plan that programmers, numeric designers, UI designers and QA can implement and verify without another interpretation pass.

## Planning hierarchy

Use a dynamic `System -> Subsystem -> Mechanism -> RuleGroup` hierarchy. Do not force a fixed chapter count and do not merge heterogeneous mechanisms merely to fit a template.

## Rule closure contract

For every applicable mechanism, close the relevant parts of:

- trigger and preconditions;
- state before / state after;
- execution sequence and result;
- lifecycle: initialize, activate, change, expire/cleanup;
- branches, failure paths, boundaries and concurrency where relevant;
- dependencies, inputs, outputs and ownership;
- random pool/filter/count/duplicate/reroll/empty-pool rules when relevant;
- formula/calculation attribution and configurable parameters when relevant;
- persistence, inheritance and reset scope;
- QA acceptance cases.

## Evidence and decision authority

1. Preserve confirmed rules.
2. Evidence insufficiency is never a planning stop condition.
3. If a missing rule is primarily reconstruction of the original mechanic, close it as `inferred`.
4. If a missing rule requires a product/design choice to make implementation complete, select one concrete default and close it as `proposed`.
5. `inferred` and `proposed` are publication metadata. The visible rule copy must be decisive and must not contain “可能”“待确认”“根据素材推测”“建议可以”“【推断】”.
6. Explicit irreconcilable conflicts may remain `conflict`; ordinary uncertainty must not be converted into a blocker.
7. Do not fabricate formal config IDs, field names, backend APIs or technical architecture details absent from inputs.

## Final authority

The canonical structured plan is the source of truth. Final Markdown, web preview and Feishu output are projections from that structure; renderers must not independently rewrite gameplay rules.
