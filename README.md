# exprparse

算术表达式解析与求值工具包，纯标准库，无外部依赖。

## 现状

exprparse/engine.py 提供 Expression：

- evaluate(expr, variables=None)：中缀求值，支持加减乘除、括号、一元负号，除法向下取整
- to_rpn(expr)：中缀转后缀（逆波兰）记号序列，整数原样保留，一元负号写作归类记号 u
- batch_evaluate(exprs, variables)：批量求值，给出结果列表与最大值对应的下标
- scan_count()：上一次操作累计的字符串扫描次数

内部只有一条路：把表达式当成字符串，按运算符优先级从低到高反复扫描、逐段切片、
递归重建，再从最内层括号一层层剥开。没有词法单元化的记号概念，也没有调度场或
递归下降这类一趟走完的解析路径；字符串副本随括号层数成倍增加，一大就慢，
但结果是对的。

异常基类 ExprError，派生 InvalidSyntaxError、UnbalancedParenError、
DivisionByZeroError、UnknownVariableError、EmptyExpressionError。

## 问题

求值、转后缀、批量求值全挤在这一条反复扫描的路上，每往里走一层括号都要把整段
字符串再扫一遍、再切一遍，括号一多扫描量成倍上去；表达式一长，光是为找到最外层
那个运算符就要从头扫到尾，再为下一层重扫一遍，同一段字符被反复读了不知道多少遍。
没有可对照的第二条更省的做法，拿不出任何数字说明反复扫描到底多花了多少；
变量只有整串求值一条道，也没有整除与取模之外的更细口径。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_engine.py 基线一致（基线一个字不改，必须全绿）
- 新行为另开 tests/ 下的测试文件
- 纯标准库，无第三方依赖

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

## 实现说明

（实现后补，10 行以内）
