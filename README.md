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

两份改动从同一版本分叉后能合回一条线：同字段撞车有消解口径，合并完说得清每条变更的来路。

## 实现说明

1. 分叉即各自的 `ChangeLog`；`merge(obj, base_version, branches, base=, version=, clock=, resolver=)` 返回 `MergeResult`，分支为 `(名字, ChangeLog)`，只放分叉后的改动。
2. 默认策略 `"first-wins"` 按分支传入顺序前者赢；内置 `"latest-ts"` 取最后改动 ts 晚的；两种内置策略删除恒赢。
3. 自定义消解函数签名 `resolver(candidates, base_value)`，候选为 `Candidate(branch, value, change)`，返回赢家 `Candidate`、分支名或候选下标。
4. `DELETE` 表示删除字段：`snapshot()` 不再含已删字段（含“删后又被改”的坑），但删除动作和中间冲突留在 `entries()`/`history()` 里。
5. 每条合并记录带 `sources`（同值并列两边都记），赢家写入快照；`conflicts()` 按字段记账，`losers()` 平铺所有被消解的输家候选。
6. 合并版本默认 `base_version + 1`，合并 ts 取自注入时钟，每个字段调用一次；单线 `ChangeLog` 与基线测试原样不动。

## 运行

```bash
python3 demo.py                            # 单线变更与快照重建演示
python3 -m unittest discover -s tests -v   # 全部测试（基线 + 合并）
```
