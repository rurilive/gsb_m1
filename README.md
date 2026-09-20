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

## 多分支合并

`changelogd/merge.py` 在不改基线的前提下支持分叉合并：

- `fork(base, name, clock=None)`：从基准日志分出一条空分支（仍是 `ChangeLog`），分支只记分叉后的改动
- `merge(obj, base, branches, base_version, resolver=None, clock=None)`：把分叉自同一版本的分支合回一条线，返回 `MergeResult`
- `MergeResult`：`log()` 取合并后的 `ChangeLog`；`history(obj)` 返回 `MergedChange`（带 `sources` 来源分支）；`origin(change)` 查单条来源；`conflicts(obj)` 取冲突账目；`losers(obj)` 列出所有被消解的输家原记录

## 实现说明

- 默认策略 `last_write_wins(field, candidates)`：墓碑优先（删了不复活），否则取候选里 ts 最大的，平手按分支名字典序。
- 消解函数签名 `(field, candidates) -> Candidate`，`candidates` 是按分支名排序的 `Candidate(branch, change)` 列表，返回其中一个（或直接返回它的 `change`）；另有 `prefer_branch(name)` 预置策略。
- 只有一条分支动过的字段直接并入；多条分支最终值相同视为一致，来源记全部命中分支，不算冲突。
- 赢家在分支上的 ts 决定并入顺序，版本号从 `base_version` 起逐条 +1，并入记录的 ts 走合并时钟（可注入）。
- `DELETE` 是墓碑值：默认口径下删除赢得冲突，输家改动仍按来源写进历史、随后落墓碑，所以快照没有该字段、历史看得到中间发生过什么。
- 来源记账：并入的每条都带 `sources`，基准原文来源为空；冲突用 `Conflict(field, winner, losers)` 记账，赢家和输家都是 `Candidate`，复盘可定位到分支与原记录。

## 运行

```bash
python3 demo.py                            # 单线变更与快照重建演示
python3 -m unittest discover -s tests -v   # 基线与合并行为测试
```
