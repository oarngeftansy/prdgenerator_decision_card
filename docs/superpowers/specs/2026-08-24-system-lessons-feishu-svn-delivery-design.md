# System Lessons、飞书交付与 SVN 三重同步设计

日期：2026-08-24  
状态：已确认设计，待实施计划  
目标分支：`codex/planner-decision-card`

## 1. 目标与边界

本轮包含三个按顺序交付的工作包：

1. 将已经通过验证的 12 条 Planner Feedback 抽象成项目无关、能被运行时消费的 System Lesson。
2. 基于 Final Delivery Candidate v3 新建飞书执行案，保留上一版玩法流程图和配置表，但不恢复已停用的 UE、竞品或 UX 画板。
3. Git 变更完成并推送后，将可复现项目包提交到 SVN 的 `ai_gamedesigntool` 子目录，并建立后续 Git、本地、SVN 三重同步流程。

本轮不改变 Evidence、Fact、Rule、Gap、FeedbackTrace 的权威关系，不把 Feedback 文本直接作为项目事实，不新增玩法专用分类器，也不将《一路狂飙》的实体、文案或 ID 写进通用 Lesson。

## 2. 方案选择

采用“声明式 Lesson Registry + 运行时策略门禁”。

不采用以下方案：

- Lesson 编译生成所有 Policy：约束强，但会引入额外构建链和派生文件，超出当前最小改造范围。
- Lesson 仅做文档或校验：无法证明运行时真正消费 Lesson，不满足用户验收条件。

## 3. System Lesson 数据模型

新增版本化声明文件：

`data/planner_knowledge/system-lessons-v1.json`

每条记录至少包含：

- `lessonId`
- `sourceFeedbackIds[]`
- `lessonType`
- `problemPattern`
- `decisionLogic`
- `applicableScope[]`
- `nonApplicableScope[]`
- `affectedPipelineStages[]`
- `policyRefs[]`
- `testRefs[]`
- `status`: `candidate | approved | deprecated`

Lesson 只保存可复用判断逻辑，不保存项目答案。`sourceFeedbackIds` 只用于来源追踪，不参与项目事实判断。

当前 12 条 Feedback 收敛为 11 条 Lesson，其中持续状态反馈与 Temporal Completeness 共享同一条 Lesson：

| System Lesson | 来源 Feedback | 通用职责 |
|---|---|---|
| Rule Intent Responsibility | PF-20260820-01 | 按规则回答的问题区分 Target、Mode、Trigger、Interval、Range、Damage |
| Evidence-bounded Lifecycle Closure | PF-20260820-02 | 检查生命周期阶段，但只恢复证据支持的 Rule；Closure Required 与 Final Required 分离 |
| Persistent Temporal State | PF-20260820-03、PF-20260824-11 | 跨时间检查持续状态差异；视觉变化只形成 Candidate，审核后才进入权威层 |
| Evidence and Parameter Authority | PF-20260820-04 | Observed Value、Pattern、Configured Value、Formula 分层；禁止无依据跃迁 |
| Candidate Type Resolution | PF-20260820-05 | 异构候选先解析类型，不默认共享 Eligibility、Sampling、Weight 或 Limit |
| Canonical Ownership and Global Recovery | PF-20260820-06 | 一条规则一个 full definition；Closure 前先执行全局 Approved Information Recovery |
| Approved Narrative Recovery | PF-20260824-07 | 结构化 Rule 缺失不等于项目规则未知；只允许 confirmed narrative 恢复 Rule |
| Recovered Dependency Closure | PF-20260824-08 | Rule 引用的 Entity、State、Result、Mechanic 必须有定义或具体 Gap |
| Rule Publication Value | PF-20260824-09 | derived trivial/redundant clause 不进入 Final；特殊例外保留 |
| Run-specific Evidence Boundary | PF-20260824-10 | 单局观察默认是 Evidence，不自动升级为通用规则或配置 |
| Mechanic Narrative Ordering | PF-20260824-12 | Final 按机制语义和玩家执行顺序组织，不按 Rule ID、创建时间或 Evidence 顺序 |

## 4. Runtime 消费模型

新增深模块 `backend/system_lesson_registry.py`，职责仅包括：

1. 加载并校验 Lesson schema、唯一 ID、Feedback 覆盖、Policy/Test 引用。
2. 构建 `policyRef → approved lessonIds` 索引。
3. 为现有 Policy/Guard/Schema/Classifier 提供统一的启用判断。
4. 输出只读的 Lesson coverage 和 Feedback → Lesson → Policy → Test 映射。

