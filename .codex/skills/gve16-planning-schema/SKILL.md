---
name: gve16-planning-schema
description: Build and validate the GVE16 intermediate planning model for gameplay and interaction videos. Use when converting timestamped evidence into deterministic scenes, events, components, rules, flows, uncertainty labels, acceptance criteria, and design-handoff data before rendering a planning document.
---

# GVE16 Planning Schema

Use `backend.planning_model.build_planning_model` as the canonical data contract between video understanding and documents.

## Required Contract

- `standard`: `GVE16`; `mode`: `gameplay` or `interaction`.
- Deterministic `SCN-*`, `EVT-*`, `CMP-*`, and `FLOW-*` identifiers.
- Every event contains trigger/action, before state, response, after state, and non-empty video evidence.
- Evidence contains source frame, scene, timestamp, evidence level, and confidence.
- Evidence levels normalize to `observed`, `inferred`, or `unknown`; defaults must be explicitly labeled in prose or extensions.
- Gameplay mode supplies core loop and visible rules; interaction mode supplies task flow, component-state information, and any observed `叙事`、`引导`、`红点提示` rule domains.
- Interaction narrative records trigger scene/node, presentation, and post-playback flow; guidance records trigger scope/count, prerequisites, ordered steps, target component, prompt copy, and completion destination; red-dot rules record show condition, clear condition, and full penetration path. Unobserved fields remain `待确认`.
- `designHandoff.status` remains `schema-ready` until an external connector actually writes an artifact.

## Validation

Run `validate_planning_model` before rendering. Reject invalid modes, missing collections, missing evidence, unresolved references, or non-serializable values. Preserve structured dict/list states; never coerce them through set membership.

## Rendering

Generate the human-readable GVE16 document from this model while retaining source frame IDs and timestamps. The JSON model and Markdown document are two views of the same conclusions.
