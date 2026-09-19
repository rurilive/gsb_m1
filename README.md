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
python3 -m unittest discover
```

## Known Issues

以下四个线上现象均已修复，根因与修复方式如下（回归测试见 `tests/test_diffkit.py`）：

- **重复行文件补丁落点偏移一行**：`apply_patch` 直接用 hunk 头的 1 基行号 `old_start` 当 0 基下标（`patch.py`），落点整体偏一行；文件全是重复行时上下文校验恰好也能通过，错误被掩盖。修复：统一由 `_offset()` 做 1 基行号到 0 基下标的换算（`count=0` 的纯插入 hunk 按惯例取插入点）。
- **应用补丁后文件尾换行丢失**：`apply_patch`/`unapply_patch` 用 `"\n".join()` 重建文本，永远不会产生结尾换行；同时 `parse_patch` 直接丢弃 `\ No newline at end of file` 标记，换行状态完全丢失。修复：解析时保留 `\` 标记行，应用时按标记确定结尾换行；`diff.py` 侧把标记内联到对应行之后（末行换行状态不同的相等行按 `-`/`+` 对输出，避免标记归属歧义），内容相同仅换行不同的情形单独成 hunk，末尾换行差异落在所有 hunk 之外时补一个独立 hunk。
- **补丁基线与目标不一致时静默产出缺改动的文件**：`apply_patch` 上下文校验失败时 `continue` 跳过该 hunk，不报错。修复：校验失败立即抛 `ValueError`，带 hunk 头信息，发布流程可感知失败。
- **反向应用（回滚）直接失败**：`unapply_patch` 错用 old 侧坐标（`old_start`/`old_count`）去匹配 new 侧内容，纯新增 hunk（`old_count=0`）下期望内容永远对不上而报错。修复：反向应用改用 new 侧坐标与 new 侧行数做匹配，替换内容取 old 侧。
