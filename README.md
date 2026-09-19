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
