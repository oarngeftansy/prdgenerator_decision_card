# Evidence-to-output matrix

| Evidence | Can directly establish | Cannot establish alone | Typical output |
|---|---|---|---|
| Ordered screenshots | visible objects, UI states, displayed values, before/after changes, item variants | hidden probability, server ownership, exact formula, reset across sessions | evidence card, local screenshot, visible-state rule |
| Video sequence | trigger order, duration, repeated behavior, transition, failure shown on screen | configuration field names and unshown branches | rule sequence, state/branch matrix, acceptance case |
| Reference document | explicit rules, boundaries, reset/persistence, ownership, table/field names | facts not written in that document | rule body, configuration source, dependency |
| Spreadsheet/config table | field list, type/unit/value/range, categories, content catalog | player experience not represented by fields | parameter table, content catalog, formula inputs |
| Meeting/technical notes | server/client responsibility, algorithm choice, exit/re-entry behavior, implementation constraints | polished player-facing rules unless confirmed | technical constraint, boundary, state retention rule |
| Planner decision | approved hidden rule, exception, naming, scope | unrelated systems | confirmed rule with planner provenance |

## Reverse reasoning checklist

- Repeated visible variants imply a content catalog only when each item can be distinguished.
- A value changing across two states supports a state change, not automatically a formula.
- A formula needs an explicit reference source or confirmed planner rule.
- A table field name comes from a reference/config source, never from visual inference.
- Exit, re-entry, activity end, retry, cap, invalid target, and repeated operation are separate boundary evidence.
- A screenshot belongs beside the rule it proves. Do not reuse one image as generic evidence for unrelated chapters.

## Source-scope isolation

Every conclusion records one of: `current_material`, `current_reference`, `current_configuration`, `planner_decision`, or `sample_reserve`.

- The first four scopes may publish only what that source actually supports.
- `sample_reserve` may create an inspection responsibility or a decision question, but `publicationAllowed` must remain false until current-project evidence or a planner decision supports the conclusion.
- 局部截图与流程图就近放置：use `afterRuleId` to bind an image to the exact rule it clarifies; keep diagrams inside the owning mechanism and preserve the reviewed semantic flow.
- One evidenced fact maps to one publishing carrier. Other workbench fields reference it through `carrierRefs` instead of copying the sentence.
