# Phase 5.4.5 Expanded External Skill Source Audit

Date: 2026-08-17
Mode: research/distillation only; no skill execution, runtime installation, Rule/Gap/Renderer/GameRuleModel/P4 mutation

## Source-location result

The requested files were **not found in the locally searchable installed Codex skill/plugin directories or the project workspace**. The similarly named local files (for example Figma design-system material) are unrelated and were not used. The audit therefore used the two authors' primary GitHub repositories and their raw Markdown sources. No standalone `system.md` or `systems.md` file was discoverable in Game Development Orchestrator; system-design reasoning was audited where it actually appears across genre, balance/economy, progression, level-design, and implementation/config references.

Primary repositories:

- Game Development Orchestrator: <https://github.com/lorenzopapa2/game-development-orchestrator>
- Claude-Code-Game-Studios: <https://github.com/Donchitos/Claude-Code-Game-Studios>

## Adapter boundary

Every accepted pattern is anonymized and has `contentAuthority: none`. It may emit only a `possible mechanic dimension` or `possible rule dimension`. It cannot prove existence, answer a rule, or create `missingGameRules`.

`ExternalGameDesignCorpus → possible dimension → Phase 5.4.4 MechanicScope inference → confirmed/strongly_implied only → GameRuleModel`

`possible`, `unsupported`, and `contradicted` remain outside Planner Review. External numeric examples, genre norms, system names, chapter layouts, commands, roles, and production workflow are never copied as project facts.

## Source-by-source disposition

