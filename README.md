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

## 实现说明

- 合并入口 `changelogd.merge.merge(base, left, right, resolve=resolve_newest)`：三方都是 Change 序列，按 (obj, field) 对齐，返回 `MergeResult`
- 分支是否"动过"某字段，看它在该字段上的最终值与 base 是否不同；两边都没动的字段只保留 base 记录
- 默认策略 `resolve_newest`：删除优先，否则 (version, ts) 较新者胜，完全打平取 right；可换成 `resolve_left` / `resolve_right`
- 自定义消解函数签名 `resolve(field, left_change, right_change) -> Change`；返回两边之外的 Change 时按 `"resolved"` 来源单独入选
- 删除写作 `log.delete(obj, field, version)`（即 append 一个 `DELETED` 值），`at` 快照不再出现该字段，`history` 仍保留全程
- 来源记账：结果的 `changes` 是 `MergedChange(change, origin)`，origin ∈ base/left/right/resolved，change 就是原变更对象
- 冲突记账：每个冲突一条 `Conflict(obj, field, winner, losers)`，输家带来源，可经 `MergeResult.losers` 全部列出
- `MergeResult.apply_to(log)` 把合并结果按序重放进一个 ChangeLog，之后用 `at` 取最终快照

## 运行

```bash
python3 demo.py                            # 单线演示 + 多分支合并演示
python3 -m unittest discover -s tests -v   # 行为基线 + 合并测试
```
