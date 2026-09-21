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

以下问题已在当前版本修复，回归测试见 `tests/`（`python3 -m unittest discover -s tests`）：

- **自依赖不报错**：`_visit` 中 `if dep == name: continue` 把包对自己的依赖直接跳过，
  自环永远进不了环检测。已移除该分支，自依赖（含带版本约束的写法）现在会抛
  `CircularDependencyError`，错误信息带环路径。
- **两次解析顺序不一致**：`resolve` 用 `set(requests)` 去重后迭代，字符串集合的迭代
  顺序受进程 hash 种子影响，导致多入口时拓扑序不稳定、缓存失效。已改为
  `dict.fromkeys(requests)`，按请求顺序去重，同一输入输出逐项一致。
- **未启用的可选组参与解析**：`_direct_deps` 中 `deps.extend(enabled or optional)` 在
  没有可选组被启用时退化为把全部可选依赖加入依赖图，可选组内部的环（如
  `archive` ↔ `archive-sse`）被误报为循环依赖。已改为只 extend 显式启用的部分，
  未启用的可选依赖完全不参与解析。
- **版本冲突被静默吞掉**：`_select_version` 对每个约束单独扫描并用结果覆盖 `best`，
  最终版本只需满足最后一个约束（如 `json>=2.0` 与 `json<2.0` 并存时锁到 1.1.0）。
  已改为先把所有约束方的约束合并，再取同时满足全部约束的最高版本，无任何版本
  满足时抛 `ConflictError`。
