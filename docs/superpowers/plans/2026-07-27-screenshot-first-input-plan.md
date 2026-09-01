# Screenshot-First Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make an ordered folder of 2–30 screenshots the default analysis input, retain one optional auxiliary video, and preserve the existing history, GVE16 review, and Feishu representative-frame delivery contracts.

**Architecture:** The browser owns folder filtering, natural ordering, preview/reordering, and multipart manifest creation. A focused backend image-sequence module validates the same contract again, persists normalized source images, and emits the existing frame/scene schema so analysis and delivery code can be reused. The processing dispatcher skips video extraction for image jobs; an optional video is analyzed afterward into non-blocking supplemental context and never changes primary frame IDs or order.

**Tech Stack:** Vanilla HTML/CSS/JavaScript, browser File/Directory APIs, FastAPI multipart uploads, Python 3.11, Pillow, OpenCV, existing OpenAI-compatible vision client, pytest, Node built-in test runner.

## Global Constraints

- The selected folder contributes only first-level JPG, JPEG, PNG, and WebP files; child-directory files are ignored.
- A task accepts 2–30 primary screenshots and at most one optional auxiliary video.
- Filenames do not require numeric prefixes; initial order uses `Intl.Collator("zh-CN", { numeric: true, sensitivity: "base" })`.
- The user-confirmed array order is authoritative; screenshot order alone does not prove a specific transition action.
- Re-selecting a folder replaces screenshots but preserves the auxiliary video; cancelling the picker changes nothing.
- Dragging is not the only ordering method: each screenshot has focusable move-up, move-down, and remove buttons.
- Auxiliary video is supplemental and non-blocking. It cannot add primary frames, renumber `F0001`–`F0030`, change screenshot order, or overwrite reviewed content.
- Existing video-only API requests remain accepted for compatibility.
- Existing GVE16 document format and Feishu UE-board representative-frame rules remain unchanged; all uploaded screenshots must not be copied into the document or board.
- Do not add a runtime dependency and do not implement the broader FlowDoc review UI in this change.

---

### Task 1: Pure screenshot selection and ordering model

**Files:**
- Create: `js/screenshot-input.js`
- Create: `tests/js/screenshot-input.test.js`
- Modify: `index.html` (load `js/screenshot-input.js` between `state.js` and `assets.js`)

**Interfaces:**
- Consumes: browser-like `File` objects with `name`, `type`, `size`, and optional `webkitRelativePath`.
- Produces: `selectTopLevelScreenshots(files: Iterable<File>): { accepted: File[], ignoredCount: number, nestedCount: number }`, `validateScreenshotCount(count: number): { valid: boolean, message: string }`, `moveItem(items: unknown[], fromIndex: number, toIndex: number): unknown[]`, and `buildImageManifest(assets: ScreenshotAsset[]): { clientId: string, originalName: string, order: number }[]`, where `ScreenshotAsset` is `{ id: string, file: File|null, kind: "image", name: string, size: number, type: string, url: string, relativePath: string, width: number, height: number }`.

- [ ] **Step 1: Write the failing model tests**

```js
test("filters to supported first-level images and sorts naturally", () => {
  const files = [
    fakeFile("10.png", "image/png", "shots/10.png"),
    fakeFile("2.png", "image/png", "shots/2.png"),
    fakeFile("nested.jpg", "image/jpeg", "shots/child/nested.jpg"),
    fakeFile("notes.txt", "text/plain", "shots/notes.txt"),
  ];
  const result = selectTopLevelScreenshots(files);
  assert.deepEqual(result.accepted.map((file) => file.name), ["2.png", "10.png"]);
  assert.equal(result.nestedCount, 1);
  assert.equal(result.ignoredCount, 1);
});

test("validates the inclusive 2 to 30 boundary", () => {
  assert.equal(validateScreenshotCount(1).valid, false);
  assert.equal(validateScreenshotCount(2).valid, true);
  assert.equal(validateScreenshotCount(30).valid, true);
  assert.equal(validateScreenshotCount(31).valid, false);
});

test("reordering and manifest generation use the same array order", () => {
  const moved = moveItem([{ id: "A", name: "a.png" }, { id: "B", name: "b.png" }], 1, 0);
  assert.deepEqual(buildImageManifest(moved), [
    { clientId: "B", originalName: "b.png", order: 1 },
    { clientId: "A", originalName: "a.png", order: 2 },
  ]);
});
```

- [ ] **Step 2: Run the model tests and verify RED**

Run: `node --test tests/js/screenshot-input.test.js`

Expected: FAIL because `js/screenshot-input.js` and its exported functions do not exist.

- [ ] **Step 3: Implement the dependency-free model**

