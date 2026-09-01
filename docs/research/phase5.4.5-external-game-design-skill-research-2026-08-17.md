# Phase 5.4.5 External Game Design Skill Distillation — Research Note

Date: 2026-08-17  
Mode: read-only research; no skill installation or runtime execution

## Authority boundary

This note distills abstract design-question patterns only. Every accepted entry has `contentAuthority: none` and may produce only a `possible scope` or `possible rule dimension`. It cannot establish that a mechanic exists in the current project, supply a rule answer, create `missingGameRules`, close a Gap, or bypass the Phase 5.4.4 `MechanicScope` gate. Project Evidence / Fact / Rule / UI structure / relationships must independently promote a candidate to `confirmed` or `strongly_implied` before rule reconstruction.

The numerical values and genre-specific recommendations in the sources are examples or opinions, not project facts. They are intentionally not copied into the corpus candidates below.

## Primary sources audited

### Game Development Orchestrator

- [`genre-templates.md`](https://github.com/lorenzopapa2/game-development-orchestrator/blob/main/references/genre-templates.md): genre core loops, candidate systems, balance emphasis, level-design emphasis, hybrid composition.
- [`balance-economy.md`](https://github.com/lorenzopapa2/game-development-orchestrator/blob/main/references/balance-economy.md): combat math, source/sink economy, probability, progression and difficulty validation.
- [`economy_and_progression.md`](https://github.com/lorenzopapa2/game-development-orchestrator/blob/main/references/data_models/economy_and_progression.md): formula families for damage, growth, economy, RNG and strategic balance.
- [`level-design.md`](https://github.com/lorenzopapa2/game-development-orchestrator/blob/main/references/level-design.md): level purpose, pacing arc, encounter composition, boss checks and spatial structure.
- [`implementation.md`](https://github.com/lorenzopapa2/game-development-orchestrator/blob/main/references/implementation.md): reviewed only for configuration schema and data/dependency portions; runtime architecture and engineering workflow were excluded.

### Claude-Code-Game-Studios

- [`map-systems/SKILL.md`](https://github.com/Donchitos/Claude-Code-Game-Studios/blob/main/.claude/skills/map-systems/SKILL.md): explicit-system extraction, implicit-system candidates, dependency mapping and design order.
- [`design-system/SKILL.md`](https://github.com/Donchitos/Claude-Code-Game-Studios/blob/main/.claude/skills/design-system/SKILL.md): player fantasy, core rules, states/transitions, constraints, formulas, dependencies and tuning knobs.
- [`design-review/SKILL.md`](https://github.com/Donchitos/Claude-Code-Game-Studios/blob/main/.claude/skills/design-review/SKILL.md): completeness, cross-system consistency and game-designer/systems-designer review lenses.
- [`game-designer.md`](https://github.com/Donchitos/Claude-Code-Game-Studios/blob/main/.claude/agents/game-designer.md): nested gameplay loops, player-facing rules, progression/economy, feedback loops, player experience and failure recovery.
- [`systems-designer.md`](https://github.com/Donchitos/Claude-Code-Game-Studios/blob/main/.claude/agents/systems-designer.md): formula contracts, interaction matrices, feedback loops, tuning parameters and gameplay impact.

## Accepted corpus candidates

All rows below are candidates, never instantiated project mechanics.

Accepted count: **28**.

| ID | Classification | Abstract pattern | Allowed inference |
|---|---|---|---|
| EXT-MSP-01 | `mechanic_scope_pattern` | Decompose a concept from explicitly named player actions, loop steps, MVP features and visible interfaces; inferred companion systems remain candidates until independently evidenced. | possible scope |
| EXT-MSP-02 | `mechanic_scope_pattern` | Model nested player loops separately: moment-to-moment action, session goal/reward cycle, and long-term return/progression loop. | possible scope |
| EXT-MSP-03 | `mechanic_scope_pattern` | For hybrid genres, treat the primary loop and secondary meta-structure as separate candidate scope sources; do not union every genre template item. | possible scope |
| EXT-MSP-04 | `mechanic_scope_pattern` | A level/section/room may have a dominant player-facing purpose such as teaching, testing, combining, rewarding, resting, culminating or routing. | possible scope |
| EXT-GRP-01 | `game_rule_pattern` | Reconstruct the normal player-use chain: entry/trigger → available action or choice → rule resolution → observable outcome. | possible rule dimension |
| EXT-GRP-02 | `game_rule_pattern` | If evidenced states exist, ask which player-visible states exist, which transitions are valid, and what causes each transition. | possible rule dimension |
| EXT-GRP-03 | `game_rule_pattern` | Ask both capabilities and limitations: what the player can do, cannot do, and under which conditions. | possible rule dimension |
| EXT-GRP-04 | `game_rule_pattern` | Separate ordinary rules from genuinely unusual player-facing edge outcomes; QA enumerability alone does not create a new design rule. | possible rule dimension |
| EXT-GRP-05 | `game_rule_pattern` | A confirmed failure loop may need failure trigger, player cost, recovery path and retained/reset state, calibrated to failure frequency. | possible rule dimension |
| EXT-GRP-06 | `game_rule_pattern` | A confirmed encounter may define threat, aid/enabler, rule modifier, objective and completion result as distinct dimensions. | possible rule dimension |
| EXT-SDP-01 | `system_dependency_pattern` | Map upstream inputs and downstream outputs, including the gameplay data exchanged and the system that owns each contract. | possible scope/rule dimension |
| EXT-SDP-02 | `system_dependency_pattern` | Distinguish hard dependencies required for the mechanic to function from soft dependencies that only enhance it. | possible scope dimension |
| EXT-SDP-03 | `system_dependency_pattern` | Check dependency claims bidirectionally and surface inconsistent expectations instead of silently inventing a bridge rule. | possible rule dimension |
| EXT-SDP-04 | `system_dependency_pattern` | Config references and IDs can suggest possible relations among content objects, loot/rewards, levels, unlocks and progression, but schema fields never prove those mechanics exist. | possible scope |
| EXT-PRG-01 | `progression_pattern` | A confirmed progression system may require acquisition input, growth transformation, milestone/unlock effect, pacing over phases and reset/persistence behavior. | possible rule dimension |
| EXT-PRG-02 | `progression_pattern` | Evaluate whether an unlock changes player strategy/capability or only changes magnitude; the distinction is a design dimension, not an assumed answer. | possible rule dimension |
| EXT-PRG-03 | `progression_pattern` | Distinguish within-session growth, between-session/meta growth and reset/prestige loops when evidence supports those lifecycles. | possible scope |
| EXT-RND-01 | `randomization_pattern` | A confirmed random selection/drop system may define candidate eligibility, weights/probabilities, duplicate handling, failure-streak protection and reset scope. | possible rule dimension |
| EXT-RND-02 | `randomization_pattern` | Random content generation may define content grammar, distribution constraints, guaranteed placements and invalid combinations. | possible rule dimension |
| EXT-RND-03 | `randomization_pattern` | Probability must be evaluated together with expected player cost/time and the consequence of duplicates or misses. | possible rule dimension |
| EXT-ECO-01 | `economy_pattern` | For each evidenced resource, map sources, sinks, converters, storage/retention and the player action enabled or constrained by the flow. | possible rule dimension |
| EXT-ECO-02 | `economy_pattern` | Model affordability and surplus/deficit across gameplay phases, without importing external target values. | possible rule dimension |
| EXT-ECO-03 | `economy_pattern` | Connect reward amount, upgrade/purchase cost and time-to-next-meaningful-goal as one economy/progression lever. | possible rule dimension |
| EXT-BAL-01 | `balance_pattern` | A gameplay formula candidate must specify inputs, output, bounds/extreme behavior and player-facing impact; values remain unresolved until project evidence or planner input exists. | possible rule dimension |
| EXT-BAL-02 | `balance_pattern` | Identify tuning levers together with safe ranges only after the mechanic exists; evaluate how each lever changes strategy, pacing, outcome or resource pressure. | possible rule dimension |
| EXT-BAL-03 | `balance_pattern` | Check early/mid/late outputs, difficulty shape, recovery possibility and dominant-strategy risk rather than treating more formulas as deeper design. | possible rule dimension |
| EXT-BAL-04 | `balance_pattern` | Use interaction matrices only when the project already supports multiple interacting types/elements/statuses; matrix completeness cannot establish their existence. | possible rule dimension |
| EXT-BAL-05 | `balance_pattern` | Treat positive growth loops and stabilizing/counter loops as linked design levers and inspect runaway or dead-end behavior. | possible rule dimension |

## Excluded classifications

These patterns were audited but must not enter `ExternalGameDesignCorpus`.

| ID | Classification | Pattern | Exclusion reason |
|---|---|---|---|
| EXT-IMP-01 | `implementation_only` | Per-frame/per-tick update order, event bus, observer, component/entity and command-pattern selection. | Changes architecture, not player rules by itself. |
| EXT-IMP-02 | `implementation_only` | Hot reload, debug commands, logging, visualizers, test scenes, asset loading and pooling. | Production/tooling workflow only. |
| EXT-IMP-03 | `implementation_only` | Internal subsystem failure recovery, cache/state cleanup, determinism, rollback and save compatibility engineering. | Retain only in the implementation layer unless independent evidence establishes a player-facing rule. |
| EXT-IMP-04 | `implementation_only` | File format, schema type, internal ID, serialization, source-code ownership and update timing. | Configuration plumbing; only a field's gameplay effect may remain a gameplay parameter. |
| EXT-REJ-01 | `reject` | Instantiate every “key system” listed for a detected genre. | Directly violates the MechanicScope gate; genre similarity is not existence evidence. |
| EXT-REJ-02 | `reject` | Import benchmark values, recommended percentages, target durations, formula constants or rarity ratios as project defaults. | External examples have no project authority. |
| EXT-REJ-03 | `reject` | Treat all implicit/hidden systems from concept decomposition as confirmed. | They are exploration candidates only. |
| EXT-REJ-04 | `reject` | Require every GDD template section or every edge case to become a Planner Review decision. | Documentation/QA completeness must not set planner granularity. |
| EXT-REJ-05 | `reject` | Use “programmer can implement without questions” as sufficient evidence that a question is game design. | Implementation precision and planner salience are different gates. |
| EXT-REJ-06 | `reject` | Adopt source claims framed as universal rules (“every economy”, fixed genre norms, mandatory formula families). | Overgeneralized authority; applicability must be independently proven. |

## Adaptation audit

### Source-to-category disposition

| Source area | Useful categories | Main quarantine |
|---|---|---|
| genre templates | mechanic scope, progression, randomization, economy, balance | Genre lists and benchmarks cannot instantiate scope. |
| balance/economy | progression, randomization, economy, balance | Numeric recommendations and formula choices cannot become answers. |
| economy/progression models | progression, randomization, economy, balance | “Standard/proven” language is not project authority. |
| level design | mechanic scope, game rule, balance | Level-purpose and encounter checklists apply only after level/encounter evidence. |
| implementation config/data | system dependency, balance parameter structure | Runtime architecture, file schemas and update timing are implementation-only. |
| map-systems | mechanic scope, system dependency | “Implicit systems” stay possible; no automatic existence promotion. |
| design-system | game rule, system dependency, balance | Fixed GDD section template and edge-case enumeration do not create decisions. |
| design-review | game rule, system dependency, balance | Reviewer routing and QA completeness are workflow metadata. |
| game-designer lens | mechanic scope, game rule, progression, economy, balance | Theory frameworks are evaluation lenses, not project facts. |
| systems-designer lens | system dependency, progression, randomization, economy, balance | Formula/matrix completeness only applies to already-supported mechanics. |

### Required adapter contract

For every accepted external candidate:

1. Emit only `possible` scope or a non-instantiated possible rule dimension.
2. Attach external source provenance and `contentAuthority: none`.
3. Run Phase 5.4.4 `MechanicScope` using current-project Evidence / Fact / Rule / UI / relationship bases.
4. If the result is `possible`, `unsupported` or `contradicted`, keep it outside `missingGameRules` and Planner Review.
5. Only `confirmed` or `strongly_implied` scope may expose a corresponding rule dimension; the external source still cannot answer it.
6. Route direct player-outcome values to `gameplayParameters`; route file/schema/runtime details to `implementationDetails`.

## Audit conclusion

The two repositories contain useful vocabularies for discovering candidate gameplay scope, rule dimensions, dependencies, progression, randomization, economy and balance. Their strongest transferable contribution is the shape of questions and relationships, not any mechanic inventory or answer. The safe adapter therefore preserves their breadth as exploration hints while enforcing a hard two-step boundary:

`external pattern → possible candidate → MechanicScope Gate → confirmed/strongly_implied only → missingGameRules`

No external pattern may skip the middle gate, and no external numeric or genre convention may be treated as current-project evidence.
