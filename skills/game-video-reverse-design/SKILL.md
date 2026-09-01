---
name: game-video-reverse-design
description: Analyze game recordings, trial videos, or gameplay demos to reverse-engineer gameplay rules, interaction logic, level mechanics, and system structures. Build a structured PRD for prototype development by reconstructing player actions, system responses, state machines, and causal chains from observable video evidence. Use when the user wants to "拆解游戏玩法", "复刻游戏原型", "逆向游戏机制", "分析游戏视频", "游戏PRD", "玩法状态机", "关卡机制拆解", or "game reverse design". This skill focuses on gameplay logic and rules, not just visual reconstruction.
---

# Game Video Reverse Design & Interactive Prototype Reconstruction

## Purpose

Analyze game recordings, trial videos, or gameplay demonstrations to identify player operations, UI changes, system feedback, and level state transitions. Reverse-engineer gameplay rules, interaction logic, level mechanics, and system structures.

Convert observable video content into a structured PRD usable for gameplay replication, prototype development, and implementation.

This skill is NOT about summarizing video content. It is about:

- Reconstructing causal relationships between player actions and system responses.
- Rebuilding gameplay rules and interaction state machines.
- Decomposing level elements and mechanic trigger logic.
- Outputting actionable gameplay prototype requirements.
- Clearly labeling confirmed rules, inferred rules, and unverified rules.

## When to Use

Use this skill when the user requests:

- Analyze gameplay from a video.
- Decompose game mechanics from a recording.
- Replicate a game's gameplay prototype.
- Output a PRD based on a trial/demo video.
- Reconstruct click, drag, swipe, or other interaction logic.
- Analyze level elements, obstacles, and item rules.
- Analyze page transitions and system flows in a game.
- Derive gameplay state machines from video.
- Output implementation requirements for design, art, client, and server teams.
- Perform video-level reverse engineering on competitor games.

## Input Requirements

Input can include:

1. Full game recordings.
2. Single-level videos.
3. Tutorial / onboarding videos.
4. Core gameplay demonstrations.
5. System function operation videos.
6. Page transition recordings.
7. Multiple videos showing different operation outcomes.
8. User-supplied gameplay background, genre, or analysis targets.

Recommended user-provided context:

- Original video files.
- Game name and version.
- Target platform.
- Modules to focus on.
- Whether a full PRD is needed.
- Whether flowcharts, state machines, or prototype descriptions are needed.

When video information is incomplete, still perform maximum analysis based on available frames. Do not halt the task.

## Core Analysis Principles

### 1. Evidence-Based

All rule judgments should come from observable evidence:

- What operation did the player perform?
- What was the UI state before the operation?
- What changed after the operation?
- Did any values change?
- Did elements move, disappear, spawn, or unlock?
- Were there animations, sounds, vibrations, or prompts?
- Did the system allow or reject the operation?
- Does the same operation produce different results in different states?

Do NOT assume common genre rules as the actual rules in the video.

### 2. Distinguish Fact, Inference, and Unknown

All conclusions fall into three categories:

- **Confirmed**: Clear video evidence supports it. Can be written directly into PRD.
- **High-confidence inference**: Not fully shown but reasonably deducible from repeated behavior.
- **Unverified**: Missing key evidence; cannot confirm specific rules or values.

Output must explicitly label these. Do not package inference as confirmed fact.

### 3. Prioritize Causal Chains

Identify:

> Player action → System judgment → State change → Feedback → Subsequent available actions

Example:

> Player taps a blocked element
> → System judges element is currently non-interactive
> → Element does not move
> → Plays shake animation
> → Shows "blocked" tooltip
> → Player remains in current level state

### 4. Prioritize State, Not Just Visuals

Do not just write: "Player taps button and a popup appears."

Further decompose:

- Under what state is the button visible?
- What conditions make it tappable?
- Does the original page persist after tapping?
- Does the popup block other operations?
- Can the popup be dismissed by tapping outside?
- What state is returned to after closing?
- Do popup operations affect original page data?
- Is there a secondary confirmation?

### 5. Output Must Be Reproducible

Each rule should be:

- Configurable by a designer.
- Drawable as a flow by an interaction designer.
- Implementable as state changes by a client developer.
- Sufficient for server-side data requirement judgment.
- Testable by QA.

