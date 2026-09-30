# parsex

上下文无关文法识别与解析的朴素工具，纯标准库，无外部依赖。

## 现状

parsex/earley.py 提供 Grammar、BacktrackParser 与 ParseNode：

- Grammar(rules)：rules 是一串 (左部, 右部) 二元组，左部为单个非空白字符，
  右部为字符串（可为空串表示空产生式），第一条规则的左部即开始符号
- Grammar.rules_for(nt)：取某非终结符的全部右部
- BacktrackParser(grammar).accepts(text)：判断 text 能否被整个导出
- .parse(text)：给出一棵解析树，不识别则为 None
- .all_parses(text) / .count_parses(text)：枚举全部解析树 / 统计解析个数
- .matches(nt, text)：非终结符在 text 中所有可导出的子串区间
- .attempts()：最近一次调用里尝试过的非终结符展开次数

内部只有回溯递归下降这一条路：对每条规则逐一尝试它右部的每一种展开，命中就
前进，失败就退回换下一种展开，没有任何记忆化与条目去重。结果算得对，规模一
大就是指数级；遇到左递归文法还会陷进无限递归，因此现有实现只能处理非左递归
文法。

## 问题

每尝试一种展开都要从头重新推导，同一条目在树的不同分支里被反复重算，长输入
下代价指数爆炸；没有条目集合与去重，同名同位置的条目被重复处理；左递归文法
（如 E -> E+T）根本进不去，必须事先改写文法才能用。

## 目标

见任务描述。约束：

- 现有行为与 tests/test_earley.py 基线一致（基线一个字不改）
- 纯标准库，Python 3.10+

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 实现说明

（实现后补，10 行以内）
