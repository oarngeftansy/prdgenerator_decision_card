# Feishu Native Planning Publication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish an approved gameplay or interaction plan as a native Feishu document inside the fixed “视频策划案生成中心” folder, with embedded UE flow whiteboards, evidence images, safe retries, and edit-conflict protection.

**Architecture:** Add a dependency-free Python boundary around `lark-cli.cmd`, pure renderers for Feishu XML and Mermaid, and a publication service that owns idempotency and persisted external-artifact state. FastAPI exposes publication commands and the existing browser renders those states without ever handling Feishu tokens.

**Tech Stack:** Python 3.11, FastAPI, subprocess, existing JSON job storage, `lark-cli` 1.0.73, Feishu Docx XML, Mermaid whiteboards, vanilla JavaScript/CSS, pytest, Node test runner.

## Global Constraints

- External writes happen only after an explicit “发布到飞书” click.
- Use Feishu user identity (`--as user`), never bot identity.
- Reuse the root-level folder named exactly `视频策划案生成中心`; create it only when absent.
- Never store or return Feishu access tokens, refresh tokens, App Secret, visual-model API keys, arbitrary shell text, or unrestricted local paths.
- Do not overwrite a Feishu document when its revision differs from the last successfully published revision.
- A repeated request with the same idempotency key must not create duplicate folders, documents, images, or whiteboards.
- Gameplay and interaction documents must preserve their distinct GVE16 chapter semantics.
- First version uses native Feishu XML and embedded Mermaid whiteboards; no cloud service or general-purpose whiteboard DSL.

---

### Task 1: Safe `lark-cli` execution boundary

**Files:**
- Create: `backend/feishu_cli.py`
- Test: `tests/test_feishu_cli.py`

**Interfaces:**
- Produces: `LarkResult`, `LarkCommandError`, `LarkCli.run(args: list[str], stdin: str | None = None) -> LarkResult`, `LarkCli.auth_status() -> dict[str, Any]`.
- Consumes: Windows executable `lark-cli.cmd`; callers pass logical argv only.

- [ ] **Step 1: Write failing execution-boundary tests**

```python
def test_cli_uses_argv_without_shell_and_parses_success(fake_process):
    cli = LarkCli(run_process=fake_process)
    result = cli.run(["auth", "status", "--json", "--verify"])
    assert result.data["identity"] == "user"
    assert fake_process.calls[0]["shell"] is False

def test_cli_rejects_unapproved_command():
    with pytest.raises(ValueError, match="command not allowed"):
        LarkCli().run(["drive", "+delete", "abc"])

def test_cli_turns_missing_scope_into_structured_error(fake_process):
    fake_process.stderr = json.dumps({"ok": False, "error": {"subtype": "missing_scope", "missing_scopes": ["drive:drive"]}})
    with pytest.raises(LarkCommandError) as caught:
        LarkCli(run_process=fake_process).run(["drive", "files", "list", "--as", "user"])
    assert caught.value.kind == "missing_scope"
```

- [ ] **Step 2: Run tests and verify RED**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_cli.py -q`

Expected: FAIL because `backend.feishu_cli` does not exist.

- [ ] **Step 3: Implement the smallest safe adapter**

```python
ALLOWED_PREFIXES = {
    ("auth", "status"),
    ("drive", "files", "list"),
    ("drive", "+create-folder"),
    ("docs", "+create"),
    ("docs", "+fetch"),
    ("docs", "+update"),
    ("docs", "+media-insert"),
    ("whiteboard", "+query"),
}

class LarkCli:
    def run(self, args, stdin=None):
        if not any(tuple(args[:len(prefix)]) == prefix for prefix in ALLOWED_PREFIXES):
            raise ValueError("command not allowed")
        completed = self._run_process(
            [self.executable, *args], input=stdin, text=True,
            capture_output=True, shell=False, timeout=self.timeout,
        )
        payload = json.loads(completed.stdout or completed.stderr)
        if completed.returncode or payload.get("ok") is False:
            raise LarkCommandError.from_payload(payload)
        return LarkResult(data=payload.get("data", payload), raw=payload)
```

The implementation must scrub token-shaped values from exceptions and logs, map `missing_scope`, `not_authenticated`, `confirmation_required`, `timeout`, and `command_failed`, and never accept `--yes` or path arguments outside the supplied task directory.

- [ ] **Step 4: Run tests and verify GREEN**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_cli.py -q`

