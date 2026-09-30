# simplexlp

一个纯标准库的线性规划工具箱，无外部依赖。做排产、配比、资源分配的脚本里，
总会碰到一串线性约束下要让某个线性目标最大的情形，simplexlp 就是干这件事的
那一层。

## 现状

- `simplexlp/vertex.py`：线性规划写成若干小于等于形式的约束，加上每个变量
  非负，目标取最大，整数、分数或浮点都按分数精确表示，不做浮点近似。
- `naive_optimize`：最朴素的顶点枚举，把任意两条约束相交当候选点，逐个代回
  全部约束看可不可行，可行的里面挑目标值最大的那个。
- `refine_intersection`：两条约束直接两两消元求交点，只处理两个变量，多余
  变量当零，平行或重合给 None。
- `naive_vertex_count`、`all_constraint_pairs`：露出候选对数是约束条数的两两
  组合，条数一多就是组合量级。
- `naive_is_feasible`、`naive_objective_value`、`point_value`：判断一个点在
  约束下可不可行，以及它在目标下取值多少。
- `variables_seen`、`naive_covered_variables`：列出这批约束覆盖过哪些变量。
- `simplexlp/LinearProgramError`：所有可诊断错误的基类，带 `message`、
  `position` 与 `data`。

## 问题

现在求最优只有一条路，靠枚举约束两两相交的候选点，约束条数一多，组合数就压
得跑不动；状态只会报最优或不可行，无界、多解、冗余一概看不出来；给出的顶点
也没定下多解时取哪一个的口径；候选点只在前两个变量上求交，再多变量就漏；判
可行、算目标值、列覆盖变量各是各的小函数，互相印不上。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
