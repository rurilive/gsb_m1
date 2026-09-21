# rbacflow

网关侧的授权策略库，纯标准库，无外部依赖。策略数据是本地状态，判定不碰网络。

## 现状

- `rbacflow/store.py`：`PolicyStore` 持有策略库的全部状态。`declare(role)`
  登记角色（重复声明是空操作），`grant(role, action)` / `revoke(role, action)`
  加减授予，`deny(role, action)` 记显式拒绝，`inherit(child, parent)` 串继承，
  `granted(role)` / `denials(role)` 给直接写入的规则，`parents(role)` /
  `children(role)` 看继承边，`allowed(role, action)` 做精确查表，
  `rules()` 展开全部授予，`roles()` 与 `stats()` 看账
- `rbacflow/engine.py`：`Engine(store)`。`check(role, action)` 判一个动作，
  `check_many(role, actions)` 批量判，`permitted(role)` 列角色直接拿到的
  动作模式，`explain(role, action)` 给结论和依据
- `rbacflow/actions.py`：动作名的规范与拆段。动作名是冒号分隔的小写段，
  比如 `docs:read`、`pkg:sub:list`；授予和拒绝支持尾部通配 `pkg:*`、`*`
- `rbacflow/errors.py`：`PolicyError` / `UnknownRole` / `InvalidAction` /
  `DuplicateGrant` / `DuplicateDeny` / `NotGranted` / `InheritanceCycle`

判定口径（查具体动作 `a`、角色 `r`）：

- 子角色吃到父角色及全部祖先的授予与拒绝；多父和菱形都支持，菱形去重，
  距离取最近
- `inherit` 成环（含自环）当场抛 `InheritanceCycle`，不留半截边
- 星号只能落在模式最后一段：`pkg:*` 盖住 `pkg:read`、`pkg:sub:list`，
  但不盖 `pkg` 本身；`*` 盖住一切
- 显式拒绝压过一切允许：任何祖先的 deny 命中就是拒绝，哪怕允许更精确、
  来自更近的角色
- 多条规则都命中时取最具体：精确压通配、长前缀压短前缀、近亲压远亲
- 都没命中时默认拒绝

store 里一改（授予、拒绝、继承边），下一次判定立刻看到新结果；几个
Engine 共用一个 store 时看到的是一份账。

## 用法

```python
from rbacflow import Engine, PolicyStore

store = PolicyStore()
store.declare("editor")
store.grant("editor", "docs:write")

engine = Engine(store)
engine.check("editor", "docs:write")   # True
```

### 继承、通配与拒绝

```python
store.declare("staff")
store.declare("contractor")
store.grant("staff", "docs:*")        # 尾部通配
store.deny("staff", "pkg:delete")     # 显式拒绝
store.inherit("contractor", "staff")  # contractor 吃到 staff 的规则

engine.check("contractor", "docs:read")    # True（继承来的通配）
engine.check("contractor", "pkg:delete")   # False（拒绝压允许）
```

`inherit` 支持多父与菱形；成环的声明当场抛错：

```python
store.inherit("a", "b")
store.inherit("b", "c")
store.inherit("c", "a")        # InheritanceCycle，不等到查询时炸栈
```

### explain 给依据

```python
expl = engine.explain("contractor", "pkg:delete")
expl.allowed          # False
expl.kind             # "deny" / "allow" / "default"
expl.pattern          # "pkg:delete" 命中的那条规则
expl.source           # "staff" 规则写在哪个角色上
expl.distance         # 1 沿继承走了几步
expl.path             # ("contractor", "staff")
expl.match            # "exact" 或 "wildcard"
expl.reason           # 可读的中文结论
bool(expl)            # 与 check 结论一致；expl.as_dict() 取全部字段
```

### 性能

继承解析按“模式 × 角色”记忆化，沿父边向上只在首次访问时走一遍（显式栈
DFS，千级深链不炸栈）；改一条规则只失效该模式的记忆，改继承边才全量
失效。五万角色、十万规则、上千级深链的库，热路径百万次判定在十秒内，
中途加规则下一次判定即生效。

## 目标

见任务描述。约束：现有接口与 `tests/` 基线行为保持不变，纯标准库。

## 运行

```bash
python3 demo.py                          # 建策略、判定、改授权、继承与解释
python3 -m unittest discover -s tests    # 全部行为基线（含随机对拍、压测）
```
