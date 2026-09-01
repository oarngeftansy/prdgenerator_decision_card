# Provenance rules

## Evidence priority

1. Confirmed planner decision: authoritative for intended behavior, never retroactively presented as screenshot fact.
2. Configuration table or named reference-document block: authoritative for fields, formulas, ranges, reset and persistence when the wording is explicit.
3. Video sequence: supports visible order, state transition and feedback; it does not prove hidden probability or persistence beyond the observed interval.
4. Screenshot: supports visible objects, labels, state, layout and displayed values only.
5. Context inference: publishable only when the chain below is complete.

## Required record

Each claim records `text`, `sourceType`, `sourceIds`, and `carrier`. For `context_inference`, also record:

- `premises`: direct observations used;
- `steps`: the causal or contrast reasoning;
- `alternatives`: other explanations considered;
- `confidence`: low, medium, or high;
- `publicationAllowed`: whether the evidence is strong enough to enter confirmed prose.

Low-confidence inference or `publicationAllowed: false` becomes a decision card, not document copy.

## Six evidence-conditioned axes

| Axis | Include when | Suitable carrier |
|---|---|---|
| Content inventory | Evidence distinguishes multiple named objects or variants | compact list or table |
| Configuration | A source exposes fields, units, ranges, defaults or sources | one configuration table |
| Execution sequence | Order changes the result or a multi-step algorithm is explicit | numbered steps |
| Formula | An expression and variable meaning are sourced | formula block; example only when all values are known |
| Boundary | Failure, empty, cap, repeat, invalid or re-entry behavior is evidenced | adjacent clause or focused list |
| Lifecycle | Reset, persistence, temporary storage or cross-session behavior is evidenced | adjacent clause or focused paragraph |

The six depth axes are the minimum publication gate, not the entire content model. Also check three cross-cutting dimensions when supported:

| Dimension | Include when | Suitable carrier |
|---|---|---|
| Interaction and feedback | Player input, toast, modal, selection state or system response is evidenced | causal prose or page board |
| Runtime responsibility | Client/server ownership, precomputation, validation or synchronization timing is explicit | responsibility sequence |
| Presentation contract | Animation order, display format, sorting, colors or carrier authority affects acceptance | presentation rules beside the relevant behavior |

A screenshot or short video cannot authorize configuration ownership, a hidden formula, persistence, reset timing, or client/server responsibility. Those require a reference document, configuration table, confirmed planner decision, or a fully replayable inference chain.

## Positive and negative examples

Positive: a reference block says reroll clears the temporary result, restarts at step one, accumulates cost in the current level, and resets when the level ends. Preserve that causal order in one compact paragraph or a short ordered list.

Negative: a screenshot shows a refresh button with “1/1”. It proves the visible count, but not how the count is earned, whether it resets next wave, or whether refresh is without replacement.

Positive: a short movement rule and a short health rule share one “核心战斗” section and each use one dense paragraph.

Negative: expand both into identical headings for normal flow, key rules, special cases, validation and configuration source.
