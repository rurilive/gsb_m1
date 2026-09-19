# diffkit

发布系统内嵌的补丁工具：unified diff 生成、应用、反向应用（回滚）。纯标准库，无外部依赖。

## 模块

- `diffkit/diff.py`：`unified_diff(old, new, fromfile, tofile, context=3)`，标准 hunk 头，含 `\ No newline at end of file` 标记
- `diffkit/patch.py`：`parse_patch` / `apply_patch(text, patch)` / `unapply_patch(text, patch)`

## 运行

```bash
python3 demo.py
```

## Known Issues

以下问题均已修复，防回归测试见 `tests/`（`python3 -m unittest discover -s tests`）。

- **重复行文件打补丁落点偏一行（已修复）**
  根因：`apply_patch` 把 hunk 头里的 1 基行号 `old_start` 直接当 0 基下标用，
  少减了 1。重复行场景下移一位后上下文恰好仍能匹配，于是改动落到隔壁行。
  修复：统一经 `_hunk_pos` 换算（`count == 0` 时按惯例指向前一行）。
- **打完补丁文件尾换行丢失，sha 对不上（已修复）**
  根因：应用/回滚时用 `"\n".join()` 重建文本，恒不补结尾换行；`parse_patch`
  又直接丢弃 `\ No newline at end of file` 标记，补丁里的文件尾信息全丢。
  此外 `unified_diff` 把标记统一追加在 hunk 末尾而非跟在对应行之后，且
  "仅文件尾换行不同"时干脆输出空补丁。修复：解析时把标记记录到
  `Hunk.no_newline`；应用/回滚时若末尾 hunk 覆盖到文件尾，结尾换行由补丁
  决定，否则保持原文件的结尾状态；diff 侧改用 `splitlines(keepends=True)`
  逐行发射，标记紧跟其所属行，换行差异自然体现为最后一行的 replace。
- **补丁基线与目标不一致时静默产出缺改动的文件（已修复）**
  根因：`apply_patch` 上下文不匹配时直接 `continue` 跳过该 hunk，不报错。
  修复：与 `unapply_patch` 一致，不匹配即抛 `ValueError`，且在任何 hunk
  失配时整体失败，不返回部分应用的结果。
- **反向应用（回滚）直接报失败（已修复）**
  根因：`unapply_patch` 用旧侧区间定位：匹配切片长度用了 `old_count`、
  推进游标也用了 `old_count`，而回滚时目标文件是"新"版本，应使用
  `new_start`/`new_count`。新旧两侧行数不一致的 hunk 必然匹配失败。
  修复：回滚一律按新侧区间定位、校验和推进。

注：因 `apply_patch` 现在对基线漂移会抛 `ValueError`，`demo.py` 场景 3
相应改为捕获并打印该异常（演示的四个场景与调用链路不变）。
