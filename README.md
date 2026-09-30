# nttx

整数系数多项式的工具包，纯标准库，无外部依赖。

## 现状

`nttx/poly.py` 提供 `Polynomial` 与几个辅助函数，能力朴素但正确：

- `Polynomial(coefficients)`：低位在前存储，自动去掉高次零项，零多项式用空列表表示
- `__add__` / `__sub__` / `__mul__`：加减逐项对齐，乘法是双重循环逐项卷积，平方级
- `evaluate(x)` / `evaluate_many(points)`：逐点代入求值
- `scalar_mod(m)`：逐项对模数归一，负数按取模语义落到非负区间
- `from_roots(roots)` / `convolve(a, b)` / `deduce_length(a, b)` / `validate_points(poly, points)`：常见辅助

异常统一挂在 `nttx.poly.NttxError` 之下（也可从包根 `nttx` 导入）：
`InvalidCoefficientsError`、`InvalidModulusError`、`EmptyPolynomialError`、
`EvaluationError`。

## 问题

乘法只能做平方级的双重循环卷积，长度上千就明显变慢；求值也是逐点代入，
没有变换加速；除法取模只有逐项归一，没有多项式的逆与带余除法。

## 目标

见任务描述。约束：

- `tests/test_poly.py` 行为基线保持不变（基线一个字不改）
- 新行为另开测试文件
- 纯标准库

## 运行

```bash
python3 demo.py
python3 -m unittest discover -s tests
```

（实现后补，10 行以内）
