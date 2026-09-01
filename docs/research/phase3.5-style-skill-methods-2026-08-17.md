# Phase 3.5：风格蒸馏方法研究

日期：2026-08-17  
范围：仅研究 `snowmays/style-alchemy` 与 `larashero3-dotcom/writing-dna-skill/SKILL.md` 的方法。本文不安装、不调用两项 Skill，不提取作者身份风格，也不提供任何可用于补齐策划规则或 Gap 的内容。

## 结论

Planning Style Distillation 应采用“证据与规则分离”的双产物模式：先归一化人工策划文档样本，再分别提取可量化的表层语言特征和经人工标注的文档结构特征；人读报告保留证据、例外和判断过程，机器读 profile 只保存允许进入 Renderer 或 Style Linter 的确定性约束。

可借鉴 `style-alchemy` 的核心不是仿写能力，而是把模糊风格拆成维度、以样本例证支撑特征、再固化为可编辑和可校验的 YAML 资产。其公开说明明确区分人读报告与机器读 profile，并强调 YAML 的人工可修、可评估属性。[Style Alchemy README](https://github.com/snowmays/style-alchemy)

可借鉴 `writing-dna-skill` 的范围严格限定为 L1 与 L2：L1 用统计提取词频、句长、标点和格式，L2 用人工标注归纳结构骨架；其自身将 L1–L2 定义为“怎么写”，而 L3–L5 是选题、素材策略和认知框架等“怎么想”。本项目明确排除 L3–L5。[Writing DNA SKILL.md](https://github.com/larashero3-dotcom/writing-dna-skill/blob/main/SKILL.md)

## 来源方法与可迁移部分

### Style Alchemy：结构化 style profile

来源方法：

1. 原始样本先归一化，保留原文并形成统一格式。
2. 把“风格”拆成独立分析维度，每个维度由样本原文例证支持。
3. 同时输出人读分析报告和机器读 `style_profile.yaml`。
4. 将标题、节奏、语言、动词等可量化特征写入标准 schema。
5. profile 可人工修订，并可用于后续风格匹配度检查或 lint。

证据：仓库说明的流程包括“归一化样本 → 场景识别 → 分维分析 → 报告与 YAML 双产物”，并说明 profile 用于人机分离、人工修订和评估。[Style Alchemy README](https://github.com/snowmays/style-alchemy)

对 PlanningStyleSpec 的迁移：

- 把分析维度换成执行策划专属维度：标题、层级、bullet 密度、句长、主语、语义句型、数值与配置写法、逻辑/表现分段、正文/表格选择、主定义/引用、动词和禁用语言。
- 每项特征记录 `evidence`、`sample_scope`、`confidence`、`renderer_permission` 和 `lint_rule`，不能只写抽象形容词。
- Markdown 负责解释证据、适用条件和例外；YAML 只承载确定性、可执行的规则。
- 原始样本只作为研究证据，不进入运行时生成链路。

不迁移：

- “按某作者写作”的身份仿写目标。
- 情绪词、口头禅、个人修辞和内容创作公式。
- profile 融合后自由生成新内容。
- 从风格例证反推项目规则、字段、数值或章节。

### Writing DNA：仅 L1 表层语言与 L2 文档结构

L1 的来源方法是脚本统计，包括高频词、平均句长、短句/长句占比、段落平均句数、标点和小标题长度；L2 则要求逐篇人工标注结构骨架，再按文档类型归纳可复用模板。[Writing DNA SKILL.md](https://github.com/larashero3-dotcom/writing-dna-skill/blob/main/SKILL.md)

对 PlanningStyleSpec 的迁移：

| 层次 | 可提取特征 | 推荐方法 | 输出用途 |
|---|---|---|---|
| L1 | 标题长度、句长、bullet 密度、主语显式率、条件/状态句式、常用执行动词、禁用 AI/meta 词、标点和公式格式 | 确定性统计 + 人工抽检 | profile 阈值、Renderer 受控句式、Style Linter |
| L2 | 对象/系统→稳定规则类别层级、Logic/Presentation 分段、正文/表格选择、规则主定义/引用、章节内分组 | 逐章人工标注 + 跨样本归纳 | DocumentAssembler 组织策略、章节布局 lint |

L1/L2 的采用原则：

- 统计值必须附样本范围与分布，不能把单一文档的偶然写法固化成强制规则。
- 结构模板按 `chapterType` 或内容形态分类，不建立一套适用于所有章节的模板。
- 可自动测量的特征与需人工判断的特征分开记录。
- 只有跨多个合格人工样本稳定出现、且不携带项目语义的特征，才允许进入 Renderer。

明确排除：

- L3 选题逻辑：发布时机、切入角度、话题优先级。
- L4 素材策略：作者偏好的信息源、权威对象和论证策略。
- L5 认知框架：世界观、价值判断、核心假设和命题。
- 由上述层次导出的内容选择、观点、因果解释和缺失项答案。

这些内容即使能在样本中归纳，也不得写入 `planning_style_profile.yaml`，不得供 Renderer、GapAnalyzer 或 DocumentAssembler 读取。

## 建议的蒸馏流程

1. 冻结并登记语料：记录文档来源、版本、文档类型及是否为人工执行稿；原文只读。
2. 去项目化归一：仅统一编码和可解析结构，不替换专有词，不重写句子。
3. L1 统计：计算标题、句长、bullet、主语、句型、动词、标点、数值/配置表达以及禁用词命中。
4. L2 标注：人工标注章节树、段落职责、Logic/Presentation 边界、正文/表格选择及主定义/引用。
5. 特征证据化：每项候选特征保存出处、样本数、反例和置信度。
6. 去内容化审查：删除项目名称、字段、编号、数值、专属机制和任何可用于回答 Gap 的语义。
7. 权限分级：标记为 `renderer_allowed`、`linter_only` 或 `forbidden`。
8. 双产物输出：Markdown 提供完整证据链；YAML 提供版本化、可验证的确定性约束。
9. 盲测：换用完全不同类型游戏，确认风格规则仍成立且不会生成原样本的系统、对象或规则。

## 建议的 profile 证据字段

```yaml
feature:
  id: sentence.condition_when_then
  layer: L1
  description: 条件先行，随后表达执行行为
  sample_scope:
    document_count: 0
    occurrence_count: 0
  evidence:
    - source_id: anonymized-document-id
      location: anonymized-section-path
      excerpt_hash: sha256-placeholder
  counterexamples: []
  confidence: pending
  permission: renderer_allowed
  deterministic_constraint: true
  content_free: true
  lint:
    rule_id: pending
    severity: pending
```

本文只给出字段设计，不填写未经实际语料统计的数量和阈值。

## Renderer 允许与禁止边界

允许进入 Renderer 的只有表达与组织规则，例如：

- 经验证的受控句型变体及其适用语义模式。
- 标题长度和稳定概念命名约束。
- 一条 bullet 承载一个主要职责的密度约束。
- 数值、公式、配置引用的格式规则。
- Logic 与 Presentation 的分段规则。
- 已确定的正文/表格选择条件。
- 主定义章节完整表达、其他章节只引用的组织规则。
- 内容无关的执行动词白名单和 AI/meta 语言禁用表。

禁止进入生成链路：

- 样本文档中的具体句子、字段、编号、数值、对象和机制。
- GVE16 或其他项目的章节清单直接复制。
- 作者的观点、世界观、选题逻辑和素材偏好。
- 任何能关闭 Gap、补全 Rule 或增加未审核事实的信息。
- “常见游戏通常如此”一类经验性答案。
- 原文例证全文或可识别的高重合表达；例证只留在研究报告，运行时 profile 使用抽象规则。

## 对 Phase 4 的直接启示

- Renderer 不是“写得像”，而是根据 Rule 语义选择有限且稳定的句型。
- Style profile 不提供内容，只约束已审核内容的呈现。
- DocumentAssembler 可读取 L2 组织规则，但不能据此新增章节或 Slot。
- Style Linter 可以评估标题、句长、密度、禁用词、分段与引用规范，但不能参与事实判断。
- 若某项风格特征证据不足，应留在报告中并标为 `pending`，不应成为生成规则。

## 来源与使用声明

- [snowmays/style-alchemy](https://github.com/snowmays/style-alchemy)：仅借鉴结构化拆解、样本归一化、证据支撑、Markdown/YAML 双产物和可校验 profile 的方法。
- [larashero3-dotcom/writing-dna-skill/SKILL.md](https://github.com/larashero3-dotcom/writing-dna-skill/blob/main/SKILL.md)：仅借鉴 L1 表层统计与 L2 人工结构标注。L3–L5 明确排除；L6 也不作为本阶段方法来源。

本研究笔记是方法参考，不是对两个 Skill 的安装、运行或衍生产物，也不构成针对任何作者的仿写规范。