## Standard Analysis Pipeline

### Phase 1: Video Segmentation

Split video by function and gameplay stage. Common segments:

1. Launch & login
2. Home screen
3. Level entry
4. Pre-level popup
5. Core gameplay process
6. Item usage
7. Victory settlement
8. Defeat settlement
9. Reward collection
10. System unlock
11. Return to home
12. Event or monetization pages

For each segment, record: start time, end time, current page, main player actions, main system feedback, involved mechanics.

### Phase 2: Operation Event Extraction

Extract player input events per segment. Include: tap, rapid tap, double-tap, long-press, drag, swipe, pinch, rotate, release, wait, back, close, confirm, cancel, use item, watch ad, consume resource, restart.

Record format:

| Timestamp | Current State | Player Action | Target Object | System Response | Resulting State |
|---|---|---|---|---|---|

### Phase 3: UI State Identification

Identify all logically meaningful states on the page, e.g.:

Default, tappable, non-tappable, selected, locked, unlocked, cooldown, active, completed, claimed, insufficient-quantity, ad-available, ad-unavailable, new-feature-hint, red-dot, loading, network-error.

For each state, describe: entry condition, visual appearance, available operations, exit condition, next state transition.

### Phase 4: Core Loop Extraction

Identify the minimal core gameplay loop:

> Player goal → Player action → System rule judgment → Board/scene change → Player feedback → Goal progress change → Next action or level end

Specify: player core goal, main decisions, main operations, system constraints, positive feedback sources, failure pressure sources, single-round end conditions, out-of-level progression.

### Phase 5: Level Mechanics Decomposition

Document each level element individually. For each element, analyze:

- **Basic info**: name, type, initial state, spawn position, direct operability.
- **Interaction rules**: how to operate, prerequisites, continuous operation, undo, influence from other elements.
- **State changes**: what states exist, how to enter each, reversibility, visual changes.
- **Trigger logic**: tap trigger, match trigger, collect trigger, turn trigger, time trigger, combo trigger, quantity trigger, adjacency trigger, overlap trigger, random trigger.
- **Results**: element disappears, spawns, moves, opens area, unlocks content, creates block, changes counter, provides reward, triggers animation, affects other elements.

### Phase 6: Interaction Logic Reconstruction

Write each key interaction as a complete chain. Template:

**Interaction name**: e.g., "Tap selectable mahjong tile"

**Prerequisites**: current state conditions.

**Player action**: what the player does.

**System judgment**: ordered checks the system performs.

**Success result**: what happens on success.

**Failure result**: what happens on failure.

**Feedback**: tap feedback, movement animation, sound, vibration, value changes, highlights, tooltip text.

**Resulting state**: player can continue, enter match animation, enter item selection, enter victory, enter defeat.

### Phase 7: State Machine Reconstruction

Rebuild at minimum:

- **Level state machine**: not-started, preparing, in-progress, input-locked, animation-playing, paused, about-to-win, victory, about-to-lose, defeat, revive, restart, exit-level.
- **Element state machine**: locked → unlock condition met → unlock animation → interactive → operated → eliminated.
- **Page state machine**: home → tap level entry → pre-level popup → tap start → level page → victory settlement → reward page → return home.

### Phase 8: Values and Configuration Identification

Extract observable or inferable values from video: target count, steps, time, resource quantities, item counts, reward amounts, combo thresholds, unlock conditions, slot capacity, failure thresholds, ad count, stamina cost, currency cost, level number, difficulty indicator.

Label all values: fixed, configurable, inferred, unconfirmable-from-video.

### Phase 9: Edge Case Completion

Videos typically only show the happy path. Supplement necessary edge cases based on known rules: rapid consecutive taps, operating during animation, insufficient resources, full slots, expired targets, duplicate claims, network interruption, exit and re-enter, mid-level quit, force-close app, ad playback failure, reward delivery failure, multiple simultaneous triggers, victory and defeat conditions met simultaneously, UI elements obscured by popups, input latency on low-end devices.

Edge logic must be labeled as "suggested implementation", not original game rules.

## Output Structure

The final PRD should include:

