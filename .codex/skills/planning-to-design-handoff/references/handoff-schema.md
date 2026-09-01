# Design Handoff Schema

Required top-level fields:

- `status`: `schema-ready` or `generated`.
- `targets`: requested systems such as `feishu-whiteboard` or `figma`.
- `nodes`: stable scene/page/component IDs, labels, types, hierarchy, and optional layout hints.
- `flowEdges`: stable edge ID, source, target, event ID, trigger, guard, response, and transition.
- `designTokens`: observed or explicitly defaulted colors, typography, spacing, radii, and effects.
- `componentStates`: component ID plus default/hover/pressed/selected/disabled/loading/error/success states when supported by evidence.
- `generatedArtifacts`: external type, ID, URL, and creation timestamp; empty until a connector succeeds.
- `diagnostics`: missing targets, unresolved references, unsupported transitions, and unknown values.

Before external creation, verify every edge source/target exists and every token reference resolves.
