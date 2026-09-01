# GVE16 production-depth addendum (2026-08-11)

## Purpose

This note distills the information roles and writing logic from the newly supplied vehicle, weapon, monster, and level examples. It is a reusable question set for reconstructing planning documents. It is not evidence that the current job has the same fields, values, table names, slot counts, or rules.

## Evidence boundary

- Sample facts answer “what should we investigate?”
- Current screenshots answer only visible state, layout, labels, and observable transitions.
- Current reference documents/configuration tables may prove hidden rules, formulas, field names, defaults, and reset behavior.
- Confirmed planner decisions may be written as conclusions.
- Multiple reasonable interpretations with insufficient evidence must become a decision card.
- Never copy sample-only identifiers such as official table names or exact numeric limits into another project.

## Reverse-engineered organization logic

1. Start from the entity or gameplay phase, not a universal template.
2. Give a short content inventory before rules when multiple distinguishable items exist.
3. Describe behavior in player/system order: trigger, prerequisite, processing, result, feedback, exception.
4. Put business-name-to-field mappings immediately after the behavior they implement.
5. Use a compact configuration table only for values, units, ranges, weights, and lookup relationships.
6. Close the mechanism with irreversible choices, reset scope, re-entry, and settlement behavior.
7. Merge headings whose content is too small; retain headings when they separate genuinely different responsibilities.
8. Use bullets for parallel rules and numbered steps for strict execution order. Avoid converting table cells into stiff prose.

## Two complementary sample-depth patterns

### Full-system specification pattern

The broader sample begins with a numbered gameplay introduction that already closes the player loop: challenge and failure, wave victory, placement/merge, preparation refresh, inventory expansion, in-level experience and choices, external progression, unlocks, sweep, stamina, and endless mode. Later chapters expand each promise into implementable rules.

Its important techniques are:

- The overview is an index of the actual design, not generic promotional prose. Every major overview claim must map to a later chapter or be explicitly scoped out.
- Objects are separated before behavior: monster, hero, projectile, player avatar, currencies, materials, and special objects each receive only their applicable properties and rules.
- The same object is split by lifecycle when needed, such as external level versus in-level merge level.
- Concrete examples disambiguate formulas and state changes, such as proportional current/max HP changes.
- Cancelled, deferred, and phase-specific features remain traceable as historical status, but are excluded from current runtime flow and active configuration.
- Large mechanisms cover normal flow, illegal operations, rollback, save timing, re-entry, interruption, settlement, and reset rather than stopping at the happy path.

### Focused gameplay-delivery pattern

The focused sample begins with separate UX, planning-board, and competitor-reference carriers, then organizes gameplay by vehicle, weapon, monster, combat, and level. It keeps configuration mappings beside the behavior and embeds images at the exact rule they prove.

Its important techniques are:

- Visible UI state, structural flow, gameplay rule, and configuration data use different carriers but share one semantic model.
- Attribute names are not enough: the document explains meaning, unit, ownership, calculation role, trigger timing, and interaction with other attributes when supported.
- A mechanism normally closes with irreversible choices, unlock/reset scope, or persistence rules.
- Cross-references such as “see combat rules” prevent duplicate formulas while retaining navigability.
- Images are placed locally beside slot display, configuration structure, random selection, statistics, or settlement rather than collected as a decorative gallery.

## Cross-sample granularity test

A current-project chapter reaches comparable granularity only when all applicable checks pass:

1. Its overview claim has a traceable detailed landing point.
2. Its objects, states, and local/external lifecycles are distinguished where the evidence requires it.
3. Its behavior reaches trigger, input/read, judgment, processing order, result/write-back, feedback, failure, and reset.
4. Its parameters include supported meaning, unit, source, calculation role, and nearby mapping; exact identifiers are used only with authoritative evidence.
5. Its formulas state operands, order, units/scale, caps or rounding when known, and use an example when ambiguity remains.
6. Its complex sequence, judgment, loop, or state transition has the appropriate player, system, algorithm, or state diagram.
7. Its screenshots or local diagrams are adjacent to the rule they prove.
8. Its cancelled/deferred/history items cannot enter active rules, completion percentage, or export gates.
9. Its prose uses concrete actors and conditional verbs; it avoids slogans, generic benefit claims, and table-like sentence dumping.

## Content coverage comes before depth

Depth review cannot discover a system that was omitted from the directory. Before writing or grading chapters, build a content inventory from every evidence source and reconcile it against the document model.

### Gameplay and mode content

- Player objective, basic operation, core loop, preparation/combat/settlement phases, win/fail, replay or continuation.
- Main stages, endless or special modes, external challenge/unlock, sweep, first-clear, progress rewards, stamina or entry costs when present.
- Scene/map composition, wave progression, timing, movement, stopping, spawning, NPC events, and level-specific modifiers.

