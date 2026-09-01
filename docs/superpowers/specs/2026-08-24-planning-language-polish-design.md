# Planning Language Polish Design

## Goal

将已冻结的 Final Delivery Candidate v2 做纯文本润色，生成 `Final Delivery Candidate v3 / Planner Review Ready`。不得修改 Rule、Intent、Slot、Owner、Gap、Evidence、Projection 或 FeedbackTrace。

## Boundary

- 输入是已经组装完成的 Final Document。
- 只允许修改 `sentence.text`、Gap `proposal` 和 Gap `question`。
- 章节、对象、机制、semantic group、句子顺序、Gap 数量和 provenance 字段保持不变。
- 润色规则必须是确定性的句法变换，不调用 LLM，不补充事实。
- 数值规则保持当前位置；只允许在首条数值示例文本前增加“数值示例：”标签。

## Rendering

新增纯函数 `polish_final_document(document) -> document`。函数深拷贝输入，然后执行：

1. 压缩“随后……刷新后……”等重复连接词；
2. 将“触发条件待确认”改为直接向策划提问；
3. 删除“确保……可以判定”等审计式尾句，但不得删除 Gap；
4. 在保持 semantic group 顺序的前提下标记数值示例；
5. 保留每个 sentence / proposal / question 的其余字段。

## Integrity Gate

v3 生成器读取 v2 的 Projection 与 FeedbackTrace，按字节复制到 v3，并记录复制前后 SHA-256。两个哈希必须分别完全一致。FeedbackTrace 必须保持 12 条 `fully_reflected`、0 partial、0 regressed；否则停止生成。

## Verification

- 单元测试验证文本改善、顺序不变、Gap 不丢失、输入不被修改；
- 生成 `v2-to-v3.diff`；
- 运行完整 Python 测试集；
- 只提交本次新建的润色模块、测试、生成脚本、设计/计划与 v3 文本产物，不混入工作区既有未提交修改。