```js
const SCREENSHOT_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);
const screenshotCollator = new Intl.Collator("zh-CN", { numeric: true, sensitivity: "base" });

function selectTopLevelScreenshots(files) {
  const all = Array.from(files || []);
  const rootName = (all.find((file) => file.webkitRelativePath)?.webkitRelativePath || "").split("/")[0];
  let ignoredCount = 0;
  let nestedCount = 0;
  const accepted = all.filter((file) => {
    const parts = String(file.webkitRelativePath || file.name).split("/").filter(Boolean);
    if (rootName && parts.length !== 2) { nestedCount += 1; return false; }
    if (!SCREENSHOT_TYPES.has(file.type)) { ignoredCount += 1; return false; }
    return true;
  }).sort((left, right) => screenshotCollator.compare(left.name, right.name));
  return { accepted, ignoredCount, nestedCount };
}

function validateScreenshotCount(count) {
  if (count < 2) return { valid: false, message: "请至少选择 2 张截图。" };
  if (count > 30) return { valid: false, message: "一次最多分析 30 张截图。" };
  return { valid: true, message: `已选择 ${count} 张截图，可以开始分析。` };
}

function moveItem(items, fromIndex, toIndex) {
  const copy = [...items];
  if (fromIndex < 0 || fromIndex >= copy.length || toIndex < 0 || toIndex >= copy.length) return copy;
  const [item] = copy.splice(fromIndex, 1);
  copy.splice(toIndex, 0, item);
  return copy;
}

function buildImageManifest(assets) {
  return assets.map((asset, index) => ({ clientId: asset.id, originalName: asset.name, order: index + 1 }));
}

if (typeof module !== "undefined") module.exports = { selectTopLevelScreenshots, validateScreenshotCount, moveItem, buildImageManifest };
```

- [ ] **Step 4: Run the model tests and verify GREEN**

Run: `node --test tests/js/screenshot-input.test.js`

Expected: all screenshot model tests PASS.

- [ ] **Step 5: Commit the model boundary**

```powershell
git add js/screenshot-input.js tests/js/screenshot-input.test.js index.html
git commit -m "feat: add screenshot input model"
```

---

### Task 2: Screenshot-folder and auxiliary-video user interface

**Files:**
- Modify: `index.html` (upload panel and asset script version)
- Modify: `css/style.css` (ordered preview, auxiliary-video row, focus, and mobile layout)
- Modify: `js/state.js` (separate `screenshots` and `auxiliaryVideo` state)
- Modify: `js/assets.js` (selection, decoding, rendering, reorder/delete, invalidation)
- Modify: `js/app.js` (event bindings and clear behavior)
- Create: `tests/js/screenshot-assets.test.js`
- Create: `tests/test_screenshot_input_ui_contract.py`

**Interfaces:**
- Consumes: Task 1 helpers and native inputs `#screenshotFolderInput` (`multiple webkitdirectory directory`) and `#auxVideoInput` (`accept="video/*"`).
- Produces: `state.screenshots: ScreenshotAsset[]`, `state.auxiliaryVideo: VideoAsset|null`, `replaceScreenshotFolder(files): Promise<void>`, `setAuxiliaryVideo(file|null): Promise<void>`, `reorderScreenshot(fromIndex, toIndex): void`, `removeScreenshot(index): void`, and `renderScreenshotInputs(): void`, where `VideoAsset` is `{ id: string, file: File|null, kind: "video", name: string, size: number, type: string, url: string, width: number, height: number, duration: number }`.

- [ ] **Step 1: Write failing DOM/model integration tests**

```js
test("replacing a folder preserves the auxiliary video and natural order", async () => {
  state.auxiliaryVideo = { id: "V01", name: "helper.mp4" };
  await replaceScreenshotFolder([
    fakeImage("10.png", "shots/10.png"),
    fakeImage("2.png", "shots/2.png"),
  ]);
  assert.deepEqual(state.screenshots.map((asset) => asset.name), ["2.png", "10.png"]);
  assert.equal(state.auxiliaryVideo.name, "helper.mp4");
});

test("moving or deleting screenshots invalidates the current result", () => {
  state.screenshots = [{ id: "A" }, { id: "B" }, { id: "C" }];
  state.frames = [{ id: "F0001" }];
  reorderScreenshot(2, 0);
  assert.deepEqual(state.screenshots.map((asset) => asset.id), ["C", "A", "B"]);
  assert.deepEqual(state.frames, []);
});
```

The Python contract must assert the two separate inputs, folder semantics, ordered preview live region, keyboard buttons, nearby validation text, visible `:focus-visible`, and a single-column mobile rule.

- [ ] **Step 2: Run integration tests and verify RED**

Run: `node --test tests/js/screenshot-assets.test.js; python -m pytest tests/test_screenshot_input_ui_contract.py -q`