### Entity and object content

- Player/avatar/carrier, weapon/skill/projectile, monster/enemy/NPC, inventory/grid/slot, reward/item/currency, Buff/affix, and special/privileged objects when present.
- For each object: identity/type catalog, ownership, attributes, state, behavior, relationships, unlock/growth, visibility, creation/destruction, and lifecycle.

### Rule and data content

- Trigger and prerequisites, eligibility, sequence, state transition, branch, loop, interruption, rollback, success/failure, settlement, reset, and persistence.
- Configuration source, nearby business-to-field mapping, units, ranges, arrays/JSON, weights/probabilities, formulas, caps, rounding, sorting, aggregation, and write-back when supported.
- Runtime counters and temporary results, concurrency/order, empty/missing/insufficient/out-of-range handling, and data recovery.

### Interaction and presentation content

- Entry, operation, enabled/disabled state, empty/filled state, click/drag/confirm/cancel, popup/tips/toast, pause/resume, animation/audio/effect, dynamic refresh, and screen transitions when evidenced.
- UX design, planning board, competitor reference, local evidence image, gameplay structural diagram, state/system/algorithm flowchart, and configuration illustration each retain their distinct role.

### Production and scope content

- Current implementation, unimplemented requirement, cancelled history, deferred phase, dependency, source provenance, decision status, acceptance condition, and downstream owner when present.
- Program, numerical design, UI/UX, animation, audio, QA, configuration, and publishing needs must be discoverable without forcing empty sections for roles that do not apply.

The inventory must record `evidence source → identified content → applicable carrier → current coverage → gap/action`. A document fails content coverage if an evidenced item has no carrier, even when every existing chapter is individually detailed.

## Applicable production questions

### Vehicle or carrier

Check base attributes; upgrade entry/cost/result; per-level mapping; slot count and roles; empty/filled states; capacity and replacement rules; visible slot information; click behavior; privileged variant unlock/effects; irreversible choices; and reset scope.

### Weapon, skill, or affix

Check type inventory; base damage conversion; elemental or subtype damage; trigger interval; duration; direct/indirect targets; attenuation; cooldown; targeting range; shape/range calculation; external unlock and growth; affix group/prerequisite/max level/weight/name/description parameters; affected skill/effect; pool eligibility and removal.

### Monster or NPC

Check spawn timing, ordered groups, intervals, spawn-point types and offsets; movement; attack-distance entry/exit; attack animation/projectile; hit/death; health/attack/speed/range/attack interval; reduction and elemental modifiers; dodge accumulation/reset; block consumption; immunity; category; and projectile reference.

The monster attribute ledger must enumerate supported fields rather than saying “基础属性等”. In particular, check health and attack with current-level/current-wave multipliers, movement speed, attack distance, attack interval in milliseconds, final reduction, elemental reduction, dodge basis points and guaranteed-hit reset, block consumption, abnormal-effect immunity, monster category, and projectile ID. Apply the same owner-specific ledger discipline to vehicles and weapons; do not merge their fields into a generic parameter catalog.

An “attribute-complete” gate must include the whole implementation surface actually present in the system, not a short combat-stat sample. For the current reference domain this means: vehicle base stats, upgrade item/cost, weapon slots and privilege effects; weapon type, unlock and out-of-run growth; affix ownership, prerequisites, max level, weight, display copy, unlock level, target skill and effect parameters; monster base stats and wave multipliers, actions and projectile; spawn-group interval, point type, relative XY offset, group IDs and counts. These are reusable knowledge reserves, not mandatory headings or fields for unrelated projects.

### Attribute, diagram, and screenshot carriers

Core-entity attributes are part of the mechanism specification, not an audit appendix. Vehicle, weapon, monster/BOSS, projectile, resource, and reward fields must stay with their owner and state how the field participates in judgment or calculation, its unit, boundary, source, and reset/persistence behavior when known. Missing values are decisions; they are not reasons to fill the body with evidence disclaimers.

Flowcharts and screenshots are local explanatory carriers. Put an ordered/branching diagram between the prose that introduces its trigger and the prose that explains its outcomes and edge cases. Put a screenshot immediately after the rule whose visible state it demonstrates, with a short business-facing caption. A separate diagram gallery, a page of thumbnail evidence, or a planning board squeezed until unreadable does not match the sample documents'图文结合 logic.

Headings are semantic and adaptive. Do not repeat fixed headings such as “规则与边界” across mechanisms. Short rule clusters merge into the nearest meaningful part; substantial clusters receive domain-specific names. Audit language—including what a screenshot cannot prove, coverage verdicts, source confidence, and improvement paths—stays in review metadata and decision cards rather than the published design body.

