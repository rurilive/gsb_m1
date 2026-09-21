# rbacflow

网关侧的授权策略库，纯标准库，无外部依赖。策略数据是本地状态，判定不碰网络。

## 现状

- `rbacflow/store.py`：`PolicyStore` 持有策略库的全部状态。`declare(role)`
  登记角色（重复声明是空操作），`grant(role, action)` / `revoke(role, action)`
  加减授予，`granted(role)` 给角色直接拿到的动作（授予序），`allowed(role, action)`
  做精确查表，`rules()` 展开全部授予，`roles()` 与 `stats()` 看账
- `rbacflow/engine.py`：`Engine(store)`。`check(role, action)` 判一个动作，
  `check_many(role, actions)` 批量判，`permitted(role)` 列角色直接拿到的动作
- `rbacflow/actions.py`：动作名的规范与拆段。动作名是冒号分隔的小写段，
  比如 `docs:read`、`pkg:sub:list`
- `rbacflow/errors.py`：`PolicyError` / `UnknownRole` / `InvalidAction` /
  `DuplicateGrant` / `NotGranted`

当前口径：角色能做某动作，当且仅当它自己直接拿到过这个名字的动作。
store 里一改，下一次判定立刻看到新结果；几个 Engine 共用一个 store 时看到的是一份账。

## 用法

```python
from rbacflow import Engine, PolicyStore

store = PolicyStore()
store.declare("editor")
store.grant("editor", "docs:write")

engine = Engine(store)
engine.check("editor", "docs:write")   # True
```

## 目标

见任务描述。约束：现有接口与 `tests/` 基线行为保持不变，纯标准库。

## 运行

```bash
python3 demo.py                          # 建策略、判定、改授权
python3 -m unittest discover -s tests    # 既有行为基线测试
```
