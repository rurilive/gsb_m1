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

以下问题已修复（防回归测试见 `tests/`，`python3 -m unittest discover -s tests -t .`）：

- **重复行文件打补丁落点偏一行**：`apply_patch` 把 hunk 头的 1-based 行号直接当 0-based 下标用（漏了 `-1`）。重复行场景下上下文校验在错位处也能通过，于是改动落到隔壁行。已修正行号换算（含 `count=0` 时行号指向前一行的惯例）。
- **打完补丁文件尾换行丢失**：应用结果用 `"\n".join(...)` 拼接，末尾换行被丢弃；同时 `parse_patch` 直接忽略 `\ No newline at end of file` 标记。现在解析器记录两侧 no-newline 标记，应用/回滚时按标记还原文件尾字节；`unified_diff` 也补上了"仅文件尾换行不同"时生成翻转 hunk 的逻辑（此前行内容相同会返回空补丁），并把 no-newline 标记放到对应 `-`/`+` 行之后而不是无条件塞在 hunk 末尾。
- **补丁基线与目标不一致时静默丢改动**：`apply_patch` 上下文不匹配时直接 `continue` 跳过 hunk，产出缺改动的文件且不报错。现在抛 `ValueError`，发布流程可在应用阶段即失败。
- **反向应用（回滚）报上下文不匹配**：`unapply_patch` 作用在已打补丁的文本上，却用 hunk 的 old 侧区间（`old_start`/`old_count`）定位和校验。已改为使用 new 侧区间定位、按 new 侧内容校验、还原 old 侧内容。
