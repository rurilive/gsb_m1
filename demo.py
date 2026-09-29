"""routez 现状演示。

第一段：看现有朴素线性匹配的静态路由。
第二段：预留的迭代演示位子（见文末注释）。
"""

from routez import Router


def main():
    r = Router()
    r.add("/", lambda: "root")
    r.add("/users", lambda: "users")
    r.add("/users/list", lambda: "list")

    print("=== 静态路由匹配（现有能力） ===")
    print("  routes()              ->", r.routes())
    m = r.match("/users")
    print("  match('/users')       -> handler=%r params=%r" % (m.handler(), m.params))
    m = r.match("/users/list")
    print("  match('/users/list')  -> handler=%r params=%r" % (m.handler(), m.params))
    print("  match('/users/detail')->", r.match("/users/detail"))
    print("  说明：现在只有逐段全等比较，参数段与通配段都还不认识。")

    # TODO(前缀树与参数路由改造): 段树、参数段与通配段就位后，在这里补一段演示：
    # 注册形如 /users/:id 的参数路由与形如 /static/*rest 的通配路由，
    # 演示匹配 /users/42 能提取到 params 里的 id，
    # 演示通配段吃下剩余全部段并把捕获放进 params，
    # 再注册 /users/:id 与 /users/*rest 这种同前缀的多条规则，
    # 打印同一路径下按静态优于参数优于通配选出来的那条，确认优先级口径。


if __name__ == "__main__":
    main()