Expected: FAIL because the new state, controls, renderer, and accessibility contract are absent.

- [ ] **Step 3: Implement the upload panel and state transitions**

Use this state shape and keep `state.assets` as a compatibility projection only where old frame code still reads it:

```js
const state = {
  screenshots: [],
  auxiliaryVideo: null,
  assets: [],
  frames: [],
  sceneGroups: [],
  analysisMode: "interaction",
  videoSummary: null,
  currentFrameIndex: 0,
  frameFilter: "scene_representatives",
  reviewUnsaved: false,
};

function syncLegacyAssets() {
  state.assets = [...state.screenshots, ...(state.auxiliaryVideo ? [state.auxiliaryVideo] : [])];
}

function invalidateScreenshotResult() {
  state.frames = [];
  state.sceneGroups = [];
  state.videoSummary = null;
  $("output").value = "";
  syncLegacyAssets();
}
```

The preview item must render its current `index + 1`, thumbnail, escaped filename, dimensions, drag handle, and three buttons with `aria-label="上移 …"`, `aria-label="下移 …"`, and `aria-label="删除 …"`. Disable up on the first item and down on the last. `dragend`, up/down, and delete all call the same `reorderScreenshot`/`removeScreenshot` functions. `renderStats()` enables `#extractBtn` only when `validateScreenshotCount(state.screenshots.length).valid` and all screenshots have positive width/height.

- [ ] **Step 4: Add responsive and accessible styling**

```css
.screenshot-preview-list { display: grid; gap: 10px; margin-top: 16px; }
.screenshot-preview-item { display: grid; grid-template-columns: 36px 72px minmax(0,1fr) auto; gap: 12px; align-items: center; }
.screenshot-preview-item img { width: 72px; height: 72px; object-fit: cover; border-radius: 10px; }
.screenshot-order-actions { display: flex; gap: 6px; }
.screenshot-preview-item button:focus-visible, .folder-picker:focus-visible { outline: 3px solid var(--brand); outline-offset: 2px; }
@media (max-width: 700px) {
  .screenshot-preview-item { grid-template-columns: 32px 56px minmax(0,1fr); }
  .screenshot-order-actions { grid-column: 1 / -1; }
}
```

- [ ] **Step 5: Run integration tests and syntax checks**

Run: `node --test tests/js/screenshot-input.test.js tests/js/screenshot-assets.test.js; node --check js/screenshot-input.js; node --check js/assets.js; node --check js/app.js; python -m pytest tests/test_screenshot_input_ui_contract.py -q`

Expected: all commands PASS.

- [ ] **Step 6: Commit the screenshot-first interface**

```powershell
git add index.html css/style.css js/state.js js/assets.js js/app.js tests/js/screenshot-assets.test.js tests/test_screenshot_input_ui_contract.py
git commit -m "feat: add screenshot folder workflow"
```

---

### Task 3: Backend image-sequence validation and persistence

**Files:**
- Create: `backend/image_sequence.py`
- Create: `tests/test_image_sequence.py`
- Modify: `backend/storage.py` (create `source_images` and `auxiliary` directories for every new job)

**Interfaces:**
- Consumes: `persist_image_sequence(job_dir: Path, uploads: list[UploadFile], manifest_json: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]`.
- Produces: frames with existing keys `id`, `timestamp`, `sequenceIndex`, `sceneId`, `imageUrl`, `sourceName`, `structure`, `analysis`, `confirmed`, and `perceptualHash`; one scene per screenshot; ScreenCoder-compatible component tracks.

- [ ] **Step 1: Write failing validation and persistence tests**

```python
def test_persists_manifest_order_as_stable_frames(tmp_path):
    uploads = [upload("10.png", PNG_BYTES), upload("2.png", PNG_BYTES)]
    manifest = json.dumps([
        {"clientId": "B", "originalName": "2.png", "order": 1},
        {"clientId": "A", "originalName": "10.png", "order": 2},
    ])
    frames, scenes, _tracks = persist_image_sequence(tmp_path, uploads, manifest)
    assert [(f["id"], f["sourceName"], f["sequenceIndex"], f["sceneId"]) for f in frames] == [
        ("F0001", "2.png", 1, 0),
        ("F0002", "10.png", 2, 1),
    ]
    assert [scene["frameIds"] for scene in scenes] == [["F0001"], ["F0002"]]
    assert all((tmp_path / "frames" / Path(frame["imageUrl"]).name).exists() for frame in frames)

@pytest.mark.parametrize("count", [1, 31])
def test_rejects_counts_outside_contract(tmp_path, count):
    with pytest.raises(ImageSequenceError, match="2.*30"):
        persist_image_sequence(tmp_path, make_uploads(count), make_manifest(count))
```