现有声明式策略增加 `lessonRefs[]`。运行时策略只有同时满足以下条件才可执行：

- Policy 本身匹配当前输入；
- 至少一条关联 Lesson 为 `approved`；
- 当前 pipeline stage 位于 Lesson 的 `affectedPipelineStages`；
- 当前使用场景不属于 `nonApplicableScope`。

禁止 Python 按 `lessonId`、游戏品类、实体名称或《一路狂飙》文本编写玩法分支。Python 仅实现通用 Registry、阶段匹配和策略解析。

## 5. Pipeline 接入点

| Lesson 能力 | 现有运行时入口 | 接入方式 |
|---|---|---|
| Intent Responsibility | `rule_intelligence_pipeline`、approved narrative intent correction | 读取带 `lessonRefs` 的 intent/correction policy |
| Lifecycle Closure | chapter schema、gap analyzer、mechanic reconstruction | Lesson 门禁 applicability、closure 与 Final requirement policy |
| Temporal State | temporal probe orchestration、requirement temporal probe | 门禁 persistent-state candidate 和 review promotion policy |
| Evidence Authority | parameter/evidence guard | 门禁 formula、probability、weight 等 guard policy |
| Candidate Type | mechanic reconstruction | 门禁 CandidateType resolution 和共享规则检查 |
| Canonical Ownership | rule intelligence、mechanic reconstruction | 门禁 owner family、duplicate full definition 和 global recovery |
| Narrative Recovery | approved information recovery | 门禁 confirmed narrative source 与 semantic recovery policy |
| Dependency Closure | recovered rule dependency closure | 门禁 dependency contracts 和 dangling-reference audit |
| Rule Value | mechanic reconstruction | 门禁 clause decomposition/value classification |
| Run-specific Boundary | publication value guard | 门禁 observed-run value suppression |
| Narrative Ordering | mechanic reconstruction / renderer | 门禁 semantic grouping、compound decomposition 和稳定排序 |

Lesson 不得创建 Rule、批准 Fact、关闭 Gap 或直接渲染正文。它只决定已经声明的通用 Policy 是否参与分析。

## 6. 测试设计

### 6.1 Lesson Registry 合同

- 拒绝重复 `lessonId`、未知状态、缺少 decision logic、悬空 policy/test 引用。
- 12 条 Feedback 必须全部映射到 approved Lesson。
- 任何 Lesson 均不得包含当前项目名称、专用实体、专用 Rule ID 或 Final 文本。

### 6.2 跨项目中性行为测试

使用与《一路狂飙》无关的中性 fixture，例如 turret/drone/arena/token/card，不引用当前项目文本或 ID。覆盖：

- 攻击方向、攻击间隔和范围分属不同 Intent。
- 已观察生命周期阶段生成 Rule，缺失阶段只生成适用 Gap。
- 多时间窗速率变化只生成 Temporal Candidate。
- Pattern 不变成 Formula，Random 不变成等概率或无放回。
- 异构 CandidateType 不默认共享规则。
- 同一 Result Rule 只有一个 full definition。
- confirmed narrative 可恢复 Rule，unreviewed narrative 不可恢复。
- recovered rule 的所有引用必须解析或形成具体 Gap。
- trivial clause 被抑制，特殊例外保留。
- 单局奖励值不变成通用奖励规则。
- 乱序选择规则稳定输出为 Trigger → Pause → Generation → Selection → Effect → Exit → Refresh → Numeric。

### 6.3 行为耦合证明

测试通过临时内存副本把对应 Lesson 改为 `candidate/deprecated` 或删除其 Policy 引用，再运行同一中性 fixture：

- 对应 Policy 必须不再激活；
- 预期行为必须改变或验证失败；
- 其他无关 Lesson 行为保持不变。

该测试证明 Lesson 是运行时输入，不是只供审计的 Markdown。

### 6.4 回归门禁

- 原 12 条 Feedback Regression Baseline 保持 `12 fully_reflected / 0 regressed`。
- Phase 1、Phase 2、Final Reconstruction、Temporal、Web/Feishu 同源测试全部保留。
- 完整测试套件必须为 0 failed。

## 7. Feedback 映射产物

生成项目无关的机器可读映射与人读报告：

```text
Feedback
→ System Lesson
→ Runtime Policy / Guard / Schema / Classification
→ Cross-project Test
→ Current verification status
```

原项目 Feedback Baseline 继续证明历史反馈闭环；System Lesson mapping 证明这些反馈已泛化为系统能力。两者不得互相替代。

## 8. 飞书新文档设计

### 8.1 内容来源