| Source Skill / area | Original Purpose | Useful Pattern | Risk | Adapted Reverse-design Pattern | Corpus Category | Accept / Reject |
|---|---|---|---|---|---|---|
| GDO — genre templates / system inventory | Forward-design a genre-appropriate loop and feature set | Separate core loop, session loop, meta loop; inspect mechanics implied by an already evidenced player action | Genre checklist can fabricate acquisition, unlock, loadout, crafting, etc. | If evidence establishes a loop/action, inspect its entry, action, resolution, outcome and lifecycle companions as **possible** dimensions only | `mechanic_scope_pattern` | Accept after anonymization and gate |
| GDO — genre recommendations and benchmark package | Recommend conventional systems and values for genres | None as project evidence | “Typical” mechanics/values become false existence or false answers | Do not retain genre-specific inventory, target values, formula constants, rarity ratios or mandatory feature combinations | `reject` | Reject |
| GDO — balance-economy / combat numerics | Design formulas, curves and tuning tables | Inputs, output, bounds, interaction effects, outcome cadence, TTK/resource pressure | Formula archetype or benchmark may be selected without evidence | For an evidenced outcome, ask which player-facing parameters govern magnitude, cadence, range, probability, cap and trade-off; values remain unknown | `parameter_pattern` | Accept |
| GDO — balance-economy / difficulty | Create intended challenge curve and modes | Phase-to-phase pressure, recovery, spikes, counterplay, dominant strategy | Forward target curve can be mistaken for reconstructed behavior | Where stages/difficulty changes are evidenced, inspect what observable parameter/state changes and whether recovery/counterplay exists | `balance_pattern` | Accept |
| GDO — balance-economy / source-sink | Design currencies, prices and affordability | Source, sink, converter, storage, cost, reward, retention/reset and enabled action | Assumes an economy merely because the genre often has one | Only for an evidenced resource/transaction, inspect flow and player consequence as possible dimensions | `economy_pattern` | Accept |
| GDO — balance-economy / probability | Design loot/gacha/pity systems | Eligibility, weighting, replacement/duplicates, guarantee, reset scope, cost/time consequence | Gacha/loot/pity template can fabricate random systems | Only for an evidenced random choice/drop, inspect these dimensions; duplicate/pity remain unsupported until evidence promotes them | `randomization_pattern` | Accept |
| GDO — economy_and_progression mathematical models | Supply “proven” formula families for combat, growth, economy and RNG | Formula contract shape; caps, diminishing returns, scaling phases and reset | Prescriptive language and numeric defaults falsely claim authority | Retain only the questions “what inputs, transform, bounds, lifecycle and player-visible result?”; discard every default formula/value | `parameter_pattern` | Accept in reduced form |
| GDO — economy_and_progression normative models | Choose an ideal formula/economy for a new game | Forward selection rationale | Solves a design problem rather than reconstructing observed rules | Keep outside the corpus unless converted to a dimension-only question; raw recommendation is not reverse evidence | `forward_design_only` | Reject from corpus |
| GDO — level design | Design level purpose, pacing, encounters, routes and boss tests | Entry/exit, objective, completion/failure, gating, spatial constraint, encounter composition, phase transition | Level-purpose taxonomy can invent teaching/rest/reward/boss functions | If a level/section/encounter exists, inspect observable entry, objective, route constraint, escalation, completion/failure and transition dimensions | `game_rule_pattern` | Accept |
| GDO — level design target experience | Author desired emotion, teaching intent and pacing arc | Useful for new content ideation | Intent cannot be reconstructed solely from a template | Do not infer intended emotion or teaching goal without project evidence; preserve at most as later validation hypothesis | `forward_design_only` | Reject from corpus |
| GDO — implementation, config/data-model portions | Specify data-driven content and configuration schemas | Object references can reveal possible dependencies; gameplay-affecting fields expose parameter dimensions | Schema presence is mistaken for mechanic existence; file/type/ID becomes “game rule” | Treat references as relationship hints only; ask whether referenced objects and player-visible effects have independent Evidence/Fact/Rule/UI support | `system_dependency_pattern` | Accept |
| GDO — implementation runtime/architecture portions | Plan code structure, update loop, events, persistence and tooling | None for player rule reconstruction by itself | Event ordering, cache, serialization, update timing, fallback and ownership pollute gameplay reasoning | Quarantine unless an independent player-visible rule is evidenced | `implementation_only` | Reject from corpus |
| CCGS — map-systems | Extract explicit and implicit systems and map dependencies/design order | Explicit action/system inventory; upstream inputs, downstream outputs, hard/soft dependencies | “Implicit” companion system can be promoted as real | Explicit evidence seeds scope; implicit systems stay possible; dependency is promoted only by independent relationship/UI/data evidence | `mechanic_scope_pattern`, `system_dependency_pattern` | Accept |
| CCGS — design-system | Forward-author a complete GDD with rules, states, formulas, dependencies and tuning knobs | State/transition, capability/constraint, trigger/result, formula/parameter, dependency and lifecycle questions | Completeness template creates gaps for absent mechanics and excessive edge cases | Apply a rule-dimension checklist only after a scope item passes existence gating; do not copy its document sections | `game_rule_pattern`, `parameter_pattern` | Accept |
| CCGS — design-system production handoff/edge completeness | Make a design implementation-ready and exhaustive | None automatically planner-salient | “Programmer has no questions” confuses implementation completeness with game-rule evidence | Exclude code-facing acceptance, edge enumeration and handoff structure unless it changes a player-visible outcome | `implementation_only` | Reject from corpus |
| CCGS — design-review, game-designer lens | Review player fantasy, loops, clarity, motivation, feedback, progression and failure recovery | Player entry/use/result; nested loops; failure cost/recovery; retained/reset state | Reviewer preference or desired fantasy can become invented intent | For evidenced loops/failure/progression, inspect the corresponding player-visible dimensions; desired fantasy remains forward-only | `game_rule_pattern`, `progression_pattern` | Accept in reduced form |
| CCGS — design-review, systems-designer lens | Review formulas, economies, dependencies, interaction matrices and tuning | Cross-system contract, resource flow, parameter impact, feedback/runaway loops | Matrix/template completeness fabricates types, statuses or resources | Use interaction/dependency checks only where both endpoint systems already have evidence; surface inconsistency rather than inventing bridge rules | `system_dependency_pattern`, `balance_pattern`, `parameter_pattern` | Accept |
| CCGS — design-review orchestration and role routing | Coordinate specialist review and workflow | None in the corpus | Workflow metadata masquerades as design knowledge | Discard agents, routing, review commands, output paths, approvals and production sequencing | `reject` | Reject |
| CCGS — game-designer agent | Forward-design loops, progression, economy, feedback and experience | Acquisition/use/growth/reward/failure/recovery/lifecycle dimensions | Theory vocabulary and ideal loops can imply current-project intent | Convert only to anonymous conditional checks attached to evidenced mechanics | `progression_pattern`, `game_rule_pattern` | Accept in reduced form |
| CCGS — systems-designer agent | Create mathematical systems, interaction matrices and balance models | Input/output/bounds, tunable parameter effect, dependency contracts, positive/stabilizing feedback | Completeness pressure and sample formulas create unsupported systems/answers | Inspect parameter and dependency dimensions only after endpoint mechanics exist; never import values/formulas | `balance_pattern`, `parameter_pattern`, `system_dependency_pattern` | Accept in reduced form |

