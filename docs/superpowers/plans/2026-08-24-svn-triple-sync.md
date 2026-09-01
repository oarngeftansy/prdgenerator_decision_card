# SVN Triple Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 Git 已提交项目和离线运行依赖发布到 SVN `ai_gamedesigntool`，并建立可重复的本地 Git、GitHub、SVN 三重同步入口。

**Architecture:** 从 Git tree 构建隔离 staging package，再加入白名单运行依赖、manifest 和 hashes；SVN 只消费 staging，不读取脏工作区。同步脚本在 Git push 成功后才允许 SVN commit。

**Tech Stack:** PowerShell、Git、SVN CLI/TortoiseSVN command-line tools、SHA-256。

## Global Constraints

- 当前 SVN 403 未解除前不得执行写操作。
- 不上传凭证、`.git/.svn`、缓存、临时测试目录、RDP、部署备份或归属不明的未提交文件。
- SVN 包必须包含运行所需离线依赖、锁文件、安装和启动脚本。
- 任一质量门禁或 Git push 失败后不得继续 SVN commit。

---

### Task 1: 可复现打包器

**Files:**
- Create: `scripts/build_svn_release_package.ps1`
- Create: `config/svn-release-manifest.json`
- Test: `tests/test_svn_release_manifest.py`

**Interfaces:**
- Consumes: Git commit tree 和依赖白名单。
- Produces: staging directory、`release-manifest.json`、`sha256sums.json`。

- [ ] **Step 1: 写红测试**

```python
def test_svn_release_manifest_includes_runtime_and_excludes_secrets_and_caches():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert "runtime_packages_server" in manifest["dependencyRoots"]
    assert ".git" in manifest["excludeNames"]
    assert ".pytest_cache" in manifest["excludeNames"]
    assert any("credential" in pattern.lower() for pattern in manifest["secretPatterns"])
```

- [ ] **Step 2: 运行红测试**

Run: `python -m pytest tests/test_svn_release_manifest.py -q -p no:cacheprovider --basetemp .test-tmp/svn-package-red`

Expected: FAIL。

- [ ] **Step 3: 实现 manifest 和 PowerShell 打包器**

脚本用 `git archive HEAD` 导出提交树，把 manifest 白名单中的依赖复制到 staging，扫描禁止文件和敏感模式，再生成 SHA-256。

- [ ] **Step 4: 构建并核对 staging**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_svn_release_package.ps1 -OutputPath artifacts/svn-release-staging/ai_gamedesigntool`

Expected: 0 secret findings、0 excluded path、manifest commit 等于 HEAD。

- [ ] **Step 5: 提交**

```bash
git add scripts/build_svn_release_package.ps1 config/svn-release-manifest.json tests/test_svn_release_manifest.py
git commit -m "Add reproducible SVN release packaging"
```

### Task 2: 三重同步入口

**Files:**
- Create: `scripts/sync_git_svn.ps1`
- Create: `docs/operations/git-svn-triple-sync.md`
- Test: `tests/test_git_svn_sync_contract.py`

**Interfaces:**
- Consumes: clean committed Git state、remote branch、SVN URL/username via parameters。
- Produces: Git commit SHA、GitHub remote SHA、SVN revision、package SHA。

- [ ] **Step 1: 写脚本合同红测试**

```python
def test_sync_orders_quality_git_push_before_svn_commit_and_never_embeds_password():
    text = SCRIPT.read_text(encoding="utf-8")
    assert text.index("git push") < text.index("svn commit")
    assert "xin.cheng" not in text
    assert "-SvnPassword" not in text
    assert "Read-Host -AsSecureString" in text
```

- [ ] **Step 2: 运行红测试**

Run: `python -m pytest tests/test_git_svn_sync_contract.py -q -p no:cacheprovider --basetemp .test-tmp/svn-sync-red`

Expected: FAIL。

- [ ] **Step 3: 实现同步脚本和操作文档**

脚本参数只接受 Git remote/branch、SVN URL/username；密码使用安全提示输入，不落盘。执行状态按 JSON 输出。

- [ ] **Step 4: dry-run**

Run: `powershell -ExecutionPolicy Bypass -File scripts/sync_git_svn.ps1 -DryRun -SvnUrl https://192.168.50.30/svn/AI/ -SvnUsername xin.cheng`

Expected: 显示 tests → Git push → package → SVN update/add/delete/commit 的顺序，不执行外部写入。

- [ ] **Step 5: 提交**

```bash
git add scripts/sync_git_svn.ps1 docs/operations/git-svn-triple-sync.md tests/test_git_svn_sync_contract.py
git commit -m "Add guarded Git and SVN synchronization"
```

### Task 3: 权限恢复后的首次 SVN 发布

**Files:**
- Create: `artifacts/svn-initial-publication-2026-08-24/publication-result.json`

**Interfaces:**
- Consumes: 获得读写权限的 SVN 账号、Task 1 staging package、已推送 Git HEAD。
- Produces: `ai_gamedesigntool` URL 和 SVN revision。

- [ ] **Step 1: 只读列目录和权限验证**

Run: `svn ls https://192.168.50.30/svn/AI/ --username xin.cheng --password-from-stdin --non-interactive --trust-server-cert`

Expected: 成功列出根或 trunk；失败则停止。

- [ ] **Step 2: 确定唯一目标 URL**

存在 trunk 时使用 `https://192.168.50.30/svn/AI/trunk/ai_gamedesigntool`；否则使用 `https://192.168.50.30/svn/AI/ai_gamedesigntool`。不得同时创建两个路径。

- [ ] **Step 3: 构建最新 staging 并运行完整测试**

Run: `python -m pytest -q -p no:cacheprovider --basetemp .test-tmp/svn-release-full`

Expected: 0 failed。

- [ ] **Step 4: 初次 import 或 update/commit**

首次不存在使用 `svn import`；已存在则 checkout、同步 staging、`svn status` 审核后 commit。

- [ ] **Step 5: 回读核验并记录 revision**

Run: 从 `publication-result.json` 读取 `targetUrl`，再执行 `svn info $targetUrl` 和 `svn ls $targetUrl`。

Expected: URL、revision、HEAD commit、package SHA 与 publication result 一致。
