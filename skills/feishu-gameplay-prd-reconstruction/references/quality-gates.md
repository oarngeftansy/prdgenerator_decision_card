# 主策质量门禁

出现以下任一问题，必须退回并自动修复后再展示：

- 玩法概述是截图描述、对象说明或交互步骤，没有玩家目标、基础操作、核心循环和胜败条件。
- 系统目录来自固定模板，而不是当前证据。
- 多个可区分的武器、奖励、敌人、事件或状态被概括成“存在多种内容”，没有输出逐项内容清单。
- 参数化机制没有结构化字段表。
- 公式写成“待确认”，而不是省略并转入具体的“需要策划决定”。
- 公式缺少变量、计算顺序、修正、取整、边界或来源。
- 随机机制缺少候选池、资格、权重、顺序、放回方式、重复、空结果、上限或重置规则。
- 生命周期未区分正常退出、重新进入、强退重登、局内结束、关卡结算和活动结束。
- 正常正文出现 `scope`、`component`、`entry`、`result`、`unknown`、`pending_details` 等内部英文或乱码。
- 证据图片与章节文字描述的是不同画面或不同机制。
- 截图被静默遗漏或合并，没有标记为独立页面、补充画面或重复画面。
- 互斥选项可以同时选中；保存、审核和跳转没有明确反馈。
- 已确认的策划结论在重新生成时被覆盖。
- 已有证据支持的失败、上限、无效状态、重置或退出重进被遗漏。
- 图解只有文字或公式，没有表达空间、状态、分支、职责或多步算法关系。
- 出现无依据的精确数值、概率、配置表名或字段名。
- 同一机制的规则、参数、公式和验收彼此矛盾。
- 参考样例有证据支持的内容角色（内容清单、配置字段、执行顺序、公式、异常边界、生命周期）在当前草稿中被无故省略。
- 所有章节机械复用相同标题和模块，造成层级很多但每层只有一两句话；薄规则应直接写入所属小节，复杂机制才继续拆层。
- 同一业务事实被正文、对象状态、运行职责和表现要求重复发布，没有形成单一事实主载体或 `carrierRefs`。
- 样例储备被写成当前项目结论，或未按 `applicable / decision_required / not_applicable` 证明机制是否适用。
- 属性只出现在万能参数表中，没有对象归属的属性正文。
- 正文仍出现固定标题、连续机械句式或“当前项目应补齐/对齐样例”等审核报告语气；禁止审核报告口吻进入交付文档。
- 截图或图解脱离所属规则，或用同一张图证明多个不同验收结论。

最终证明必须包括：自动化测试、生成质量校验、实际交互检查和一次新的主策审阅。

可复用规则还必须通过跨项目盲测，至少覆盖三种无共同实体模板的玩法。正式自检采用分阶段验收：先提交用例与验收方法，用户确认后再执行；每个用例使用唯一匹配截图，截图需完整覆盖判断所需区域。
# Editorial separation gate

- Gameplay prose contains triggers, state transitions, calculations, results, constraints, lifecycle, and only the semantic feedback needed for implementation or testing.
- Planning-board content contains position, color, attachment, animation, component layout, and other pure presentation instructions.
- One sentence does not mix a gameplay transition with unrelated visual layout. Shared feedback is split into semantic result in prose and visual realization in the board.
- Every non-trivial chapter is readable by planner, programmer, and tester: design intent, implementation behavior, and observable boundary are recoverable without reading audit metadata.
- Compare against planner-written references by information role. Supported missing roles block delivery; unsupported sample-only roles remain non-applicable; excess filler or visual narration is removed.
- Every published sentence adds an action, state, data/configuration rule, branch/boundary, test condition, or ambiguity resolution. Generic common knowledge fails the gate.

## Handwritten planner delta gate

- Read handwritten references chapter by chapter; title, keyword, and word-count comparison is insufficient.
- Compare 机制拆分、规则深度、属性解释、配置映射、执行顺序、异常边界、生命周期、图文关系、语言与排布 separately.
- Every finding records 手写文档有、当前输出有、缺失、多余或错误、改善方式 and cites a source 章节或行号 plus the current model field or preview paragraph.
- A sample's 项目专属事实 is reserve knowledge, not current-project truth. Without current evidence or an accepted planner decision, remove it or route it to a decision card.
- Any supported missing responsibility without a remediation carrier, any unsupported copied fact, or any stale/unbound diagram blocks delivery.
