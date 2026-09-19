# orderflow

订单中心的状态机：下单 → 支付 → 发货 → 签收，侧支支持取消/退款/归档。结算、履约、售后三条业务线共用。纯标准库，无外部依赖。

## 对外 API（不可变更）

- `Order(order_id)`：`order_id`、`state()`、`allowed_events()`、`can(event)`、`is_final()`、`trail()`
- 事件方法：`pay(amount)` / `ship(carrier)` / `deliver(receiver)` / `cancel()` / `refund()` / `close()`
- `InvalidTransitionError`：非法转移与守卫不过

状态集合：created / paid / shipped / delivered / cancelled / refunded / closed。合法转移以 `tests/test_orderflow.py` 为准（含守卫与异常文案的逐字口径）。`pay` 只收正整数金额，`ship`/`deliver` 需要非空参数，守卫不过的文案是 `event '<evt>' blocked: <原因>`，事件失败时状态与轨迹原样不动。`can()` 对未知事件名抛 ValueError。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 结构说明

- 转移表 `_TRANSITIONS`：按「源状态 → 事件 → _Transition(目标状态, 守卫, 副作用)」组织，合法组合即表中有的键。
- 守卫是挂在表项上的普通函数，签名 `(order, *args)`，不过就抛错（文案口径不变）；副作用函数负责写 `amount`/`carrier`/`receiver`。
- 所有事件统一走 `Order._fire()`：查表 → 守卫 → 副作用 → 落状态 → 记 trail；`can()`/`allowed_events()` 只查表、不跑守卫。
- 加新事件（如换货、部分退款）：在 `_TRANSITIONS` 相应源状态下加一行表项，需要校验就写个守卫函数挂上，再加个调 `_fire("新事件", ...)` 的事件方法即可。
