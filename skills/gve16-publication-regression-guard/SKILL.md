---
name: gve16-publication-regression-guard
description: Audit and repair a GVE16-style gameplay planning document whose internal rules appear complete but whose final web or Feishu publication is shallow, misplaced, visually detached, or semantically incomplete.
---

# GVE16 Publication Regression Guard

Use this skill when the user judges the final document, not the internal matrix, as the product.

## Authority and scope

- Treat the user's current audit and approved project evidence as the backlog authority.
- Use GVE16 for execution depth, information organization, carrier choice, and layout relationships. Do not copy its project-specific values, names, fields, weights, or mechanic answers.
- A related sentence or keyword is not satisfaction. The published text must answer the atomic question's subject, condition, timing, action or algorithm, branch, result, parameter source/consumer, attribution, and reset where applicable.
- Tests, review data, raw nodes, and closure flags are supporting evidence only. Start acceptance from the final web/Feishu document and trace backward.

## Body-first repair contract

1. Compare the benchmark and current final document chapter by chapter and paragraph by paragraph.
2. For each non-equal atomic item, locate the exact published sentence, table row, diagram, or image. If it cannot be located, publication is open even when an approved rule exists.
3. Ensure gameplay prose is deterministically projected from approved structured rules. Measure and expose any contribution from legacy planner sections, summaries, fallbacks, hardcoded prose, or LLM regeneration.
4. Reject one-line mechanism summaries when the benchmark exposes multiple executable questions. Expand the current project's own answer without importing benchmark answers.
5. Keep one primary owner and one primary rule definition. Other chapters reference or consume it; they do not duplicate it.
6. Keep parameter values in the relevant business table, while prose explains trigger, use, consumer, calculation, lifecycle, and boundary. A table alone does not close a gameplay rule.
7. Place each necessary diagram or explanatory image immediately after the paragraph or table it explains. A detached gallery or end-of-document image dump does not satisfy the body.
8. Use native document heading levels and automatic numbering for the final Feishu body. Do not simulate numbering with typed numeric prefixes.
   The native numbering must wrap the real chapter bodies; a detached ordered
   heading index labelled “自动编号目录” is not a numbered final document.
9. Open the final body with a concise gameplay overview that answers player
   objective, core loop, in-run growth, and win/loss settlement before readers
   encounter the detailed chapter directory.
10. Exclude review language, internal IDs, lineage, proposals, alternatives, implementation notes, generic fallback, and unsupported claims from final publication.
11. Make the reading path linear before deep system detail: overview, complete
    run lifecycle, then the natural owners in encounter order. A lifecycle stage
    proven by rules or evidence must also have a visible owning subsection; it
    may not survive only as two transition sentences in another chapter.

## Visual and carrier regression checks

- A flow diagram must preserve actions, decisions, branches, loops, entry, and exit; a vertical explanation strip is not a flow diagram.
- Text, screenshots, markers, arrows, labels, section titles, and image captions must not overlap or clip at the remote default overview.
- A numbered screenshot marker must be one node containing both the circle and digit, anchored inside the actual described component region. The adjacent same-number text must describe that region's function and interaction.
- Keep independently contracted boards separate. Do not merge UE flow, planning sketch, and competitor reference merely because they share media.
- Treat the planning sketch as a screenshot-first page/state map: every observed page, popup, or material state gets its own representative screenshot with adjacent visible UI composition, and confirmed state-to-state links connect the screenshots. A handful of mechanic summary cards is not a GVE16 planning sketch, even when the bullets are correct.
- Feishu raster images must be uploaded as whiteboard-scoped media tokens. Do not trust SVG-embedded raster images: Feishu may strip them while leaving an apparently valid board.
- Write board structure before media. A later overwrite can invalidate uploaded images.
- Verify both remote preview and raw nodes: visible nonzero images, valid tokens, readable scale, connector direction, no accidental duplicates, and no clipped titles.

## End-to-end acceptance

For every audited item, require:

`source → approved data → rule/parameter/presentation/transition → assembly input → final artifact → Feishu node → rendered text/visual → semantic and visual verification`

Record the exact final rendered text, not only IDs. Mark the failure stage when the chain breaks.

Before claiming completion, reverse-sample from Feishu, verify that approved rules and presentation facts were not lost, and confirm zero unsupported claim, wrong owner, generic fallback, duplicate primary rule, satisfaction false positive, approved-rule publication loss, presentation loss, structural diagram loss, parameter-table loss, or unreadable remote visual.

## Previously observed failures and fixes

- Matrix-only closure: require exact final text and remote node evidence.
- Keyword false positives: validate the atomic business answer, not topical similarity.
- Legacy/fallback overwrite: make approved structured rules the deterministic final source and report source composition.
- Cross-delivery loss: project each approved fact to every declared consumer carrier.
- Blank Feishu screenshots: upload whiteboard-scoped media and reject zero-size or stripped image shells.
- Number/circle drift: render one centered ellipse node and derive its coordinate from the component target box.
- Wrong numbered region: store normalized target boxes and validate marker containment.
- Arrow/title/text occlusion: reserve title and label safe areas, route connectors around content, then inspect the remote export.
- Flowchart degraded into explanation art: gate on real decisions, branches, loops, entry, and exit.
- Section title clipping: keep a safe top margin and a separate board header outside connector routes.
- Detached numbering index: number the actual chapter sections with Feishu
  native list sequence and reject any extra “automatic-numbering directory”.
- Web/Feishu opening drift: project the same overview and inline board/P5/P6
  anchors from one canonical body, then verify their rendered order in both.
- Hidden lifecycle owner: if the flow contains normal combat → boss → cleanup →
  settlement, require both 普通怪物 and 首领 under 怪物 and keep the linear run
  flow visible before the detailed owner chapters.
- Planning sketch collapsed into summary cards: rebuild from the complete
  observed state sequence, keep one screenshot and one adjacent composition
  block per state, and connect only observed or approved transitions. Keep UE
  decisions/branches in the UE board instead of duplicating them as diamonds.
