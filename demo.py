"""FlatXorMax 现状演示。

第一段: 加入元素, 看线性扫描下的异或最大 / 最小与两数异或最大。
第二段: 预留的零一字典树演示位子 (见文末注释)。
"""

from bittrie import FlatXorMax


def main():
    print("=== 朴素异或集合 (线性扫描) ===")
    s = FlatXorMax()
    for v in (3, 10, 5, 25, 2, 8):
        s.add(v)

    print(f"  len             = {len(s)}")
    print(f"  values          = {s.values()}")
    print(f"  query_max_xor(8)= {s.query_max_xor(8)}")
    print(f"  query_min_xor(8)= {s.query_min_xor(8)}")
    print(f"  max_pair_xor    = {s.max_pair_xor()}")

    s.remove(10)
    print(f"  after remove(10), len = {len(s)}")
    print(f"  query_max_xor(8)= {s.query_max_xor(8)}")

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
