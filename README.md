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
