# Phase 5 EntityBuilder Design

## Scope

Phase 5 only builds and audits the Logic/Data Entity Graph. It does not modify approved Rules, reviewed Gaps, the six-chapter reference document, P7 export, parameters, or presentation delivery.

## Public interface

```python
build_entity_graph(
    chapters,
    approved_rules,
    reviewed_gaps,
    entity_declarations,
) -> dict
```

The function is deterministic and does not call an LLM. Inputs are treated as immutable.

## Entity contract

Each entity contains:

- `entityId`, `name`, `entityType`, `semanticKey`
- `ownerEntityId`, `parentEntityId`, `childEntityIds`
- `primaryDefinitionChapter`, `referenceChapters`
- `relatedRuleIds`, `relatedGapIds`
- `declarationEvidence` and `definitionStatus`

Allowed `entityType` values are:

- `runtime_object`
- `container`
- `content_item`
- `candidate_set`
- `runtime_context`
- `process`
- `report`

The directory tree is not an entity registry. Current-project entities are supplied as explicit domain declarations, then linked to approved rules, reviewed gaps, and classified chapters. A declaration may remain `evidence_insufficient` when it has no non-presentation definition evidence.

## Relationship contract

Core edges are limited to:

- `owner`
- `parent_child`
- `source_target`

Every core edge records its evidence Rule IDs or an explicit approved domain-declaration reason. Open Gaps can be linked to entities but cannot confirm an edge. Presentation Rules cannot support a core edge.

Source/target inference requires an approved non-presentation Rule whose structured subject and behavior/object resolve to two declared entities. It must not use a heading or a visual phrase as the sole basis.

## Definition ownership

`primaryDefinitionChapter` is selected from chapters that define the entity with approved non-presentation rules. If none exists, a declaration may nominate the expected primary chapter, but the entity remains `evidence_insufficient`. Other chapters become references; they do not duplicate the definition.

## Presentation boundary

Presentation Rules are processed after the core graph is complete. They can receive `relatedEntityIds[]` by deterministic alias matching against existing entities. They cannot:

- create an entity;
- change an EntityType;
- assign owner or parent/child;
- create a source/target edge;
- promote a visual concept such as a red overlay, border, floating number, or layout into a core entity.

The output includes a pollution audit proving that no core entity or edge depends only on Presentation evidence.

## Current reference declarations

The Phase 5 reference implementation declares the user-approved domain nodes: 载具、武器、武器栏、三选一候选集、词条、怪物、首领、关卡、结算、伤害统计. These declarations establish identity and type only; their relations still require an explicit declaration reason or approved non-presentation Rule.

## Artifacts

- `entity-graph.json`: machine-readable graph and audit
- `entity-graph.md`: human-readable nodes and edges
- `presentation-reference-audit.json`: Presentation Rule one-way references and pollution findings
- `provenance.json`: source hashes and non-mutation checks

