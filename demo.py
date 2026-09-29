"""merkletool 现状演示。

第一段：用朴素全量哈希给一份列表求指纹，看改动一个条目之后指纹整体变化。
第二段：预留的建树与包含证明演示位子（见文末注释）。
"""

from merkletool.hash import hash_text, naive_root


def main():
    print("=== 朴素全量哈希（现有能力） ===")
    leaves = ["alice", "bob", "carol"]
    print("  leaves        ->", leaves)
    print("  hash_text(a)  ->", hash_text("alice"))
    print("  naive_root    ->", naive_root(leaves))
    print("  改一条目后    ->", naive_root(["alice", "bob", "carol!"]))

    # TODO(建树与包含证明): 分层建树、包含证明与校验就位后，在这里加一段演示：
    # 对同一批叶子建一棵默克尔树，打印根；再给某一个叶子生成包含证明，
    # 用 verify 校验证明对该根成立；然后把该叶子改掉，展示根随之变化，
    # 以及原有的证明不再通过。


if __name__ == "__main__":
    main()
