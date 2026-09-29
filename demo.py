"""pather 现状演示。

第一段：用 Getter 对一个嵌套字典按点号路径取值，看看现在能做什么；
第二段：预留的查询语言演示位子（通配、过滤、递归下降、切片，见文末注释）。
"""

from pather import Getter


DOC = {
    "store": {
        "book": [
            {"title": "a", "price": 10, "author": {"name": "ann"}},
            {"title": "b", "price": 30, "author": {"name": "bob"}},
        ],
        "bicycle": {"color": "red", "price": 20},
    },
    "user": {"name": "ann", "age": 30},
}


def main():
    print("=== 点号取值 ===")
    getter = Getter(DOC)
    print("  user.name -> %s" % (getter.get("user.name"),))
    print("  store.bicycle.color -> %s" % (getter.get("store.bicycle.color"),))
    print("  store.missing -> %s" % (getter.get("store.missing"),))

    # TODO(查询语言改造): 把 pather 从点号取值扩成 JSON 路径查询引擎之后，
    # 在这里补第二段演示：用一条带通配与过滤的路径，比如在 store.book 上挑出
    # price 大于 15 的书名，再叠一个递归下降收集所有 name 字段，最后对
    # store.book 取一段切片；打印命中的匹配集合，说明求值按文档顺序返回。
    # 具体语法与语义见 README 的目标一节与任务描述。


if __name__ == "__main__":
    main()
