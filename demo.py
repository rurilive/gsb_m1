"""rbacflow 现状演示。

第一段：声明角色、给角色授予动作，看看库里的账。
第二段：逐条判定和批量判定。
第三段：线上改授权，下一次判定立刻看到新结果。
（继承、通配、拒绝与解释的位子在文末留好了。）
"""

from rbacflow import Engine, PolicyStore


def build_store():
    """一个小而真实的策略：文档和包两个命名空间，四个角色。"""
    store = PolicyStore()
    for role in ("viewer", "editor", "admin", "auditor"):
        store.declare(role)

    store.grant("viewer", "docs:read")
    store.grant("viewer", "pkg:list")
    store.grant("editor", "docs:read")
    store.grant("editor", "docs:write")
    store.grant("editor", "pkg:list")
    store.grant("admin", "pkg:read")
    store.grant("admin", "pkg:write")
    store.grant("auditor", "docs:read")
    return store


def main():
    store = build_store()
    engine = Engine(store)

    print("=== 策略库 ===")
    for role in store.roles():
        print("  %-8s %s" % (role, store.granted(role)))
    print("  stats:", store.stats())

    print("=== 判定 ===")
    for role, action in (("editor", "docs:write"),
                         ("editor", "pkg:read"),
                         ("admin", "pkg:read"),
                         ("viewer", "docs:write")):
        print("  %-8s %-12s -> %s" % (role, action, engine.check(role, action)))
    print("  editor 一次判三个:", engine.check_many("editor", ["docs:read", "pkg:write"]))
    print("  editor 名下的动作:", engine.permitted("editor"))

    print("=== 改授权 ===")
    store.grant("viewer", "docs:write")
    print("  给 viewer 补上 docs:write 后:", engine.check("viewer", "docs:write"))
    store.revoke("editor", "docs:write")
    print("  从 editor 撤掉 docs:write 后:", engine.check("editor", "docs:write"))
    print("  stats:", store.stats())

    # TODO(继承、通配、拒绝、解释): 这几样落地后，在这里补一段：
    # 子角色吃到父角色的授予，pkg:* 命中整片包动作，被拦下时打出依据链。


if __name__ == "__main__":
    main()