1. **Project overview**: game genre, analysis scope, replication target, core gameplay summary, confidence level.
2. **Core gameplay loop**: player goal, core operations, core rules, round loop, win/loss conditions, core satisfaction, core pressure.
3. **Pages & system structure**: page inventory, hierarchy, entry points, exit points, transitions, popup relationships.
4. **Level structure**: level goals, initial layout, level elements, obstacles, items, difficulty sources, end conditions, level config.
5. **Mechanism details**: one chapter per mechanism including purpose, presentation, trigger conditions, operation flow, state changes, feedback, value config, edge cases.
6. **Interaction requirements**: per-interaction object, operation method, prerequisites, success result, failure result, animation feedback, sound feedback, input lock, resulting state.
7. **State machines**: level, page, core element, item, settlement.
8. **UI & feedback requirements**: page layout, HUD info, button states, prompt methods, animation layers, sound nodes, vibration nodes, value change presentation, red dots and guidance.
9. **Configuration requirements**: use config table format.
10. **Tracking/analytics requirements**: page exposure, button clicks, level start/end, victory, defeat, quit, item use, ad trigger, resource consumption, mechanic trigger, key state changes.
11. **Edge cases & boundary logic**: distinguish video-confirmed, rule-derived, suggested.
12. **Unverified checklist**: rules video cannot confirm (random algorithms, hidden probabilities, dynamic difficulty, server logic, unseen failure branches, unseen monetization, unseen re-engagement).

## Output Format Rules

### Conclusion First, Then Evidence

State the rule conclusion first, then attach video evidence or timestamp.

### Use Precise Rule Language

Recommended: "When X, the system Y...", "Only under condition Z can the player...", "If X then Y...", "If not X then...", "After each trigger...", "When count reaches N...", "During animation, forbid...", "On completion, enter..."

Use markers: 【Confirmed】, 【High-confidence inference】, 【Unverified】, 【Suggested implementation】

### Avoid Visual-Only Descriptions

Wrong: "There is a glowing button on the page."

Correct: "When rewards are claimable, the claim button transitions from gray/disabled to highlighted/glowing. On tap, play reward fly-in animation, button switches to 'claimed' state, and repeat taps are blocked."

### Rules Must Include Input and Output

Wrong: "Use item to undo."

Correct: "When player taps the undo item, the system restores the board state from before the most recent valid operation, reverting the position changes caused by that operation. The consumed undo item is not refunded. If no undoable operation exists, the button is disabled."

## Confidence Assessment

- **High**: Same behavior appears repeatedly in video; clear action-feedback relationship; values directly observable; no obvious alternative explanations.
- **Medium**: Appears once; behavior result clear; some conditions not shown; reasonably inferable from similar mechanics.
- **Low**: Heavy occlusion; missing operation process; only result shown; multiple reasonable explanations; rules depend on hidden values or random logic.

Final document should state overall confidence and list low-confidence modules.

## What NOT to Infer from Video

Video alone typically cannot confirm: server data structures, true random algorithms, probability weights, dynamic difficulty formulas, user segmentation rules, paying user differentiation, ad waterfall logic, precise economic models, untriggered hidden mechanics, level generation algorithms, anti-cheat logic, save sync mechanisms, network reconnect mechanisms.

These can be given as replication suggestions but must be labeled as proposals, not original game facts.

## Prototype Replication Levels

- **L1: Visual flow replication** — Only replicate pages, buttons, popups, and basic transitions. No full gameplay.
- **L2: Interaction prototype** — Replicate core taps, drags, state changes, and feedback. Complete main operation flow.
- **L3: Gameplay prototype** — Implement core gameplay loop, win/loss conditions, level mechanics, and basic value config.
- **L4: High-fidelity functional replication** — Complete gameplay, level config, items, settlement, edge logic, and system progression.

After analysis, state which level the current video supports.

## Execution Requirements

- Do NOT treat video summarization as gameplay decomposition.
- Do NOT only describe visuals; explain rules.
- Do NOT only describe rules; explain trigger conditions.
- Do NOT only describe success flows; supplement failure and edge flows.
- Do NOT write inference as confirmed fact.
- Do NOT omit operation restrictions and input locks.
- Do NOT omit animation, sound, prompts, and state feedback.
- Do NOT omit page transitions and return logic.
- Output must support prototype replication.
- Honestly label unconfirmable content.