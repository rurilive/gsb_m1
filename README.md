# centledger

按权重把一笔总额分摊到若干账户并记账的小库，纯标准库，无外部依赖。
账本以整数分记账，金额在进出账本的边界上统一折到分。

## 记账口径

财务给的口径，代码要跟这个对齐：

- 分摊以分为最小单位，逐户四舍五入到分；
- 摊不平的分位尾差归给权重最大的那个账户，权重并列时取账户名
  排序靠前的；负总额（退款、对冲批）的尾差方向跟着总额走；
- 权重非负，可以是 0，0 权重的账户不参与这一笔；
- 权重全为零时整笔挂账，各户都是零，不落给任何账户；
- 不足一分的请求折成零，各户记一笔零留痕，请求照常计数；
- 同一批次号重放，必须返回与第一次完全一样的结果，对账系统
  拿批次文本逐字节比对。

## 模块

`centledger/money.py` 负责金额与分的换算：

- `to_cents(amount)`：金额换整数分，四舍五入到分
- `from_cents(cents)`：整数分换回 Decimal 金额
- `format_cents(cents)`：整数分格式化成 `12.34` 这样的定点字符串

`centledger/allocate.py` 是纯分摊逻辑：

- `allocate(total, weights)`：把 `total` 按权重摊开，返回 `Allocation`；
  `Allocation.shares` 是逐户份额，`Allocation.residual` 是按分舍入后
  剩下的尾差，由调用方按上面的口径结算
- 权重和金额都接受 int、str、Decimal；负权重、非法数值报 `MoneyError`

`centledger/ledger.py` 是账本：

- `Ledger.apply_batch(batch_id, requests)`：把一批 `BatchRequest`
  记进账本，返回 `BatchResult`，里面有本批各户的分摊合计和记完这批
  之后的余额
- `BatchResult.render()`：批次结果的文本表示，对账系统按它逐字节比对
- `Ledger.balance(account)` / `Ledger.balances()`：查余额
- `Ledger.reconcile()`：把请求总额与账户余额合起来对一遍，返回
  `ReconcileReport`，`ok` 为假表示账面对不上

## 实现

账本内部一律用整数分记账，分摊时把权重按小数位对齐放大成整数，
份额用整数乘除算出，不逐户套 Decimal 高精度运算；Decimal 金额只
在进出账本的边界上换算，十几位的大金额也不丢精度。批次号幂等：
同一个 batch_id 重放直接返回首次的结果，余额和请求数不重复累计，
输出文本逐字节相同。整批先校验再记账，非法权重整批不落账。

## 运行

```bash
python3 demo.py                          # 现状演示
python3 demo.py perf                     # 大批量分摊压测
python3 -m unittest discover -s tests -v # 行为基线测试
```
