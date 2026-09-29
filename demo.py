"""logstore 现状演示。

第一段：往字典式 KV 里写几个键、覆盖与删除，看取值与键序。
第二段：预留的落段、合并与范围扫描演示位子（见文末注释）。
"""

from logstore import KVStore


def main():
    print("=== 字典式 KV（现有能力） ===")
    store = KVStore()
    print("  put a=1   -> 覆盖", store.put("a", 1))
    print("  put b=2   -> 覆盖", store.put("b", 2))
    print("  put a=10  -> 覆盖", store.put("a", 10))
    print("  get a     ->", store.get("a"))
    print("  delete b  -> 曾存在", store.delete("b"))
    print("  keys      ->", store.keys())
    print("  len       ->", len(store))

    # TODO(落段与读取): 内存表落段能力实现后，在这里加一段演示：
    # 把内存表大小设成很小的值，连续写入若干键触发多次冻结落段，
    # 打印每个段的序号与内容，再 get 一个被后写覆盖的键，看读到的是最新版本。

    # TODO(合并与范围扫描): 段合并与范围扫描实现后，在这里加一段演示：
    # 手动触发一次合并，看合并前后段数下降、被覆盖的旧版本被回收，
    # 再 scan 一段键区间，打印该区间内每个键的最新值，确认结果有序且不含墓碑。


if __name__ == "__main__":
    main()