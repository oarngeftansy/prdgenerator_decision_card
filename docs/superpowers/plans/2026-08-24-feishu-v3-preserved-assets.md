# Feishu v3 Preserved Assets Delivery Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新建《一路狂飙》v3 飞书执行案，正文消费当前 v3，并保留上一版玩法流程图和配置表。

**Architecture:** 使用飞书 Drive copy 复制上一版文档以保留原生资源，再用 block-aware 更新重组正文。发布脚本维护唯一 checkpoint，失败时复用副本，完成后全文回读验证。

**Tech Stack:** lark-cli、DocxXML、Python、现有 Feishu CLI wrapper。

## Global Constraints

- 不新建 UE、竞品、UX 画板；删除副本中的对应旧区域。
- 正文唯一事实源为 Final Delivery Candidate v3。
- 保留玩法流程图和配置表；无法映射 Owner 的旧图表进入附录。
- 实际 H2 使用飞书原生编号，不生成独立编号目录。
- 不修改用户现有未提交的 `scripts/publish_current_alignment_to_feishu.py`。

---

### Task 1: 建立副本重组清单和发布脚本

**Files:**
- Create: `scripts/publish_yilu_v3_preserving_assets.py`
- Create: `artifacts/yilu-kuangbiao-feishu-v3-2026-08-24/asset-retention-manifest.json`
- Test: `tests/test_yilu_v3_feishu_payload.py`

**Interfaces:**
- Consumes: v3 Markdown/JSON、旧文档 token、旧文档 full XML。
- Produces: `build_v3_feishu_payload(old_document, final_v3, manifest)` 和 idempotent checkpoint。

- [ ] **Step 1: 写 payload 红测试**

```python
def test_v3_payload_keeps_gameplay_figures_and_tables_but_removes_retired_boards():
    payload = build_v3_feishu_payload(_old_doc_fixture(), _v3_fixture(), _manifest())
    assert "图示：普通怪物行为状态" in payload
    assert "配置表：三选一配置" in payload
    assert "UE流转图" not in payload
    assert "竞品参考" not in payload
    assert "自动编号目录" not in payload
```

- [ ] **Step 2: 运行红测试**

Run: `python -m pytest tests/test_yilu_v3_feishu_payload.py -q -p no:cacheprovider --basetemp .test-tmp/feishu-v3-red`

Expected: FAIL。

- [ ] **Step 3: 实现纯函数 payload builder 与 manifest**

manifest 明确列出保留图示、配置表、目标章节和旧 block id；脚本不读取旧正文作为 Rule 来源。

- [ ] **Step 4: 运行测试**

Run: `python -m pytest tests/test_yilu_v3_feishu_payload.py tests/test_feishu_publish.py -q -p no:cacheprovider --basetemp .test-tmp/feishu-v3-green`

Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add scripts/publish_yilu_v3_preserving_assets.py artifacts/yilu-kuangbiao-feishu-v3-2026-08-24/asset-retention-manifest.json tests/test_yilu_v3_feishu_payload.py
git commit -m "Prepare v3 Feishu delivery with preserved assets"
```

### Task 2: 创建、写入和远端验收

**Files:**
- Create: `artifacts/yilu-kuangbiao-feishu-v3-2026-08-24/publication-checkpoint.json`
- Create: `artifacts/yilu-kuangbiao-feishu-v3-2026-08-24/remote-verification.json`
- Create: `artifacts/yilu-kuangbiao-feishu-v3-2026-08-24/remote-outline.xml`

**Interfaces:**
- Consumes: Task 1 payload 和已验证 user identity。
- Produces: 新 document URL/token、远端 revision、保留资源核验结果。

- [ ] **Step 1: lark-cli dry-run 与授权检查**

Run: `lark-cli auth status --json --verify`

Expected: user identity ready、verified=true。

- [ ] **Step 2: 复制旧文档并保存 checkpoint**

使用 `lark-drive` 的文档 copy 命令，副本标题为《一路狂飙》玩法策划执行案｜Final Delivery Candidate v3 / Planner Review Ready。若 checkpoint 已有 document token，复用该副本。

- [ ] **Step 3: block-aware 写入**

删除已停用画板区域，替换正文块，移动保留的流程图/表格块到 manifest 指定 Owner。每次 destructive block 操作后重新 fetch，禁止复用失效 block id。

- [ ] **Step 4: 远端全文和 outline 验收**

Run: `$docToken = (Get-Content artifacts/yilu-kuangbiao-feishu-v3-2026-08-24/publication-checkpoint.json | ConvertFrom-Json).documentToken; lark-cli docs +fetch --doc $docToken --scope full --detail full --as user`

Expected: v3 正文存在；保留资源完整；UE/竞品/UX 区域为 0；标题顺序正确；内部 ID 和独立编号目录为 0。

- [ ] **Step 5: 提交验收产物**

```bash
git add artifacts/yilu-kuangbiao-feishu-v3-2026-08-24
git commit -m "Publish and verify v3 Feishu planning document"
```
