# changelogd

对象的字段变更日志：按版本号记下每次改动，随时重建历史快照。纯标准库，无外部依赖、无真实 IO。

## 现状

`changelogd/changelog.py` 提供 `ChangeLog`：

- `ChangeLog(clock=time.time)`：clock 为注入时钟，每条变更的 ts 取自它
- `append(obj, field, value, version)`：追加一条变更，返回该记录（`obj` / `field` / `value` / `version` / `ts`）
- `history(obj)`：该对象的全部变更，按 append 顺序，返回新列表
- `at(obj, version)`：重建快照——每个字段取 append 顺序里最后一条 `version` 不超过给定值的变更
- `objects()`：出现过的对象名，按首次 append 顺序

目前只有一条时间线，`version` 由调用方给，本包不校验它是否单调。

## 问题

两份改动从同一版本分叉之后没法合回一条线：同字段撞车没有消解口径，合并完也说不清每条变更打哪儿来。

## 目标

见任务描述。约束：

- 现有方法行为与 `tests/test_changelog.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                            # 单线变更与快照重建演示
python3 -m unittest discover -s tests -v   # 行为基线测试
```

## 实现说明

- `fork(base_version, name)` 复制分叉点记录成新 `ChangeLog`，分支各自 `append`，版本号独立；`DELETE` 哨兵表示删字段，`at` 折叠到它时该字段不出现在快照。
- `merge_branches(base_version, branches, resolver, clock)` 取各分支分叉后每字段最后一次改动，逐条重放回本日志；每条合并记录的 `version` 与 `ts` 都取自注入的合并时钟。
- 默认消解策略 `delete-wins`：删除先赢，否则取 `branches` 列出顺序靠前者；另有 `first-wins` / `latest-wins` / `latest-ts-wins`。
- 自定义消解函数签名 `resolver(field, candidates, base_version)`，`candidates` 是按分支顺序排好的 `Candidate(branch, change)`，返回中选 `Candidate`（也可返回分支名或下标）。
- 记账口径：输家先落线、赢家后落，`history` 两边都留痕、`at` 只剩赢家口径；`MergeReport.merged` 每条含来源分支与 `winner/loser` 状态，`provenance(obj)` 与 `history` 对齐，`conflicts` 记每个冲突字段的各方与输赢，`losers()` 单列输家。