## Distilled pattern delta

This expanded pass retains **34 accepted anonymous patterns** across the eight corpus-eligible classes. They are dimension prompts, not instantiated mechanics:

| Category | Accepted | High-value reverse-design contribution |
|---|---:|---|
| `mechanic_scope_pattern` | 4 | Explicit-action decomposition; nested lifecycles; section/encounter scope; explicit-vs-implicit separation |
| `game_rule_pattern` | 7 | Entry, action, resolution, outcome, state transition, constraints, completion/failure and recovery |
| `system_dependency_pattern` | 5 | Upstream/downstream contracts, ownership, hard/soft dependency, bidirectional consistency, reference hints |
| `progression_pattern` | 3 | Source, transformation/result, cap/cost, strategic effect, persistence/reset; session vs meta lifecycle |
| `randomization_pattern` | 3 | Eligibility, weight, constraints, duplicate/miss treatment, guarantee and reset |
| `economy_pattern` | 3 | Source/sink/converter/storage, affordability, reward-cost-time coupling |
| `balance_pattern` | 5 | Phase outputs, recovery, dominance, interaction and runaway/stabilizing loops |
| `parameter_pattern` | 4 | Player-visible magnitude, cadence, spatial reach, probability/cap/unit and downstream outcome |
| **Total eligible** | **34** | Possible dimensions only |

Excluded disposition:

- `forward_design_only`: **5** patterns — intended fantasy/emotion, ideal pacing, genre feature selection, recommended formula selection, target content composition.
- `implementation_only`: **7** patterns — event/update order, polling/cache, serialization/IDs, architecture/code ownership, tooling/debugging, technical recovery/fallback, implementation handoff detail.
- `reject`: **8** patterns — template auto-instantiation, numeric imports, implicit-as-confirmed, universal rules, workflow/role commands, exhaustive edge-gap generation, genre union, “implementable means gameplay” reasoning.

## Duplicate and GVE16 overlap audit

Cross-source semantic duplicates were collapsed before counting:

| Duplicate cluster | Repeated in | Canonical retained pattern |
|---|---|---|
| Core/session/meta loops | genre templates, game-designer, design-system | Nested lifecycle scope |
| Sources/sinks/converters | balance-economy, economy_and_progression, systems-designer | Evidenced-resource flow |
| States/transitions/constraints | design-system, design-review, game-designer | Player-visible state contract |
| Inputs/outputs/dependencies | implementation config, map-systems, design-system, systems-designer | Bidirectionally evidenced system contract |
| Formula inputs/outputs/bounds | balance-economy, mathematical models, design-system, systems-designer | Player-outcome parameter contract |
| Progression source/result/reset | genre, balance, game-designer, systems-designer | Evidenced progression lifecycle |

Raw useful candidates before collapse: **52**; duplicate candidates collapsed: **18**; canonical accepted patterns: **34**.

GVE16 already substantially covers **22/34** patterns: observable player flow, rule expression, state/result, chapter organization, parameter presentation, constraints, failure/completion and execution-level clarity. External skills do not replace that expression authority.

The **12 newly useful or materially strengthened patterns** are chiefly system-planning diagnostics rather than prose structure:

1. hard vs soft dependency;
2. bidirectional dependency consistency;
3. explicit-vs-implicit scope quarantine;
4. within-session vs cross-session persistence/reset;
5. random eligibility before weighting;
6. duplicate/miss consequence coupled to probability;
7. guarantee/pity reset scope (conditional only);
8. economy converter and storage/retention;
9. reward-cost-time-to-goal coupling;
10. runaway positive loop vs stabilizing counter-loop;
11. phase-by-phase dominance/recovery check;
12. explicit player-facing parameter dimensions: cadence, spatial reach, magnitude and caps/units.

These additions answer “what should a systems designer inspect after existence is evidenced.” GVE16 remains responsible for how a mature execution plan organizes and communicates the verified result.

## Precision decision

The expanded sources do add system-design value, particularly dependency, lifecycle/reset, resource flow, RNG consequence and gameplay-parameter reasoning. They are safe only under the adapter contract above. Any implementation of this corpus must assert:

- external pattern cannot set `existenceStatus` above `possible`;
- external pattern cannot directly create `missingGameRules`;
- numeric/formula examples are non-authoritative and excluded;
- player-outcome parameters remain gameplay; file/schema/runtime details remain implementation;
- only current-project Evidence/Fact/Rule/UI/relationship bases may promote a dimension through Phase 5.4.4.