Expected: all adapter tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/feishu_cli.py tests/test_feishu_cli.py
git commit -m "feat: add safe Feishu CLI boundary"
```

### Task 2: Native document and UE flow renderers

**Files:**
- Create: `backend/feishu_render.py`
- Test: `tests/test_feishu_render.py`
- Read: `backend/planning_model.py`
- Read: `backend/planner.py`

**Interfaces:**
- Consumes: validated `planningModel` from `build_planning_model(job)`.
- Produces: `render_feishu_document(job: dict[str, Any]) -> RenderedFeishuDocument` and `render_ue_flow(model: dict[str, Any]) -> str`.

- [ ] **Step 1: Write failing renderer tests**

```python
def test_gameplay_document_uses_native_sections_and_embedded_flow(gameplay_job):
    rendered = render_feishu_document(gameplay_job)
    assert rendered.title.startswith("Demo｜玩法策划案｜")
    assert "<h1>玩法目标与核心机制</h1>" in rendered.xml
    assert '<whiteboard type="mermaid">' in rendered.xml
    assert "玩家操作" in rendered.mermaid
    assert "default-loading" not in rendered.xml

def test_interaction_document_uses_interaction_sections(interaction_job):
    rendered = render_feishu_document(interaction_job)
    assert "<h1>页面与组件说明</h1>" in rendered.xml
    assert "显示条件" in rendered.xml
    assert "系统响应" in rendered.mermaid

def test_renderer_escapes_user_text_without_escaping_tags(gameplay_job):
    gameplay_job["planningModel"]["overview"]["summary"] = "A < B & C"
    xml = render_feishu_document(gameplay_job).xml
    assert "A &lt; B &amp; C" in xml
    assert "&lt;h1&gt;" not in xml
```

- [ ] **Step 2: Run tests and verify RED**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_render.py -q`

Expected: FAIL because renderer functions do not exist.

- [ ] **Step 3: Implement typed render output and mode-specific sections**

```python
@dataclass(frozen=True)
class EvidenceImage:
    frame_id: str
    path: Path
    anchor_text: str
    caption: str

@dataclass(frozen=True)
class RenderedFeishuDocument:
    title: str
    xml: str
    mermaid: str
    evidence_images: tuple[EvidenceImage, ...]
    content_fingerprint: str
```

Render a single `<title>`, restrained heading hierarchy, narrative paragraphs, tables only for real row/column data, one “待确认项” callout at most, and one `<whiteboard type="mermaid">...</whiteboard>` under the UE flow section. Generate stable node IDs from planning-model event IDs; escape Mermaid labels separately from XML text.

- [ ] **Step 4: Run renderer tests and existing planner tests**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_render.py tests/test_planner.py tests/test_planning_model.py -q`

Expected: PASS with no change to Markdown generation.

- [ ] **Step 5: Commit**

```powershell
git add backend/feishu_render.py tests/test_feishu_render.py
git commit -m "feat: render native Feishu planning documents"
```

### Task 3: Idempotent publication service and conflict protection

**Files:**
- Create: `backend/feishu_publish.py`
- Test: `tests/test_feishu_publish.py`
- Modify: `backend/storage.py`

**Interfaces:**
- Consumes: `LarkCli`, `RenderedFeishuDocument`, persisted job dict.
- Produces: `FeishuPublisher.publish(job, request_id, mode) -> PublicationRecord` where mode is `update` or `new_version`.

- [ ] **Step 1: Write failing service tests with a fake CLI**

```python
def test_first_publish_creates_one_folder_and_one_document(fake_cli, completed_job):
    record = FeishuPublisher(fake_cli).publish(completed_job, "req-00000001", "update")
    assert fake_cli.count("drive +create-folder") == 1
    assert fake_cli.count("docs +create") == 1
    assert record.status == "published"

def test_retry_reuses_resources(fake_cli, completed_job):
    publisher = FeishuPublisher(fake_cli)
    first = publisher.publish(completed_job, "req-00000002", "update")
    second = publisher.publish(completed_job, "req-00000002", "update")
    assert second.document_token == first.document_token
    assert fake_cli.count("docs +create") == 1

def test_external_revision_change_blocks_overwrite(fake_cli, published_job):
    fake_cli.current_revision = published_job["feishuPublication"]["revision"] + 1
    with pytest.raises(PublicationConflict):
        FeishuPublisher(fake_cli).publish(published_job, "req-00000003", "update")
```

- [ ] **Step 2: Run tests and verify RED**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_publish.py -q`

