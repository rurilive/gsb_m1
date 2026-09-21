# depsolve

构建系统的依赖解析模块：读入包清单，解析闭包、择优版本、按拓扑序输出构建顺序。

## 清单格式

```python
MANIFEST[name] = {
    "versions": ["1.0.0", "1.2.0"],   # 可用版本，升序列出
    "depends": ["fmt>=1.0", "json"],  # 硬依赖，可带版本约束
    "optional_depends": ["accel"],    # 可选依赖组，默认不参与解析
}
```

## 解析语义

- `resolve(manifest, requests, enabled=None)` 返回拓扑序的 `"name@version"` 列表，被依赖者在前
- 同一包被多方依赖时，必须同时满足全部版本约束，取满足约束的最高版本；没有任何版本同时满足时抛 `ConflictError`
- 可选依赖仅在 `enabled` 集合中显式启用时才进入依赖图，未启用时完全不参与解析
- 依赖图中出现环（包括包依赖自己）时抛 `CircularDependencyError`，错误信息带环路径
- 依赖了清单中不存在的包时抛 `UnknownPackageError`
- 解析是确定的：同一输入（含 `enabled`）两次解析，输出逐项一致

## 运行

```bash
python3 demo.py
```

## Known Issues
