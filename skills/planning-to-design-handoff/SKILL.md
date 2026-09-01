---
name: planning-to-design-handoff
description: Convert a validated GVE16 planning model into schema-ready UE flows, Feishu whiteboard nodes and connectors, or Figma-oriented pages, components, variants, tokens, and prototype links. Use after planning validation when preparing visual design handoff or flow reconstruction.
---

# Planning to Design Handoff

Transform the validated model according to [references/handoff-schema.md](references/handoff-schema.md). This absorbs the useful mapping rules from `prd-to-figma` without pretending its instruction-only package is a runnable plugin.

## Workflow

1. Validate the GVE16 model and all referenced IDs.
2. Convert scenes/pages to nodes or frames, components to component records, events to connectors/prototype links, and states to variants.
3. Generate design tokens only from observed values or explicitly labeled defaults.
4. Produce `schema-ready` handoff data and a diagnostic list for unresolved targets, tokens, or connectors.
5. If a Feishu/Figma connector is callable, write the artifact and record its external ID/URL.
6. Without a successful connector response,不得声称已经生成飞书画板或 Figma 文件。

## Output Boundary

`schema-ready` means the data is validated and ready for a connector. `generated` is allowed only after external creation succeeds and `generatedArtifacts` contains verifiable identifiers.