Expected: FAIL because the publication service does not exist.

- [ ] **Step 3: Implement the state machine and exact CLI operations**

Use these argv forms through `LarkCli`, always with `--as user --json`:

```text
drive files list --page-all
drive +create-folder --name 视频策划案生成中心
docs +create --parent-token <folder_token> --content -
docs +fetch --doc <doc_token> --scope full --detail full
docs +update --doc <doc_token> --command overwrite --revision-id <last_revision> --content -
docs +media-insert --doc <doc_token> --file <task-relative-image> --caption <caption> --selection-with-ellipsis <anchor>
whiteboard +query --whiteboard-token <board_token> --output_as code
```

Persist `folderToken`, `documentToken`, `documentUrl`, `whiteboardTokens`, `revision`, `fingerprint`, `requestId`, step states, and timestamps under `job["feishuPublication"]`. Search the root listing for exact folder name before creation. For `new_version`, derive the next `V2`, `V3` suffix from local publication history. Save after every successful external step so retries resume safely.

- [ ] **Step 4: Verify partial failure recovery**

Add tests where document creation succeeds and media insertion or whiteboard verification fails. On retry, assert document creation count remains one and status advances from `partial` to `published`.

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_publish.py -q`

Expected: all publication tests PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/feishu_publish.py backend/storage.py tests/test_feishu_publish.py
git commit -m "feat: publish plans to Feishu idempotently"
```

### Task 4: FastAPI publication endpoints and public-state scrubbing

**Files:**
- Modify: `backend/server.py`
- Test: `tests/test_feishu_publish_api.py`

**Interfaces:**
- Produces: `POST /api/jobs/{job_id}/feishu/publish`, `GET /api/jobs/{job_id}/feishu/publication`.
- Consumes: JSON body `{ "requestId": string, "mode": "update" | "new_version" }`.

- [ ] **Step 1: Write failing API tests**

```python
def test_publish_requires_completed_plan(client, incomplete_job):
    response = client.post(f"/api/jobs/{incomplete_job['id']}/feishu/publish", json={"requestId": "req-00000004", "mode": "update"})
    assert response.status_code == 409

def test_publication_api_never_returns_credentials(client, published_job):
    response = client.get(f"/api/jobs/{published_job['id']}/feishu/publication")
    text = response.text.lower()
    assert "access_token" not in text
    assert "refresh_token" not in text
    assert "appsecret" not in text
```

- [ ] **Step 2: Run tests and verify RED**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_publish_api.py -q`

Expected: FAIL with endpoint not found.

- [ ] **Step 3: Implement asynchronous publication endpoints**

Validate request IDs with `^[A-Za-z0-9_-]{10,80}$`, reject archived/incomplete jobs, return `202` while publishing, `409` for revision conflicts, and `503` for missing CLI or authentication. Add public status to `_public_job` using an allowlist rather than returning raw CLI payloads.

- [ ] **Step 4: Run API and existing regression tests**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_feishu_publish_api.py tests/test_local_evidence_api.py tests/test_video_to_gve16_contract.py -q`

Expected: PASS; existing job serialization remains compatible.

- [ ] **Step 5: Commit**

```powershell
git add backend/server.py tests/test_feishu_publish_api.py
git commit -m "feat: expose Feishu publication API"
```

### Task 5: Website publication interaction

**Files:**
- Modify: `index.html`
- Modify: `js/backend.js`
- Create: `js/feishu-publish.js`
- Modify: `js/app.js`
- Modify: `css/style.css`
- Test: `tests/js/feishu-publish.test.js`
- Test: `tests/test_feishu_publish_ui_contract.py`

**Interfaces:**
- Consumes: publication API state.
- Produces: `publishToFeishu(mode)`, `pollFeishuPublication()`, `renderFeishuPublication(publication)`.

- [ ] **Step 1: Write failing UI model and contract tests**

```javascript
test("published state exposes open, update, and new-version actions", () => {
  const html = renderFeishuPublication({ status: "published", documentUrl: "https://example.feishu.cn/docx/abc" });
  assert.match(html, /打开飞书文档/);
  assert.match(html, /更新飞书文档/);
  assert.match(html, /另存为新版本/);
});

test("conflict explains that Feishu edits are protected", () => {
  const html = renderFeishuPublication({ status: "conflict" });
  assert.match(html, /飞书文档已有修改/);
  assert.match(html, /不会覆盖/);
});
```