Add cases for unsupported MIME/extension, corrupt bytes, manifest/file count mismatch, duplicate or non-contiguous order, and a manifest filename with no matching upload.

- [ ] **Step 2: Run persistence tests and verify RED**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_image_sequence.py -q`

Expected: collection FAILS with `ModuleNotFoundError: backend.image_sequence`.

- [ ] **Step 3: Implement strict normalization and existing-schema emission**

```python
class ImageSequenceError(ValueError):
    pass

def persist_image_sequence(job_dir: Path, uploads: list[UploadFile], manifest_json: str):
    manifest = _parse_manifest(manifest_json)
    if not 2 <= len(uploads) <= 30:
        raise ImageSequenceError("截图数量必须为 2–30 张")
    if len(manifest) != len(uploads):
        raise ImageSequenceError("图片清单长度与上传文件数量不一致")
    ordered = _match_uploads_by_name(uploads, manifest)
    adapter = ScreenCoderAdapter()
    frames, scenes, tracks = [], [], {}
    previous_elements = []
    for index, (entry, upload) in enumerate(ordered, 1):
        source_bytes = upload.file.read()
        image = _decode_supported_image(upload.filename, upload.content_type, source_bytes)
        frame_id = f"F{index:04d}"
        source_filename = f"{frame_id}{_normalized_suffix(upload.filename)}"
        (job_dir / "source_images" / source_filename).write_bytes(source_bytes)
        filename = f"{frame_id}.jpg"
        frame_path = job_dir / "frames" / filename
        _write_normalized_jpeg(frame_path, image)
        structure = adapter.analyze(frame_path, job_dir / "structures")
        _assign_tracks(structure.get("elements", []), previous_elements, tracks, frame_id, float(index - 1))
        previous_elements = structure.get("elements", [])
        frames.append({
            "id": frame_id, "timestamp": float(index - 1), "sequenceIndex": index,
            "sceneId": index - 1, "sourceName": entry["originalName"],
            "imageUrl": f"/artifacts/{job_dir.name}/frames/{filename}",
            "structure": structure, "analysis": {}, "confirmed": False,
            "perceptualHash": f"{_difference_hash(image):016x}",
        })
        scenes.append({"id": index - 1, "start": float(index - 1), "end": float(index - 1), "frameIds": [frame_id], "analysis": {}})
    return frames, scenes, list(tracks.values())
```

Private helpers must parse JSON as a list of objects, require exact keys/types, require orders equal to `1..N`, reject ambiguous duplicate names, decode bytes before the job is submitted for processing, and store original names only as metadata—not as filesystem paths. Original bytes are retained under the generated `source_images/Fxxxx.<ext>` name; analysis/Feishu always uses normalized RGB JPEGs under `frames/Fxxxx.jpg` so MIME handling is deterministic.

- [ ] **Step 4: Run persistence tests and verify GREEN**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_image_sequence.py -q`

Expected: all image-sequence tests PASS.

- [ ] **Step 5: Commit backend image ingestion**

```powershell
git add backend/image_sequence.py backend/storage.py tests/test_image_sequence.py
git commit -m "feat: persist ordered screenshot sequences"
```

---

### Task 4: Dual-mode job creation, processing, retry, and document wording

**Files:**
- Modify: `backend/server.py`
- Modify: `backend/analysis_service.py`
- Modify: `backend/planner.py`
- Create: `tests/test_image_sequence_api.py`
- Modify: `tests/test_analysis_batch_policy.py`
- Modify: `tests/test_planner.py`

**Interfaces:**
- Consumes: Task 3 `persist_image_sequence(...)`; existing `reconcile_and_audit(...)` and `generate_plan(...)`.
- Produces: `POST /api/jobs` with `images: list[UploadFile] | None = File(None)`, `image_manifest: str = Form("")`, and optional `video: UploadFile | None = File(None)`; `_process(job_id: str, runtime_config: dict[str, Any])`; `analyze_video(..., input_type: str = "video")`; job metadata `inputType` equal to `image_sequence` or `video`. The task also defines `_persist_primary_video(job_id: str, upload: UploadFile) -> str`, `_persist_auxiliary_video(job_id: str, upload: UploadFile) -> dict[str, Any]`, `_remove_unstarted_job(job_id: str) -> None`, `_primary_video_path(job_id: str) -> Path`, `_prepare_video_frames(job_id: str, source: Path, runtime_config: dict[str, Any], progress: Progress) -> tuple[list[dict], list[dict]]`, and `_finish_job(job_id: str, frames: list[dict], scenes: list[dict], summary: dict) -> None` by extracting the corresponding existing statements without changing their behavior.

