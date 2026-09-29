# mergekit

一个纯标准库的序列比较与三方合并工具，无外部依赖。两段序列并行演进时常
要回答两个问题：它们差在哪，以及拿一个共同基线能不能把两侧的改动合成一
份。mergekit 就是干这两件事的那一层。

## 现状

- `mergekit/diff.py`：`diff(left, right)`，逐位比较两段序列，返回变化记录
  组成的列表。下标对齐后逐位比较，相等记 `EQUAL`，不等记 `REPLACE`；较长
  的尾巴按方向记 `REMOVE` 或 `ADD`。`changes_only` 滤掉相等项，
  `has_changes` 判断有无改动。入参只接受 `list` 与 `tuple`，其余类型抛
  `DiffError`。
- `mergekit/merge.py`：`merge(base, ours, theirs)`，两侧都与基线一致时返回
  基线，只有一侧改动时返回改动的那一侧，两侧都与基线不同则抛
  `MergeConflictError`。`same_list` 判断两段序列逐一相等，
  `changed_indices` 列出取值不同的下标。
- `mergekit/errors.py`：`MergeKitError` 基类，`DiffError` 已启用；
  `InputLimitError` / `MergeConflictError` / `StrategyError` 为后续扩展预留。

## 问题

diff 只按下标对齐，前面插一个元素就会把后面全体报成替换，看不出真正的
增删位置，因为它不算编辑脚本。merge 只会照抄单侧改动，两侧在同一处各改
各的就只能报冲突，既不逐块合并也不保留双方内容，更没有可插拔的冲突解决
策略。另外逐位的比较对输入长度不设上限，长序列上没有防线。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```
