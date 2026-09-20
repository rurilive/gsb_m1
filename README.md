# idgen

订单系统的本地 ID 生成器，纯标准库。

- `idgen/gen.py`：`IdGenerator.next_id()`，毫秒时间戳左移 16 位拼自增计数
- `tests/test_gen.py`：行为基线
- `demo.py`：连续生成演示
