# diffkit

发布系统内嵌的补丁工具：unified diff 生成、应用、反向应用（回滚）。纯标准库，无外部依赖。

## 模块

- `diffkit/diff.py`：`unified_diff(old, new, fromfile, tofile, context=3)`，标准 hunk 头，含 `\ No newline at end of file` 标记
- `diffkit/patch.py`：`parse_patch` / `apply_patch(text, patch)` / `unapply_patch(text, patch)`

## 运行

```bash
python3 demo.py
```

## 测试

```bash
python3 -m unittest discover -s tests -t .
```

## Known Issues

以下问题已修复，回归测试见 `tests/test_diffkit.py`：

1. **重复行文件补丁落点偏移一行**：`apply_patch` 把 hunk 头里的 1 基行号直接当 0 基下标用（`pos = hunk.old_start`），上下文全是重复行时校验照样通过，改动整体偏移一行。已改为 `old_start - 1`（`old_count == 0` 的插入型 hunk 按惯例取 `old_start`）。
2. **应用补丁后文件尾换行丢失**：`apply_patch`/`unapply_patch` 用 `"\n".join()` 重组文本，直接丢掉文件尾换行；`parse_patch` 把 `\ No newline at end of file` 标记丢弃，`unified_diff` 又把标记统一追加在 hunk 末尾而非紧跟对应行，且最后一行内容相同、仅尾换行不同的差异根本生成不出补丁。现在标记紧跟对应行、解析时记录到 hunk 上，应用/回滚据此还原文件尾换行，仅尾换行不同的场景也能正常出补丁。
3. **补丁基线与目标版本不一致时静默丢改动**：`apply_patch` 在上下文校验失败时 `continue` 跳过整个 hunk，不报错，静默产出缺改动的文件。现在校验失败即抛 `ValueError`。
4. **反向应用（回滚）失败**：`unapply_patch` 拿补丁的 old 侧区间（`old_start`/`old_count`）去匹配已打补丁的文件，应该用 new 侧（`new_start`/`new_count`）。已修正为 new 侧区间，并按 `+` 行实际数量校验。
