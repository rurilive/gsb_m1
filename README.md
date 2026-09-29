# orchestra

一个通用的流程编排器，纯标准库，无外部依赖。工单流转、数据回填、批处理
这类业务常常要把若干步骤按依赖串起来跑，orchestra 就是承载这层编排的那一层。

## 现状

- `orchestra/runner.py`：`Runner`，登记若干具名步骤，按登记顺序串行执行。
  - `add_step(name, func)`：登记步骤，`func` 接收 context 字典并返回任意值
  - `execute(context=None)`：串行执行全部步骤，返回合并后的 context
  - `steps()` / `executed` / `has_step(name)`：登记查询与已执行步骤
  - `require_step(steps, name)`：按名取步骤，缺失抛 `StepNotFound`
- `orchestra/pipeline.py`：`Pipeline`，`Runner` 的便捷薄封装。
- `orchestra/errors.py`：`OrchestraError` 基类，以及 `StepNotFound` /
  `DuplicateStep` / `InvalidStepName` / `DefinitionError` / `CycleError` /
  `StepFailed` / `StepTimeout` / `StateError` 等具体错误。

执行体返回字典时合并进 context，返回其它值则忽略；任一步骤抛异常时不吞掉，
直接向上传播，`executed` 保留此前成功的步骤。

## 问题

现有实现只能沿一条直线串行推进：步骤去向固定，没有条件分支；同一层级的
多个下游只能一个个来，没有并行汇聚；任一步失败，前面已经做过的外部动作
无人回收；步骤只有跑与没跑两种结果，没有可信的状态概念；失败后只能整条
重来，已成功的步骤会被重复执行；慢步骤没有任何上限保护；图是否成环、
有没有起点也无人校验。

## 目标

见任务描述。约束：

- `tests/test_runner.py` 行为基线保持不变（基线一个字不改）
- 新行为另开 `tests/test_orchestra.py`
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py                          # 顺序执行与失败传播演示
python3 -m unittest discover -s tests -v # 行为基线测试
```