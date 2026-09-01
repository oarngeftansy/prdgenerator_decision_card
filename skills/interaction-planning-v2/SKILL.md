# Interaction Planning v2

## Purpose

Convert the canonical gameplay rule model into a reviewable planning sketch that explains how player actions, system actions, states, transitions, feedback, failures, and recovery connect. This layer is a projection and review layer; it does not become a second gameplay-authority model.

## Authority

- Input authority is the current canonical System -> Subsystem -> Mechanism -> RuleGroup / Rule Model.
- Every sketch interaction must trace back to one or more canonical rule IDs.
- The sketch may organize rules for communication, but must not rewrite, weaken, or replace them.
- A Golden Sample may inform expected execution depth and readability. It must never impose its nouns, chapter count, mechanism list, screen list, or interaction pattern on another project.

## Mechanic-agnostic contexts

Do not assume every mechanic is a screen flow. Select the context that matches the mechanic:

- `ui_surface`: menus, dialogs, HUD controls, lists, buttons, direct selection and other explicit UI interaction.
- `gameplay_context`: movement, combat, placement, targeting, timing, waves, physical/world interaction and other in-play behavior.
- `system_context`: automatic simulation, economy, resource conversion, scheduling, persistence and other rules that do not need a fake screen.

The context taxonomy is descriptive, not a fixed product directory. Add or omit contexts according to the actual canonical mechanics.

## Required interaction closure

For each applicable canonical rule, expose the dimensions that actually matter. Typical dimensions include trigger, preconditions, player/system action, state change, result, feedback, exception/failure, lifecycle, persistence/reset, dependency and QA acceptance cases. Do not force irrelevant fields solely because they occurred in another sample.

The review must detect:

1. canonical rules missing from the sketch;
2. sketch interactions with no canonical rule reference;
3. transitions whose origin/result cannot be traced to the rule model;
4. duplicated interactions that conflict on the same condition;
5. unreachable or dead-end states when the canonical rule set provides enough information to identify them.

## Provenance and display

- `confirmed`: normal display.
- `inferred`: yellow display.
- `proposed`: yellow display.
- `conflict`: red display only when explicit source rules cannot be resolved to a unique rule.

`inferred` and `proposed` are complete, implementation-ready planning states. They do not block the interaction review merely because evidence is weak. Never insert provenance labels or hedging language into the user-visible rule sentence.

## Output principle

The planning sketch is the interaction-review representation of the same canonical plan. It must work for arbitrary gameplay families and must remain traceable enough that a designer can review a node/edge and navigate back to the rule that created it.