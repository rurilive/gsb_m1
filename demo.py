"""nttx 现状演示。

第一段：用朴素实现做多项式乘法与求值，看基线能力。
第二段：预留的迭代演示位子（见文末注释）。
"""

from nttx.poly import Polynomial, convolve, deduce_length


def main():
    print("=== 朴素多项式乘法（现有能力） ===")
    a = Polynomial([1, 2, 3])
    b = Polynomial([4, 5])
    product = a * b
    print(f"  a              -> {a.coefficients}")
    print(f"  b              -> {b.coefficients}")
    print(f"  a * b          -> {product.coefficients}")
    print(f"  degree(a*b)    -> {product.degree()}")
    print(f"  convolve       -> {convolve([1, 2, 3], [4, 5])}")
    print(f"  deduce_length  -> {deduce_length([1, 2, 3], [4, 5])}")

    print("=== 朴素求值与取模 ===")
    print(f"  a(2)           -> {a.evaluate(2)}")
    print(f"  a(-1)          -> {a.evaluate(-1)}")
    print(f"  a mod 7        -> {a.scalar_mod(7).coefficients}")

    # TODO: 第二段演示（实现后补）
    # 说明：数论变换实现后，在这里补一段演示——在合适素数模下把两个多项式
    # 变换到点值、点值相乘再逆变换，与上面的朴素卷积逐步断言逐项相同；
    # 再顺带演示多项式求逆与除法取商余，展示近线性路径的用法。


if __name__ == "__main__":
    main()
