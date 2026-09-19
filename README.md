# buildplan

依赖图执行器：把声明式构建清单解析成依赖图，拓扑分层后按层模拟执行，
输出执行报告。单进程内嵌，纯标准库，无外部依赖。

## 模块结构

    buildplan/
    ├── errors.py     异常族：ManifestError（清单语法/重复）、GraphError（未知依赖/成环）
    ├── manifest.py   清单解析：Target / Manifest / parse_manifest
    ├── graph.py      拓扑分层：layer_targets
    └── executor.py   执行与报告：Executor / StageVisitor / Report / Record

## 清单格式

行式文本，每行一个目标：`名字: 依赖1 依赖2`。`#` 起始为注释，空行忽略，
无依赖的目标冒号后留空。声明顺序全程保留，层内顺序与报告顺序都按它来。
语法错误、目标名非法、重复定义抛 `ManifestError`。

## 分层规则

无依赖的目标在第 1 层，其余目标层号 = 最大依赖层号 + 1。
同一层内没有依赖关系，是一个并行组，层间必须串行。
未知依赖、依赖成环（含自依赖）抛 `GraphError`。

## 模拟执行语义

- 不运行任何真实命令；每个目标的模拟耗时由名字哈希决定（1..9ms，
  `target_cost_ms`，同名恒同值）
- 命中 `Executor(fail_targets=...)` 的目标 -> `failed`，仍消耗模拟耗时
- 依赖里出现 `failed` 或 `skip` 的目标 -> `skip`，耗时计 0，级联向下传播

## 报告格式

    report: 7 target(s) in 5 layer(s) | ok=4 skip=2 failed=1 | total 31ms
    [1/5] base
      ok     base   4ms
    [2/5] core net
      ok     core   9ms
      ...

首行是汇总统计；每个并行组一行 `[层号/总层数] 成员...`；目标行两空格
缩进、状态列左对齐 7 宽、耗时右对齐 3 宽。以 tests/test_buildplan.py
的 golden 文本为准。

## 阶段钩子

`StageVisitor` 定义执行过程的四个回调：`on_layer_start` /
`on_target_finish` / `on_layer_finish` / `on_run_finish`，把实例传给
`Executor.run(manifest, visitor=...)` 即可同步观察推进过程。
报告数据由执行器直接汇总，不经过钩子。

## 运行

    python3 demo.py                          # 演示：失败级联的执行报告
    python3 -m unittest discover -s tests -v # 行为基线测试

## 扩展说明

`Executor.plan(manifest, visitor=None)` 只产出执行计划，不执行任何模拟动作：
与 `run` 共用同一套分层推进与阶段钩子，分层结果（层序、层内并行组成员与
顺序）完全一致；但不读 `fail_targets`，没有失败注入与级联跳过，全部目标
状态固定为 `plan`，耗时恒 0。返回值是 `PlanReport`（`Report` 子类），文本
与 `run` 同源渲染：首行换成 `plan: N target(s) in M layer(s)`（不带计数与
总耗时），目标行状态列固定 `plan`、无耗时列，层标题行与报告一致。清单校验
与 `run` 相同，语法/重复/未知依赖/成环抛同样的异常。
