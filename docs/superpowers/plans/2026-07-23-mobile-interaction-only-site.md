# 2026-07-23 Mobile interaction-only site plan

## Scope
- Make the current site present as a mobile-first interaction planning tool.
- Hide non-current product entrances: gameplay selection, manual markdown download/copy, standards library authoring, and unrelated platform choices.
- Keep backend compatibility for existing jobs/tests, but force new UI-created jobs to `interaction` and `Mobile Web`.
- Make Feishu export the primary final action, with a clear authorization CTA when user login is missing/expired.

## Files likely to change
- `index.html`
- `css/style.css`
- `js/app.js`
- `js/backend.js`
- `js/feishu-publish.js`
- focused tests under `tests/` and `tests/js/`

## Verification
- Node tests for Feishu publication UI.
- Python UI contract tests.
- Focused backend publish API tests if server public state changes.