- 正文唯一来源：Final Delivery Candidate v3 / Planner Review Ready。
- 流程图和配置表来源：上一版飞书文档 `PYf7dBtgdodX9txDCpTctE7inGd` 中的玩法图解与配置表。
- 不从旧正文反推或补充新的 Confirmed Rule。

### 8.2 创建策略

先复制上一版飞书文档以保留原生图片、流程图和表格块，再在副本中重组正文：

- 删除旧的 UE流转图、UX设计、策划草图、竞品参考画板区域；
- 保留玩法相关的流程图和配置表；
- 将 v3 规则正文写入对应机制；
- 旧流程图/表格仅作为既有交付物保留，不改变 v3 Rule Authority；
- 若某旧图表与 v3 当前机制没有可解析的对应章节，则移动到“附录：既有玩法图表”，不得插入错误 Owner。

### 8.3 标题与阅读顺序

- 文档标题使用《一路狂飙》玩法策划执行案和 v3 状态。
- 开头为玩法概述和单局流程。
- 实际 H2 使用飞书原生自动编号；不额外生成“自动编号目录”。
- H3/H4 按系统 → 对象 → 机制展开。
- 图解紧邻对应机制正文，不能截断同一规则组。
- 配置表放在对应规则和数值说明之后。

### 8.4 验收

- 回读完整文档，核对标题树和正文首尾。
- 图解和表格数量不低于副本重组前确定的保留清单。
- 图解、表格与目标机制 Owner 一一映射。
- 不存在 UE、竞品或 UX 画板区域。
- 不存在独立编号目录、重复 full definition、技术 Gap 或内部 ID。

## 9. SVN 可复现交付设计

### 9.1 目标布局

最终目标目录为 SVN 仓库 `AI` 下的 `ai_gamedesigntool`。执行前通过真实 SVN 客户端确认仓库是否采用 `trunk` 布局；若存在 `trunk`，目标为：

`https://192.168.50.30/svn/AI/trunk/ai_gamedesigntool`

若仓库根本身就是工作根，则目标为：

`https://192.168.50.30/svn/AI/ai_gamedesigntool`

当前账号访问仓库返回 403；获得权限前不得猜测目录并执行写入。

### 9.2 上传边界

上传内容：

- Git 已提交源码、配置、数据、文档和正式产物；
- 前后端锁文件与安装脚本；
- 服务器运行必需的离线依赖；
- 启动、安装、升级脚本；
- 发布 manifest、依赖清单和 SHA-256 校验清单。

不上传：

- `.git`、`.svn` 元数据；
- 凭证、token、API Key 和本机用户配置；
- pytest/cache/temp、浏览器缓存和一次性 QA 目录；
- 旧部署备份、RDP 文件、无生产用途的大量调试截图；
- 未提交且归属不明的用户工作区修改。

### 9.3 三重同步

新增受测的 PowerShell 同步入口，按固定顺序执行：

1. 检查 Git 工作区与目标分支。
2. 运行质量门禁。
3. 创建 Git commit 并推送同名远端分支。
4. 从已提交 Git tree 构建 SVN staging package，加入离线运行依赖和 manifest。
5. SVN update、差异预览、add/delete、commit。
6. 输出 local commit、remote Git commit、SVN revision 和 package hash。

任一阶段失败即停止，禁止出现 Git 已失败但 SVN 继续提交，或从未提交工作区直接打包的情况。

## 10. 错误处理与安全

- 工作区已有大量历史未提交修改；所有提交必须精确暂存，禁止 `git add -A`、reset 或 stash 覆盖。
- 飞书写入失败必须复用同一个新文档副本和检查点，禁止重试时创建多个文档。
- SVN 访问或权限失败时保留 staging package 和 manifest，但不执行降级写入其他路径。
- 所有外部凭证仅用于命令认证，不写入 Git、SVN、日志、报告或 Final。
- Git 与 SVN 提交前扫描常见 token、密码、绝对用户路径和本机部署文件。

## 11. 完成标准

System Lesson：

- 12 条 Feedback 全部映射到持久化 approved Lesson；
- 每条 Lesson 至少有一个真实 runtime consumer 和跨项目测试；
- 禁用 Lesson 会改变对应运行时行为；
- 不含《一路狂飙》专用内容。

飞书：

- 新文档创建成功并返回链接；
- v3 正文、标题层级、保留图解和配置表通过远端回读；
- 不包含已停用画板。

Git/SVN：

- 完整测试 0 failed；
- 相关变更独立提交并推送 GitHub；
- SVN 可复现项目包提交成功并返回具体项目 URL 与 revision；
- 三重同步入口和运行说明进入仓库。
