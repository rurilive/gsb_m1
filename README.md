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

- 表驱动：`_TRANSITIONS` 是「事件 → {源状态: 目标状态}」的转移表，唯一状态字段是 `_state`，所有事件统一走 `_fire()` 查表。
- 守卫挂在 `_GUARDS`（事件 → 函数），状态检查通过后执行；参数落库的副作用挂在 `_ACTIONS`。
- `_EVENTS` 决定 `allowed_events()` 的输出顺序；六个 `_xxx` 旗标仅兼容保留，逻辑不读。
- 加事件（如「换货」「部分退款」）：在 `_EVENTS` 末尾加名字，`_TRANSITIONS` 加一行源状态映射，按需补 `_GUARDS`/`_ACTIONS`/`_FLAG_BY_EVENT` 各一条即可。
