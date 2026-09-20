# fairlease

按优先级发放租约的公平分配器，纯标准库，无外部依赖。

## 现状

`fairlease/lease.py` 提供 `FairLease`：

- `FairLease(clock=time.monotonic, aging=5.0)`：clock 为注入时钟，aging 为老化窗口秒数
- `request(node, prio, timeout=None)`：登记一条请求并返回凭据 ticket；prio 越小越优先，timeout 为最长等待秒数，None 表示不设上限
- `grant()`：发放一条租约并返回 node，队列里没有可发放的请求时返回 None
- `pending()`：仍会参与下一轮发放的 node 列表，按服务顺序排列
- `cancel(ticket)`：撤销尚未发放的请求，返回是否真的撤掉
- 内部记录每条请求的入队时刻与递增 ticket，ticket 顺序即先来后到

## 契约

- 优先级数字越小越优先，同优先级按先来后到。
- 一条请求从入队起等待达到 aging 即视为老化，排到所有未老化请求前面；多条老化请求之间仍按先来后到。老化保证任何请求在有限时间内被发放。
- `cancel` 之后请求立即出队，不再参与发放。
- 请求等待时间超过 timeout 即作废并移出队列；恰好等于 timeout 的那一刻仍视为有效。

## 问题

线上出现低优先级长期拿不到租约、同优先级乱序、撤单不生效、
超时边界误杀几处毛病。

## 目标

见任务描述。约束：

- 现有行为与 `tests/test_fairlease.py` 基线保持不变（基线一个字不改）
- 纯标准库

## 运行

```bash
python3 demo.py                          # 现状复现
python3 -m unittest discover -s tests -v # 行为基线测试
```

## 实现说明

每轮 `grant()`/`pending()` 都会先用注入时钟做一次清扫和排序，
规则如下。

- **老化提升（防饿死）**：请求等待时长 `now - arrival >= aging`
  即进入老化组。老化组整体排在未老化组之前，因此新到的高优先级
  请求不能插到任何老化请求前面。老化组内部不再看优先级，严格按
  ticket（入队顺序）服务。任意请求最多等待 `aging` 加上前面已老化
  请求的数量个发放轮次就一定被发放，等待上界有限，不会被持续涌入
  的高优先级饿死。未老化组维持“prio 小者优先”。
- **同级顺序**：未老化组的排序键为 `(prio, ticket)`，ticket 是
  `request()` 时分配的全局递增整数，所以同优先级严格先来后到，
  与节点名无关；老化组内同样按 ticket 先来后到。
- **撤单语义**：`cancel(ticket)` 直接把请求从队列字典中移除
  （`dict.pop`），立即出队，下一轮排序和发放都看不到它，不会再
  占用发放名额；ticket 不存在（已发放、已撤销或非法）时返回
  `False`，撤掉真实在队请求返回 `True`。
- **超时边界**：清扫条件为严格大于
  `now - arrival > timeout` 才作废；等待时长恰好等于 `timeout`
  的那一刻请求仍然有效，可以正常发放，超过（哪怕极小量）才移除。
  `timeout=None` 的请求永不过期。

回归测试见 `tests/test_fairlease_regression.py`，基线测试
`tests/test_fairlease.py` 保持不变。