- [ ] **Step 1: Write failing API and processing-dispatch tests**

```python
def test_create_image_job_preserves_order_and_skips_video_extraction(monkeypatch):
    submitted = []
    monkeypatch.setattr(server.executor, "submit", lambda fn, *args: submitted.append((fn, args)))
    response = server.create_job(
        video=None, images=[upload("b.png"), upload("a.png")],
        image_manifest='[{"clientId":"a","originalName":"a.png","order":1},{"clientId":"b","originalName":"b.png","order":2}]',
        mode="interaction", project_name="截图任务", scope="", api_base="", model="", api_key="",
        transcription_api_base="", transcription_model="whisper-1", transcription_api_key="", standard_id="",
    )
    assert response["metadata"]["inputType"] == "image_sequence"
    assert [frame["sourceName"] for frame in response["frames"]] == ["a.png", "b.png"]
    assert submitted[0][0] is server._process
```

Add tests that: video-only creation still works; neither input returns 400; images plus an auxiliary video stay `image_sequence`; `_process` does not call `inspect_video` or `extract_and_structure` for image jobs; retry and reanalysis find image evidence without requiring `source.*`; planner analysis说明 says `原始截图`/`顺序位置` for image jobs and retains `原视频`/time wording for legacy video jobs.

Add one analysis policy test proving seven image-sequence screenshots are sent in two overlapping batches of at most six, every adjacent pair appears together in at least one request, and video interaction analysis retains its existing representative-frame policy.

- [ ] **Step 2: Run API tests and verify RED**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_image_sequence_api.py tests/test_planner.py -q`

Expected: FAIL because `create_job` still requires a video and `_process` has a video-path-only signature.

- [ ] **Step 3: Extend create-job atomically**

Use the following dispatch contract:

```python
@app.post("/api/jobs")
def create_job(
    video: UploadFile | None = File(None),
    images: list[UploadFile] | None = File(None),
    image_manifest: str = Form(""),
    mode: str = Form("gameplay"),
    project_name: str = Form("未命名项目"),
    scope: str = Form(""),
    api_base: str = Form(""), model: str = Form(""), api_key: str = Form(""),
    transcription_api_base: str = Form(""), transcription_model: str = Form("whisper-1"),
    transcription_api_key: str = Form(""), standard_id: str = Form(""),
) -> dict[str, Any]:
    uploads = images or []
    input_type = "image_sequence" if uploads else "video"
    if not uploads and video is None:
        raise HTTPException(400, "请上传 2–30 张截图")
    job = new_job({"mode": mode, "projectName": project_name, "scope": scope,
                   "inputType": input_type, "standardId": standard_id or None})
    try:
        if uploads:
            frames, scenes, tracks = persist_image_sequence(job_path(job["id"]), uploads, image_manifest)
            job.update(frames=frames, scenes=scenes, componentTracks=tracks, checkpoint="frames-complete")
            if video is not None:
                job["auxiliaryVideo"] = _persist_auxiliary_video(job["id"], video)
        else:
            job["sourceUrl"] = _persist_primary_video(job["id"], video)
    except (ImageSequenceError, ValueError) as exc:
        _remove_unstarted_job(job["id"])
        raise HTTPException(400, str(exc)) from exc
    plan_example = ""
    if standard_id:
        standard_path = STANDARDS_ROOT / f"{standard_id}.json"
        if standard_path.exists():
            standard = json.loads(standard_path.read_text(encoding="utf-8"))
            plan_example = f"{standard.get('description', '')}\n{standard.get('planExample', '')}"
    standard_prompt = build_standard_prompt(mode, plan_example)
    ai_config = _runtime_ai_config(api_base, model, api_key)
    runtime_config = {
        **ai_config,
        "transcriptionApiBase": transcription_api_base.strip() or ai_config["apiBase"],
        "transcriptionModel": transcription_model.strip() or "whisper-1",
        "transcriptionApiKey": transcription_api_key.strip() or ai_config["apiKey"],
        "standardPrompt": standard_prompt,
    }
    job["runtimeProfile"] = {key: value for key, value in runtime_config.items() if "Key" not in key}
    save_job(job)
    executor.submit(_process, job["id"], runtime_config)
    return _public_job(job)
```

Validation must complete before `executor.submit`; on failure remove only the newly generated job directory after resolving it through `job_path(job_id)`, so interrupted uploads do not appear in history.

- [ ] **Step 4: Dispatch processing and preserve retry/reanalysis**

```python
def _process(job_id: str, runtime_config: dict[str, Any]) -> None:
    job = load_job(job_id)
    if job["metadata"].get("inputType") == "image_sequence":
        frames, scenes = job["frames"], job["scenes"]
    else:
        source = _primary_video_path(job_id)
        frames, scenes = _prepare_video_frames(job_id, source, runtime_config, progress)
    input_type = job["metadata"].get("inputType", "video")
    frames, scenes, summary = analyze_video(job_path(job_id), frames, scenes, runtime_config,
                                            job["metadata"]["mode"], progress, input_type=input_type)
    _finish_job(job_id, frames, scenes, summary)
