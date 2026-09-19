# confy

服务进程的配置读取包，纯标准库，无外部依赖。

## 现状

配置是一份启动时写死的扁平 dict（`confy/store.py`），键用点号分层（`db.pool_size`）。
`confy/api.py` 提供读取入口：

- `get(key, default=None)` 读叶子值；缺失返回 default，分支键视同缺失
- `require(key)` 读必配叶子值；缺失抛 `MissingKeyError`（KeyError 子类）
- `section(prefix)` 分支键下的子树副本（去掉前缀）；叶子或未知键抛 `MissingKeyError`
- `describe()` 逐行 `key = value (type)` 的配置清单
- `leaf_keys()` / `is_branch(key)` 键空间辅助

## 目标

见任务描述。约束：

- `tests/test_settings.py` 是行为基线，一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 现状演示
python3 -m unittest discover -s tests -v # 行为基线测试
```
