# confy

服务进程的配置读取包，纯标准库，无外部依赖。

## 现状

内置默认配置是一份扁平 dict（`confy/store.py`），键用点号分层（`db.pool_size`）。
`confy/api.py` 提供读取入口（均读三层合并视图）：

- `get(key, default=None)` 读叶子值；缺失返回 default，分支键视同缺失
- `require(key)` 读必配叶子值；缺失抛 `MissingKeyError`（KeyError 子类）
- `section(prefix)` 分支键下的子树副本（去掉前缀）；叶子或未知键抛 `MissingKeyError`
- `describe()` 逐行 `key = value (type)` 的配置清单
- `leaf_keys()` / `is_branch(key)` 键空间辅助

## 分层规则

- 三层优先级：内置默认 < JSON 文件 < 环境变量，高层覆盖低层同名键
- `load(paths=None, environ=None)` 重建配置层；`environ` 缺省取 `os.environ`，可注入映射便于测试
- JSON 文件嵌套对象展平成点号键，值保留原生类型；低层已是叶子的路径整体替换
- 环境变量只认 `CONFY_` 前缀，双下划线分层：`db.pool_size` ↔ `CONFY_DB__POOL_SIZE`
- 环境变量值自动推断：`true`/`false`→bool、纯整数→int、含小数点或 e→float、其余为字符串
- `typed(key, type)` 严格读取：缺失 KeyError、类型不符 TypeError，bool 不算 int
- `validate({key: type})` 把缺失与类型不符聚成 `ConfigErrors`，每条带 key/原因/层
- `source_of(key)` 追溯来源：`defaults` / `file:路径` / `env:变量名`

## 目标

见任务描述。约束：

- `tests/test_settings.py` 是行为基线，一个字不改
- 纯标准库，Python 3.8+

## 运行

```bash
python3 demo.py                          # 单层读取 + 分层配置演示
python3 -m unittest discover -s tests -v # 行为基线 + 分层测试
```