```

For `input_type="image_sequence"`, `analysis_service.py` analyzes every primary screenshot, uses overlapping batches `[0:6], [5:11], …` so each adjacent pair is visible together, and adds to the prompt: “截图顺序只表示用户给出的流程顺序；分别识别单页事实，并仅将有画面支撑的相邻变化写为推断，无法证明的操作写待确认。” This caps a 30-image job at six detail requests rather than reusing the video frame-by-frame policy.

`retry_job` resets to `checkpoint="frames-complete"` for image jobs and `None` for video jobs. `reanalyze_job` requires existing `frames` for both types and submits `_process(job_id, config)`. The image plan uses sequence labels (`第 1 张`, `第 2 张`) rather than pretending ordinal positions are video seconds.

- [ ] **Step 5: Run API, planner, and legacy regression tests**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_image_sequence_api.py tests/test_image_sequence.py tests/test_analysis_batch_policy.py tests/test_planner.py tests/test_history_access.py tests/test_video_to_gve16_contract.py -q`

Expected: all tests PASS, including legacy video creation assertions.

- [ ] **Step 6: Commit dual-mode processing**

```powershell
git add backend/server.py backend/analysis_service.py backend/planner.py tests/test_image_sequence_api.py tests/test_analysis_batch_policy.py tests/test_planner.py
git commit -m "feat: process screenshot sequence jobs"
```

---

### Task 5: Non-blocking auxiliary-video enrichment

**Files:**
- Create: `backend/auxiliary_video.py`
- Modify: `backend/analysis_service.py`
- Modify: `backend/server.py`
- Modify: `backend/planner.py`
- Create: `tests/test_auxiliary_video.py`
- Modify: `tests/test_planner.py`

**Interfaces:**
- Consumes: optional persisted auxiliary video path, primary analyzed frames, existing `_client`/`_call`, and `Progress`.
- Produces: `analyze_auxiliary_video(video_path: Path, job_dir: Path, primary_frames: list[dict[str, Any]], config: dict[str, Any], progress: Progress) -> dict[str, Any]` with `status`, `sampleCount`, `transitions`, `temporaryPrompts`, `operationTiming`, `uncertainties`, and `technicalError`; persists only in `job["auxiliaryVideo"]["analysis"]` and `analysisSummary["auxiliaryVideo"]`, then renders qualified items inside the existing GVE16 状态与异常 section.

- [ ] **Step 1: Write failing bounded-sampling and failure-isolation tests**

```python
def test_auxiliary_analysis_is_bounded_and_does_not_mutate_primary_frames(tmp_path, monkeypatch):
    primary = [{"id": "F0001"}, {"id": "F0002"}]
    before = copy.deepcopy(primary)
    monkeypatch.setattr(auxiliary_video, "_sample_video", lambda *_: make_samples(tmp_path, 8))
    monkeypatch.setattr(auxiliary_video, "_analyze_samples", lambda *_: {
        "transitions": [{"fromFrameId": "F0001", "toFrameId": "F0002", "motion": "淡入"}],
        "temporaryPrompts": [], "operationTiming": [], "uncertainties": []})
    result = analyze_auxiliary_video(tmp_path / "aux.mp4", tmp_path, primary, {}, lambda *_: None)
    assert result["status"] == "completed"
    assert result["sampleCount"] <= 12
    assert primary == before

def test_auxiliary_failure_returns_warning_instead_of_raising(tmp_path, monkeypatch):
    monkeypatch.setattr(auxiliary_video, "_sample_video", lambda *_: (_ for _ in ()).throw(ValueError("bad video")))
    result = analyze_auxiliary_video(tmp_path / "bad.mp4", tmp_path, [], {}, lambda *_: None)
    assert result["status"] == "failed"
    assert "bad video" in result["technicalError"]
```

