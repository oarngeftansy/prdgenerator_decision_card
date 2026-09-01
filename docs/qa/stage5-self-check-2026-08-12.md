# 阶段 5 自检报告（revision 175）

正式任务：`8312a91c89e144e6a59f81b982f14c06`

结论：内容、图文、表格、完成度和 P7/飞书同源自检通过；阶段状态仍为“等待用户验收”。当前 5 张决策卡保持未处理，完成度 91%，飞书导出被正确阻止。飞书反馈表 9 条开放记录的代码与页面回归已通过，但记录关闭仍需要用户按证据明确验收。

## 自动化基线

- Python：826/826 通过。
- JavaScript：391/391 通过。
- 真实浏览器：P1–P7 全部可进入；P7 颗粒度、语言和交付同源审计通过；浏览器错误 0。
- 正式输出：7 个玩法章节、7 张业务专用表、6 张不同流程图、15 张竞品参考卡、8 处正文局部截图、67 项内容覆盖记录。

## 用例结果与主证据

| 用例 | 自检 | 主证据 |
|---|---|---|
| S5-TC01 P7 顺序与动态目录 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc10-p7-order-and-status.png` |
| S5-TC02 玩法概述与正文落点 | 通过 | `artifacts/stage5-browser-acceptance/s5-tc01-03-04-08-p7-unified-blocked-full.png` |
| S5-TC03 内容盘点与样例颗粒度 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc01-content-coverage-full.png` |
| S5-TC04 核心对象属性正文 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc-vehicle-object-attribute-hierarchy-full.png` |
| S5-TC05 正文/命名/配置/生命周期顺序 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc12-gch-003-attribute-prose.png` |
| S5-TC06 业务专用配置表 | 通过 | `artifacts/stage5-planner-table-acceptance/s5t-tc02-weapon-tables-full.png` |
| S5-TC07 执行顺序、公式与随机闭环 | 通过（5 个无唯一答案项留在决策卡） | `artifacts/stage5-v2-browser-acceptance/s5r-tc02-prose-depth-full.png` |
| S5-TC08 流程图嵌入正文 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc04-05-six-distinct-diagrams-full.png` |
| S5-TC09 策划草图与正文同步 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc09-planning-gameplay-trace-full.png` |
| S5-TC10 竞品参考与局部截图 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc06-two-boards-full.png` |
| S5-TC11 标题、语言与去废话 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc07-sample-alignment-full.png` |
| S5-TC12 决策卡 | 通过 | `artifacts/stage5-v2-browser-acceptance/s5r-tc11-pending-decision-navigation.png` |
| S5-TC13 完成度与旧版本守卫 | 通过 | `artifacts/stage5-browser-acceptance/s5-tc01-03-08-p7-status-viewport.png` |
| S5-TC14 操作入口去重与防抖 | 通过 | `artifacts/stage5-browser-acceptance/s5-tc02-isolated-ready-viewport.png` |
| S5-TC15 飞书反馈表开放项 | 实现自检通过，等待用户逐条验收后关闭 | `artifacts/stage6-browser-acceptance/p1.png`、`p2.png`、`p3.png`、`p4.png`；开放项清单见 `docs/qa/feedback-open-items-2026-08-11.md` |
| S5-TC16 P7 与飞书同源 | 通过（只核对渲染同源，未绕过决策门禁发布） | `artifacts/stage5-v2-browser-acceptance/s5r-tc03-entity-attributes-full.png` |

## 表格补充证据

- 载具：`artifacts/stage5-planner-table-acceptance/s5t-tc01-vehicle-tables-full.png`
- 武器与词条：`artifacts/stage5-planner-table-acceptance/s5t-tc02-weapon-tables-full.png`
- 怪物与波次：`artifacts/stage5-planner-table-acceptance/s5t-tc03-monster-wave-tables-full.png`
- 三组均满足 `scrollWidth == clientWidth`，右边界位于证据画布内，未出现通用审计表头。

## 本轮自检中发现并修复

1. 删除正式载具正文中的“需由策划决策后再固化”，并让语言门禁以后自动拦截此类审核状态语言。
2. `attributeSections` 改为只对有属性的机制适用，简单机制允许空数组，避免固定模板反向污染生成。
3. 修复三个过期验收脚本：对象标题层级采集、P1–P7 断言导入、目录项选择器。
4. 正式任务从 revision 174 安全迁移到 revision 175，迁移前已自动备份。

## 用户验收入口

局域网：`http://192.168.50.67:8000/?job=8312a91c89e144e6a59f81b982f14c06&ui=final_preview`

阶段 5 只有在用户确认本报告及 TC15 开放反馈项后才标记通过。
