"""schedx 现状演示。

第一段：建一张小图，看朴素扫描给出的就绪任务、拓扑序与串行总时长。
第二段：预留的迭代演示位子（见文末注释）。
"""

from schedx.plan import FlatSched


def main():
    print("=== 朴素扫描（现有能力） ===")
    s = FlatSched()
    s.add_task("fetch", 3)
    s.add_task("parse", 2, ["fetch"])
    s.add_task("render", 5, ["parse"])
    s.add_task("publish", 1, ["render"])
    print("  tasks()           -> %s" % s.tasks())
    print("  ready_tasks(set())-> %s" % s.ready_tasks(set()))
    print("  ready_tasks(fetch) -> %s" % s.ready_tasks({"fetch"}))
    print("  topo_order()      -> %s" % s.topo_order())
    print("  total_time_serial -> %s" % s.total_time_serial())
    print("  can_finish(publish, {fetch,parse}) -> %s"
          % s.can_finish("publish", {"fetch", "parse"}))

    # TODO: 第二段演示（实现后补）


if __name__ == "__main__":
    main()
