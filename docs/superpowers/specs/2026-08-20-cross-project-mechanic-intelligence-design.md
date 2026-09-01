# Cross-Project Mechanic Recognition & Planning Intelligence

## Objective

Convert Mechanic Library into a composable planning knowledge graph. Evidence can activate several Mechanic Patterns in one feature; activated patterns expose only evidence-supported execution responsibilities and compose through shared project nodes.

## Authority Boundary

- Pattern data is `contentAuthority=none` and never supplies a project answer.
- Evidence, Approved Rule and current project relationships remain the only authority for existence and satisfaction.
- Game genre is never an existence signal.
- Unsupported responsibilities remain dormant rather than becoming missing requirements.

## Declarative Graph

The versioned JSON graph contains L1 domain, L2 family, L3 pattern, L4 responsibility, existence-signal and shared-concept nodes. Typed edges express `contains`, `specializes`, `may_activate`, `activated_by`, `shares_concept` and `depends_on`.

Pattern detection is additive. A candidate pattern is detected when its declarative signal contract is satisfied; every result carries evidence IDs, matched signal IDs, confidence, related entities and related patterns. Responsibility activation evaluates its own contract against signals, current rules and project relations.

## Generic Engine Outputs

- `DetectedMechanic[]`
- `ActivatedResponsibility[]`
- `ProjectMechanicGraph`
- `MissingRequirement[]`

No game-specific branch may be added to the engine. New genres and patterns are data additions plus benchmark cases.

## Acceptance

The migration suite contains at least 25 system, gameplay and hybrid cases. It checks mechanic recall/precision, responsibility recall/precision, high-value gaps, noise suppression, hierarchy, lifecycle, branch, algorithm, parameter and cross-system coverage.
