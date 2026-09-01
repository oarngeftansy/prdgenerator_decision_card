# Granularity contract

## 玩法概述

先用玩家视角回答五件事：玩家目标、基础操作、核心循环、成长或资源驱动、胜败条件。缺少其中任何一项时，概述不得通过主策检查。对象属性和页面布局不属于概述。

## Adaptive hierarchy

1. Domain/system: the actual player-facing system, such as combat, team play, map exploration, or activity scheduling.
2. Subsystem: a coherent responsibility inside that system.
3. Mechanism: one independently reviewable rule set with its own inputs, state changes, or outputs.
4. Rule cluster/variant: use only when a mechanism contains a meaningful algorithm step, state family, or result branch.

Never treat heading count as quality. GVE16 reaches weapon attributes, affix prerequisites, target counts, attenuation, combat formulas, wave rules, and settlement because the sources support them. GVE5 reaches team creation constraints, data resets, maze generation steps, field validation, distance rules, and state persistence for the same reason.

## Module selection

- Rule bullets: deterministic behavior and exceptions.
- Parameter table: three or more structured fields, configurable content, attributes, costs, probability, duration, level, range, or content catalog.
- Formula block: explicit calculation with named operands and order.
- State/branch matrix: mutually exclusive states, permissions, failure branches, lifecycle, or exit/re-entry.
- Local screenshot: layout, component grouping, visible state comparison, or a specific rule step.
- Diagram: spatial relationship, multi-step algorithm, ownership, branching, or cross-system dependency. Never diagram pure prose or a standalone formula.

## Parameter row

Record: category, field/name, planner meaning, type, unit, default value, allowed range, configuration source, delivery/growth source, rounding, evidence level, evidence reference.

配置表名和字段名只能从参考文档、配置表或策划人工确认中提取。截图与视频不得推导隐藏配置命名。数值字段还应覆盖上下限、取整、投放来源和生命周期。

## Parameter carrier selection

按机制语境选择载体，不把“参数相关”一律等同于参数表：

1. 行为正文说明机制何时发生、如何执行、产生什么结果。
2. 就近命名映射逐行写 `业务名 → 配置表/字段名`，紧邻所属机制，不集中到脱离上下文的字段字典页。
3. 只有参考文档、配置表或策划决定提供权威名称时，才能写正式表名和字段名；否则写 `建议程序字段名（待程序/配置表确认）`。
4. 配置表集中承载值、单位、范围、默认值与来源，正文不逐格复述。
5. 生命周期紧跟机制结尾，说明不可逆、保存、清除或重置范围，不混入字段表。

不得用集中字段字典总表替代行为正文、就近命名映射、配置表和生命周期的分工。

## Formula block

Record: formula name, expression, variable meanings, calculation order, additive/multiplicative modifiers, rounding, boundary handling, evidence level, source, and a substituted example only if all values are confirmed.

## Rule depth

For every applicable mechanism cover: entry condition, existing state, processing order, player choice, state change, success result, failure result, reset/persistence, repeated operation, limit/invalid condition, and exit/re-entry.

退出重进必须按证据区分正常退出、重新进入、强退重登、局内结束、关卡结算和活动结束；不得合并成一句“重置”。

## Cross-project carrier and activation contract

- 单一事实主载体：正式结论在正文、业务表、公式或图解中选择一个主载体；状态、职责和表现字段若重复同一事实，改用 `carrierRefs`，不得再次发布整句。
- Domain state uses `applicable / decision_required / not_applicable`. Only current evidence can activate a domain. Ambiguity creates a decision card; absence creates no chapter and no filler.
- `sample_reserve` is a reusable question source, never a current-project conclusion source. It may suggest what to inspect or ask, but cannot authorize a value, entity, heading, formula, or lifecycle rule.
- 对象归属的属性正文先解释业务含义、读写时机、计算或判定作用及边界；配置表只承载查配信息。不同所有者不得合并为万能属性表。
- 禁止固定标题。一个短信息簇并入最近的业务父级；只有独立有用的规则簇、表格、公式或图解保留标题。
