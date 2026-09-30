# linearsolve

一个纯标准库的线性方程组求解工具箱，无外部依赖。做数值实验的脚本、批处理的
报表、教学演示里的方程演算，都会碰到一串系数与常数项要求解的情形，linearsolve
就是干这件事的那一层。

## 现状

- `linearsolve/solve.py`：一个线性方程组写成增广矩阵，每行是各变量系数再跟
  一个常数项，整数或分数精确表示，不做浮点近似。
- `naive_solve_matrix` 与 `naive_solve`：最朴素的主元消元，按列从左到右、
  行从上到下逐格消，不选主元，只有主元恰好为零才到下面换一行；消成上三角后
  只看最后一行判无解，最后一行之外看不出别的。
- `naive_is_consistent`：消元后逐行看系数全零而常数项非零即矛盾。
- `naive_rank`：消元后数非零行的个数，不含常数项列。
- `naive_free_symbols`：按全零列即自由来挑，只在没换列时看着对。
- `naive_determinant`：按定义对第一行展开、递归累加带符号余子式，阶乘量级。
- `parse_matrix_text`、`build_augmented`：在矩阵文本与增广矩阵之间来回。
- `linearsolve/LinearSolveError`：所有可诊断错误的基类，带 `message`、
  `position` 与 `data`。

## 问题

现在消元不选主元，主元落空才被动换行，遇到数值接近或主元为零的情形口径飘；
判定无解、无穷多解只看最后一行，给不出自由变量；求秩与求行列式各走各的路，
互相印不上；行列式还停在递归展开的阶乘量级，阶数一高就跑不动。

## 目标

见任务描述。

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