- [ ] **Step 2: Run auxiliary tests and verify RED**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_auxiliary_video.py -q`

Expected: collection FAILS because `backend.auxiliary_video` does not exist.

- [ ] **Step 3: Implement a single-call, maximum-12-frame supplement**

`_sample_video` must inspect video metadata, sample uniform positions plus detected scene-change positions, deduplicate them, cap the result at 12 across the full duration, and save files under `job_dir / "auxiliary"`. `_analyze_samples` makes one low-detail vision request with the auxiliary samples plus a compact JSON summary of the already analyzed primary screenshots. Its prompt explicitly allows only transition/motion, temporary prompts, and operation timing tied to adjacent primary frame IDs. `analyze_auxiliary_video` catches every video/model exception and returns a failed status instead of raising.

```python
def analyze_auxiliary_video(video_path, job_dir, primary_frames, config, progress):
    try:
        samples = _sample_video(video_path, job_dir / "auxiliary", limit=12)
        analysis = _analyze_samples(samples, primary_frames, config)
        return {"status": "completed", "sampleCount": len(samples), **analysis, "technicalError": ""}
    except Exception as exc:
        return {"status": "failed", "sampleCount": 0, "transitions": [],
                "temporaryPrompts": [], "operationTiming": [], "uncertainties": [],
                "technicalError": str(exc)}
```

- [ ] **Step 4: Run enrichment only after primary screenshot analysis**

In `_process`, call `analyze_video` first. If `metadata.inputType == "image_sequence"` and an auxiliary path exists, call `analyze_auxiliary_video`; write its output into the two declared result fields; then continue audit/planning even when its status is `failed`. Do not merge its returned objects into `frames`, `scenes`, confirmed review fields, or Feishu media selection. In `planner.py`, `_auxiliary_state_notes(job)` converts successful items to inference-labelled bullets inside the existing 状态与异常 section and converts a failed status to one non-blocking pending-confirmation bullet; this keeps the GVE16 heading order unchanged.

- [ ] **Step 5: Run auxiliary and primary regressions**

Run: `$env:PYTHONPATH="$PWD\calibration_packages"; python -m pytest tests/test_auxiliary_video.py tests/test_image_sequence_api.py tests/test_analysis_batch_policy.py tests/test_planner.py tests/test_feishu_render.py tests/test_feishu_publish.py -q`

Expected: all tests PASS; assertions confirm the primary frame list and representative-frame output are unchanged.

- [ ] **Step 6: Commit auxiliary-video enrichment**

```powershell
git add backend/auxiliary_video.py backend/analysis_service.py backend/server.py backend/planner.py tests/test_auxiliary_video.py tests/test_planner.py
git commit -m "feat: add optional video enrichment"
```

---

### Task 6: Frontend multipart submission and history restoration

**Files:**
- Modify: `js/backend.js`
- Modify: `js/app.js`
- Modify: `js/frames-models.js` (sequence-position labels for image jobs)
- Create: `tests/js/screenshot-backend.test.js`
- Modify: `tests/js/archive-history.test.js`

**Interfaces:**
- Consumes: Task 1 `buildImageManifest`, Task 2 state, Task 4 public job fields `metadata.inputType`, `frames[].sourceName`, `frames[].sequenceIndex`, and optional `auxiliaryVideo`.
- Produces: `buildJobFormData(): FormData`, screenshot-first `extractWithIntegratedBackend()`, and history restoration in `syncBackendResult(job)`.

- [ ] **Step 1: Write failing payload and restoration tests**

```js
test("buildJobFormData appends screenshots in confirmed order", () => {
  state.screenshots = [asset("B", "2.png"), asset("A", "10.png")];
  state.auxiliaryVideo = asset("V", "helper.mp4", "video");
  const data = buildJobFormData();
  assert.deepEqual(data.getAll("images").map((file) => file.name), ["2.png", "10.png"]);
  assert.deepEqual(JSON.parse(data.get("image_manifest")).map((item) => item.order), [1, 2]);
  assert.equal(data.get("video").name, "helper.mp4");
});