The Python contract test must assert one primary “发布到飞书” button, an `aria-live` status region, no token input, and touch targets at least 44 px high.

- [ ] **Step 2: Run tests and verify RED**

Run: `node --test tests/js/feishu-publish.test.js; python -m unittest tests.test_feishu_publish_ui_contract`

Expected: FAIL because the module and controls are absent.

- [ ] **Step 3: Implement in-place publication UI**

Keep the user in the output section. Generate the idempotency request ID once per click and reuse it through polling/retry. Render planner-language states: “正在检查飞书登录”“正在创建文档”“正在上传关键帧”“正在创建 UE 流转图”“已发布到飞书”“飞书登录已过期”“飞书文档已有修改，不会自动覆盖”. Disable publication when no validated plan exists.

- [ ] **Step 4: Run frontend tests and syntax checks**

Run: `node --test tests/js/feishu-publish.test.js tests/js/frame-renderer-contract.test.js; node --check js/feishu-publish.js; node --check js/backend.js; node --check js/app.js; python -m unittest tests.test_feishu_publish_ui_contract`

Expected: all tests and syntax checks PASS.

- [ ] **Step 5: Commit**

```powershell
git add index.html js/feishu-publish.js js/backend.js js/app.js css/style.css tests/js/feishu-publish.test.js tests/test_feishu_publish_ui_contract.py
git commit -m "feat: add Feishu publication workflow"
```

### Task 6: Authentication guidance, real dry run, and end-to-end verification

**Files:**
- Modify: `README.md`
- Modify: `docs/ARCHITECTURE.md`
- Test: `tests/test_feishu_publish_contract.py`

**Interfaces:**
- Consumes: completed publication workflow.
- Produces: operator instructions and a verified end-to-end path.

- [ ] **Step 1: Add contract coverage for operational guarantees**

Test that the implementation invokes `lark-cli.cmd`, requires user identity, uses the exact fixed folder name, rejects arbitrary CLI commands and absolute media paths, persists only the publication allowlist, and never claims `published` before document fetch and whiteboard query verification succeed.

- [ ] **Step 2: Document setup and recovery**

Document these Windows commands and behaviors:

```powershell
lark-cli.cmd --version
lark-cli.cmd auth status --json --verify
lark-cli.cmd auth login --domain docs --domain drive --no-wait --json
```

Explain that the current machine reports user `岛岛` but has no usable user token, so the first real publish must complete user authorization. Do not record verification URLs or device codes in repository files.

- [ ] **Step 3: Run the full focused suite**

Run:

```powershell
$env:PYTHONPATH="$PWD\calibration_packages"
python -m pytest tests/test_feishu_cli.py tests/test_feishu_render.py tests/test_feishu_publish.py tests/test_feishu_publish_api.py tests/test_feishu_publish_contract.py tests/test_planner.py tests/test_video_to_gve16_contract.py -q
node --test tests/js/feishu-publish.test.js tests/js/frame-reviewer.test.js tests/js/frame-renderer-contract.test.js
python -m unittest tests.test_feishu_publish_ui_contract tests.test_single_frame_ui_contract
python -m compileall -q backend
python -c "import backend.server"
```

Expected: all tests pass with no credential material in output.

- [ ] **Step 4: Complete user authorization only when ready for a real write**

Run `lark-cli.cmd auth login --domain docs --domain drive --no-wait --json`, generate the required QR code from the returned opaque verification URL, show both to the user, end the turn, and wait for explicit confirmation. In the following turn, complete the device-code flow and re-run `auth status --json --verify`.

- [ ] **Step 5: Perform one real publication acceptance test**

From an existing completed job, click “发布到飞书” once and verify:

- exactly one root folder named “视频策划案生成中心” exists;
- exactly one correctly named document is created;
- mode-specific headings and evidence images render;
- the embedded UE flow contains readable nodes and edges;
- the website opens the returned Feishu URL;
- retrying the same request creates no duplicate artifact;
- changing the Feishu document and publishing again produces `conflict` rather than overwriting it.

- [ ] **Step 6: Final simplification and verification review**

Run `git diff --check`, inspect the scoped diff for duplicate state machines, unused helpers, shell-string construction, credential leakage, and unnecessary dependencies, apply safe simplifications, then repeat Step 3.

- [ ] **Step 7: Commit**

```powershell
git add README.md docs/ARCHITECTURE.md tests/test_feishu_publish_contract.py
git commit -m "docs: verify Feishu publication workflow"
```
