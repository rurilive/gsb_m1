"""memfs 现状演示。

第一段：扁平存储的写入、追加、读取与键列表。
第二段：预留的目录树与链接演示位子（见文末注释）。
"""

from memfs import MemStore


def main():
    print("=== 基础读写 ===")
    store = MemStore()
    store.write("greeting", b"hello")
    store.append("greeting", b" world")
    print("  greeting:", store.read("greeting"))
    print("  size:", store.size("greeting"))
    store.write("alpha", b"1")
    store.write("beta", b"2")
    print("  keys:", store.keys())
    print("  条目数:", len(store))

    # TODO(目录树与链接): 目录树、路径解析、符号链接与硬链接就位后，
    # 在这里补一遍演示：mkdir 建目录，往目录里写文件，
    # 建一个符号链接指向该文件，再建一个硬链接共享同一份内容，
    # 然后把内容读回来，打印链接计数与目录列表（有序）。


if __name__ == "__main__":
    main()