test("syncBackendResult restores screenshot names and order from history", () => {
  syncBackendResult({ metadata: { inputType: "image_sequence", mode: "interaction" },
    frames: [serverFrame("F0001", "first.png", 1), serverFrame("F0002", "second.png", 2)],
    scenes: [], plan: "# plan" });
  assert.deepEqual(state.screenshots.map((item) => item.name), ["first.png", "second.png"]);
  assert.equal(state.screenshots[0].url, `${BACKEND_BASE}/artifacts/job/frames/F0001.png`);
});
```

- [ ] **Step 2: Run frontend backend tests and verify RED**

Run: `node --test tests/js/screenshot-backend.test.js tests/js/archive-history.test.js`

Expected: FAIL because submission still requires a video asset and history does not restore screenshot assets.

- [ ] **Step 3: Submit the authoritative screenshot order**

```js
function buildJobFormData() {
  const data = backendConfigForm();
  state.screenshots.forEach((asset) => data.append("images", asset.file, asset.name));
  data.append("image_manifest", JSON.stringify(buildImageManifest(state.screenshots)));
  if (state.auxiliaryVideo) data.append("video", state.auxiliaryVideo.file, state.auxiliaryVideo.name);
  data.append("mode", "interaction");
  data.append("project_name", $("projectName").value.trim() || "未命名项目");
  data.append("scope", $("scope").value.trim());
  data.append("transcription_api_base", $("transcriptionApiUrl").value.trim() || $("apiUrl").value.trim());
  data.append("transcription_model", $("transcriptionModel").value.trim() || "whisper-1");
  data.append("transcription_api_key", $("transcriptionApiKey").value.trim() || $("apiKey").value.trim());
  data.append("standard_id", $("standardSelect").value);
  return data;
}
```

`extractWithIntegratedBackend` returns `false` only when the backend health check fails, not when no video exists. It validates 2–30 screenshots before POST and uses screenshot-oriented upload/progress/error copy.

- [ ] **Step 4: Restore history without pretending remote URLs are local Files**

For `image_sequence`, map sorted backend frames to read-only preview assets with `file: null`, `url: BACKEND_BASE + frame.imageUrl`, `name: frame.sourceName`, `sequenceIndex`, and decoded dimensions when available. Show the auxiliary video filename/status from job metadata, but keep reorder controls disabled for a completed historical result until the user selects a new local folder. Use `第 N 张` in frame/timeline labels; hide the video player and time-axis percentages for image jobs.

- [ ] **Step 5: Run frontend tests and syntax checks**

Run: `node --test tests/js/screenshot-input.test.js tests/js/screenshot-assets.test.js tests/js/screenshot-backend.test.js tests/js/archive-history.test.js; node --check js/backend.js; node --check js/app.js; node --check js/frames-models.js`

Expected: all commands PASS.

- [ ] **Step 6: Commit submission and history restoration**

```powershell
git add js/backend.js js/app.js js/frames-models.js tests/js/screenshot-backend.test.js tests/js/archive-history.test.js
git commit -m "feat: submit and restore screenshot jobs"
```

---

### Task 7: End-to-end regression, visual QA, and minimality review

**Files:**
- Modify only if verification exposes a defect: files already listed in Tasks 1–6 and their tests.
- Do not add generated files from `artifacts/`, `data/jobs/`, logs, or local credentials to Git.

**Interfaces:**
- Consumes: the complete screenshot-first workflow.
- Produces: fresh automated and browser evidence that screenshot input, history, analysis, and Feishu representative-frame behavior satisfy the approved spec.

- [ ] **Step 1: Run the complete automated regression suite**

```powershell
$env:PYTHONPATH="$PWD\calibration_packages;$PWD\runtime_packages"
python -m pytest tests -q
node --test tests/js/*.test.js
python -m compileall backend api_server.py
Get-ChildItem js/*.js | ForEach-Object { node --check $_.FullName }
```

Expected: all pytest and Node tests PASS; compile and syntax commands exit 0.

- [ ] **Step 2: Start the service and run functional browser QA**

Run: `powershell -ExecutionPolicy Bypass -File .\start.ps1`

Verify in a desktop viewport and a 390px mobile viewport:

1. Select a folder containing `2.png`, `10.png`, a nested image, and a text file; only the two first-level images appear, in natural order, with ignored counts.
2. Add one auxiliary video; reorder screenshots by drag and then by keyboard buttons; video remains separate and screenshot numbering follows the array.
3. Confirm 1 and 31 screenshots block analysis while 2 and 30 enable it.
4. Create a real image-sequence job and confirm the backend reports `inputType=image_sequence`, stable `F0001…`, meaningful vision output, and no video-extraction stage.
5. Reload from local history and confirm filename/order/thumbnail restoration.
6. Confirm auxiliary-video failure produces a warning while the primary screenshot job completes.
7. Export a reviewed job and verify the Feishu document contains no separate evidence-frame gallery and the UE board receives only selected representative frames.

- [ ] **Step 3: Review the diff for scope and simplicity**

Run: `git diff --stat 60f0aad..HEAD; git diff --check 60f0aad..HEAD; git status --short`

Expected: no whitespace errors; no dependency-file changes; no FlowDoc review redesign; `artifacts/` remains untracked and unstaged. Remove duplicated helpers, dead compatibility branches, and unused CSS found by the focused ponytail review, then rerun Step 1.

- [ ] **Step 4: Commit verification-only fixes if any were required**

```powershell
git add backend js css tests index.html
git diff --cached --quiet; if ($LASTEXITCODE -ne 0) { git commit -m "fix: close screenshot workflow regressions" }
```

- [ ] **Step 5: Report the verified outcome**

Report exact test counts, the tested local/LAN URL, whether a real vision request produced qualified content, whether auxiliary failure isolation was exercised, and whether the Feishu representative-frame count matched the reviewed events. State any failed external dependency without describing the product change as complete.
