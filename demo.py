"""matx 演示脚本。

第一段：跑一遍基线功能（live，可直接运行）。
第二段：实现后补。
"""

from matx.mat import NaiveMat, fib, mat_identity, mat_mul, mat_power


def baseline_demo():
    a = [[1, 1], [1, 0]]

    print("斐波那契 fib(10):", fib(10))
    print("矩阵乘积 A*A:", mat_mul(a, a))
    print("矩阵幂 A**5:", mat_power(a, 5))
    print("矩阵幂 A**10:", mat_power(a, 10))
    print("单位矩阵:", mat_identity(2))
    print("A**10 的左上角:", mat_power(a, 10)[0][0])

    m = NaiveMat(a)
    print("NaiveMat.power(10) 的左上角:", m.power(10).to_list()[0][0])


def main():
    print("== 第一段：基线功能 ==")
    baseline_demo()
    print("== 第二段：矩阵快速幂、斐波那契与线性递推加速 ==")
    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
