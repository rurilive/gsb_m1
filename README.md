# nimgar

取石子游戏的必胜判定与基本组合游戏的朴素求解器，纯标准库，无外部依赖。

## 现状

`nimgar/core.py` 提供 `NimGar`：

- `single_win(size, max_take=1, takes=None)`：单堆取石子游戏的先手赢输，递归枚举全部走法
- `single_min_takes(size, max_take=1, takes=None)`：单堆取胜的最少落子步数，同样递归枚举
- `multi_xor(heaps)`：多堆取石子游戏各堆石子数的按位异或
- `multi_winning_move(heaps)`：多堆的一条制胜走法，按固定口径取第一条把异或变成零者
- `grundy(start, move_fn)`：单个子游戏的格林数，取后继格林数集合的最小不出现整数
- `sum_win(starts, move_fns)`：多个独立子游戏之和的赢输，把状态整体拼接后递归枚举
- `wythoff_win / wythoff_move`：威索夫博弈的赢输与一条制胜走法
- `fib_win / fib_move`：斐波那契博弈的赢输与一条制胜走法

异常基类是 `Erro`，参数非法抛 `ParamErro`，规则非法抛 `RuleErro`，局面非法抛
`StateErro`。全部路径都靠递归枚举，结果确定，但堆数一多或单堆一大就指数级地
重复展开。

## 问题

没有把单堆的模数口径、多堆的异或判定、格林数异或合并、威索夫与斐波那契的
固定结论落成第二条独立做法；没有动态规划或记忆化把重复展开压下来；没有把
朴素递归展开次数与更聪明的做法访问次数并排报出，两条路之间也没有任何逐项
核验。

## 目标

见任务描述。约束：

- `tests/test_nimgar.py` 行为基线保持不变（基线一个字不改，须全绿）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

（实现后补，10 行以内）