When wave or spawn structure is present, generate a local wave configuration table automatically. Choose only evidenced columns from level, wave, ordered group, group interval, spawn-point category, xy offset, monster/BOSS ID and count, health/attack multiplier, carrier stop point, reward, and transition condition. The table carries lookup data; adjacent prose still explains sequence, same-type spawn consistency, empty-point behavior, and boundary rules.

### Level

Check scene composition and reuse loop; wave order, distance/time derivation, spawn groups/points, carrier points and stopping; speed changes and recovery; in-level level/experience reset; three-choice and slot-machine eligibility, two-stage weighting, no-replacement, empty handling, temporary result, confirmation, reroll cost and reset; buffs; damage statistics and formulas; time limit; speed toggle persistence; success/failure settlement; external unlock, challenge, first-clear, progress, and sweep.

## Diagram triggers and diagram families

- Level-flow diagram: ordered stages with branch and merge, optional events, and return to normal combat.
- Wave/movement diagram: scene reuse, wave order, carrier point, spawn-point spatial relation, stop/resume.
- Random-selection diagram: pool eligibility, staged weighting, slot fill, temporary result, confirmation/reroll, pool removal/reset.
- State diagram: empty/filled/locked/unlocked/maxed, pause/resume, success/failure/settlement.

A diagram complements rather than replaces the corresponding rule text, parameter mapping, and lifecycle statement.

## Acceptance consequence

Granularity cannot pass based on chapter count, text length, or the presence of generic headings. It passes only when every applicable, evidence-supported production question has a traceable carrier and every material sequence/branch/loop has an adequate diagram or a documented exception.

Length is only a missing-detail warning: roughly 3,000–8,000 Chinese characters for a small feature, 8,000–20,000 for a medium core system, 20,000–50,000 for a complete core gameplay, and 50,000–150,000 or more for a multi-system game design. Never pad to reach these bands. Never shorten a rule closure to fit one response; continue by chapter when necessary.

## Reserve knowledge modules

The following modules remain available as domain-specific question libraries. They are not default chapters and are activated only when the current evidence identifies the corresponding system.

- Weapon/projectile/combat: targeting, range, cooldown, projectile lifecycle, hit order, damage modifiers, death, drops, and combat feedback.
- Buff/special effect: source, target, add/effect/remove conditions, duration, tick, stacking, refresh, dispel, source death, formula, and presentation.
- Inventory/grid/spatial placement: coordinate model, occupied cells, shape/rotation, overlap, replacement, merge, connectivity, illegal placement rollback, save timing, and feedback.
- Sweep/external progression: unlock, stamina/cost, count limits, first-clear distinction, reward aggregation, failure handling, and progress persistence.
- Random/refresh/draw: eligible pool, filtering, weights/probability units, order, replacement, duplicate/empty handling, caps, pity, reroll, temporary result, write-back, and reset.
- Waves/spawning: order, entry/end conditions, spawn points, coordinates, delays, entity IDs, multipliers, carry-over survivors, stop/resume, and next-wave transition.
- State and runtime data: initialization, modification timing, interruption, priority, concurrency, rollback, reset, and persistence.

Activation has three outcomes: `applicable` (must be covered), `decision_required` (create a decision card), or `not_applicable` (record the evidence-based reason). A reserve module must never be copied into the document merely to increase length.

## Reserve heading responsibility library

The long-form system-document headings are retained as content responsibilities, not a fixed outline:

- Basic explanation and system objects
- Player operation
- Functional rules and system judgments
- Algorithm inputs, data sources, filtering, calculation, and write-back
- State and lifecycle
- Configuration and nearby field mappings
- UI, animation, audio, and feedback
- Special rules, failures, and boundaries
- Reset and persistence
- Planner decisions

Select headings only when they separate substantial responsibilities. Merge short neighboring responsibilities into one natural section; split a complex mechanism only when each child section contains independently useful implementation information. The final hierarchy must follow the actual gameplay rather than this library's order.

## Cross-project runtime contract

The distilled method is implementation policy, not a GVE16 outline:

- Use a 单一事实主载体. Published gameplay prose owns the fact; secondary review fields use `carrierRefs` unless they add a distinct runtime responsibility.
- Resolve every reserve module as `applicable / decision_required / not_applicable`. A `sample_reserve` entry can prompt investigation but cannot become a current-project fact.
- Write 对象归属的属性正文 before lookup data. Owner, behavior, calculation role, timing, boundary, and lifecycle determine the prose; compact tables handle values and ranges.
- 禁止固定标题 and 禁止审核报告口吻. Headings follow real information clusters, while audit verdicts and repair instructions remain outside delivery copy.
- Keep 局部截图与流程图就近放置 and bind them to the exact rule or mechanism they explain.
- Validate portability through 跨项目盲测, then perform 分阶段验收 with user-approved cases and 每个用例使用唯一匹配截图.
