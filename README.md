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

以下问题已修复（防回归测试见 `tests/`，`python3 -m unittest discover -s tests` 运行）：

- **包依赖自己时不报循环依赖**：`_visit` 里对自依赖直接 `continue` 跳过（且比较的是未解析的原始声明字符串，带版本约束时连比较都不生效）。已移除该特判，自依赖统一走既有环检测，抛 `CircularDependencyError` 并带环路径。
- **同一清单两次解析顺序不一致**：`resolve` 用 `set(requests)` 迭代入口，顺序受进程 hash 随机化影响。改为按请求顺序去重遍历，输出确定。
- **未启用的可选依赖组被当作硬依赖**：`_direct_deps` 里 `enabled or optional` 在没有任何可选组被启用时退化为把全部可选依赖加进依赖图，可能引入本不该存在的环。改为仅追加显式启用的可选依赖。
- **互相打架的版本约束不报冲突**：`_select_version` 中候选版本被每个约束轮流覆盖，最终只满足最后一个约束，约束交集为空也静默通过。改为先求同时满足全部约束的版本集合，为空则抛 `ConflictError`（错误信息列出各约束来源），否则取满足约束的最高版本。
- 附带修复：入口请求了清单中不存在的包时，原来抛 `KeyError`，现在统一抛 `UnknownPackageError`。
