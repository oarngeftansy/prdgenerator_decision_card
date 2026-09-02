# Gameplay Understanding Skill v1.2

## Role

Transform evidence observations from screenshots, ordered image sequences, video probes, reference documents and reviewed temporal evidence into a gameplay understanding model. This skill explains what gameplay systems and mechanisms exist and how they relate. It does not make implementation decisions that belong to Execution Planning.

## Output authority

The output is `GameplayUnderstandingModel` and is the sole semantic source consumed by Interaction Model and P1/P2/P3 projections.

Use a dynamic hierarchy:

`System -> Subsystem -> Mechanism -> RuleGroup`

The hierarchy is discovered from the current material. Never force a fixed chapter count, a fixed list of systems, or nouns copied from a Golden Sample.

## Evidence and inference

Evidence anchors observations. Evidence insufficiency does not prevent reconstructing a plausible mechanism when multiple observations imply hidden gameplay logic. Reconstructed content must carry provenance separately from user-visible wording.

- confirmed: directly supported and reviewed.
- inferred: reconstructed from behavior, sequence, state changes or cross-frame consistency.
- conflict: explicit sources cannot be reconciled into one understanding.

Do not insert labels such as “可能”, “推测”, “待确认” into the semantic description. Provenance is metadata.

## Mechanism reconstruction

Do not stop at visible presentation. For each discovered mechanism, reason about the dimensions that are actually necessary to explain player experience and system behavior, including when relevant:

- actors/entities and resources;
- trigger and preconditions;
- state and state transitions;
- lifecycle and reset boundaries;
- temporal order, rounds, waves or scheduling;
- selection/randomness and eligibility;
- spatial/targeting relationships;
- resource/economy transformations;
- success/failure/settlement;
- dependencies between mechanisms;
- observable feedback that reveals hidden state.

Do not inject dimensions that are irrelevant to the current mechanic.

## Interaction boundary

Understanding may identify interaction intents and state transitions, but it must not decide final UI layout or implementation detail. The next stage, Interaction Model, organizes reviewed interaction observations before execution planning.

## Golden Samples

Golden Samples provide mechanism-dimension priors, execution-depth expectations and quality benchmarks. They never provide the current project's directory, mechanic inventory, object names, parameter schema or required screen list.

## Prohibitions

- no fixed 6/7/8 chapter cap;
- no skill/weapon/monster/candidate-pool assumptions unless the evidence actually describes them;
- no implementation field names invented from thin evidence;
- no Final document prose;
- no P4/P5/P6/P7 work.