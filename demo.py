"""sortlab 现状演示。

第一段：用 NaiveSorter 排一小串整数。
第二段：预留的基数排序与稳定性演示位子（见文末注释）。
"""

from sortlab.sorter import NaiveSorter


def main():
    print("=== 朴素排序 ===")
    sorter = NaiveSorter()
    data = [31, 5, 17, 2, 5, -8]
    print(f"  输入 = {data}")
    print(f"  输出 = {sorter.sort(data)}")

    # TODO(基数与外部排序改造): 基数排序实现后，在这里加一段演示：
    # 逐位分桶的稳定基数排序、负数与大整数、自定义键、超内存块的分块归并，
    # 并与朴素排序对拍。


if __name__ == "__main__":
    main()
