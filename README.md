# cfgstack

服务端配置分层合并工具：defaults < file < env，网关与若干后台任务的启动路径在用。纯标准库，无外部依赖。

## 对外 API（不可变更）

- `ConfigStack`：`add_layer(name, data)` / `add_file(name, path)` / `apply_env(prefix)` / `layers()` / `as_dict()` / `get(key, default=None)` / `require(key)` / `require_int(key)` / `require_section(name)`
- `load_config(defaults, file_path, env_prefix) -> ConfigStack`：按 defaults → file → env 依次叠加的便捷入口
- `merge_dicts(a, b)` / `merge_profiles(base, *overrides)`：深合并，返回新 dict，入参不动
- `required_subset(mapping, keys, source)`：挑出必选键，缺键抛 `MissingKeyError`
- `MissingKeyError`：缺键/缺节错误

env 变量名形如 `PREFIX__section__key`（`__` 分隔路径段），值一律当字符串，`require_int` 负责转换。层按调用先后叠加，后加的覆盖先加的；同节深合并，上层只覆盖自己给出的键。缺键报错文案以 `tests/test_cfgstack.py` 为准（各 getter 措辞不同是历史口径）。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- 层是显式管道：`ConfigStack._pipeline` 按声明顺序保存 `_Layer(name, tree)`，顺序即优先级（后者赢），`layers()` 直接读管道。
- `add_layer` / `add_file` / `apply_env` 只负责把一层规范化（env 先聚成独立树）追加进管道，不再各自手拼合并。
- 合并只有一个函数 `_merge_trees(dst, src)`：dict+dict 递归、否则 src 赢，重建 src 全部 dict 节点，故与空树合并即深拷贝。
- 层入栈、env 落树、`merge_dicts`/`merge_profiles`、`as_dict()` 全部走 `_merge_trees`；管道每层原树保留，供来源审计按值回溯。
- 缺键统一抛结构化 `MissingKeyError`：携带 `key`、`source`（访问点/传入来源）、`kind`，由 `_render_missing` 按 kind 渲染。
- 渲染表 `_MISSING_MESSAGES` 保留四处历史措辞（含 `required_subset` 的 fallback），异常类型与 `str()` 文案与旧版逐字一致。
