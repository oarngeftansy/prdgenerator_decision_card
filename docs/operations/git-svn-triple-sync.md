# Git / GitHub / SVN 三重同步

## 目标

每次发布严格按“全量测试 → Git push → 远端 SHA 校验 → 从 Git HEAD 构建离线包 → SVN 只读校验 → SVN 提交”的顺序执行。SVN 永远不直接打包当前脏工作区。

## 首次准备

- 安装带 `svn.exe` 的 Apache Subversion 命令行客户端；TortoiseSVN 图形程序不能替代本流程的非交互门禁。
- 确认 SVN 账号对 `https://192.168.50.30/svn/AI/` 至少有读取权限，并对目标目录有创建/提交权限。
- 不在脚本、Git、SVN 或日志中保存密码；执行时由安全输入框临时读取。

## 预演

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_git_svn.ps1 `
  -DryRun `
  -SvnUrl https://192.168.50.30/svn/AI/ `
  -SvnUsername <username>
```

## 正式同步

```powershell
powershell -ExecutionPolicy Bypass -File scripts/sync_git_svn.ps1 `
  -SvnUrl https://192.168.50.30/svn/AI/ `
  -SvnUsername <username>
```

根目录存在 `trunk/` 时，首次目标为 `https://192.168.50.30/svn/AI/trunk/ai_gamedesigntool`；否则目标为 `https://192.168.50.30/svn/AI/ai_gamedesigntool`。脚本不会同时创建两个目录，也不会覆盖已存在的目标。

## 包内容

发布包由 `git archive HEAD` 和 `config/svn-release-manifest.json` 中的依赖白名单组成，包含生产 Python 依赖与测试依赖。`.git`、`.svn`、缓存、临时目录、凭证文件、部署备份和未提交文件不会进入 SVN。
