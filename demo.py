"""vecpage 现状演示：版本化页表翻页错乱的几个现场。

每个场景把状态摆准再打印实际结果，带“期望”的那行是修好之后
该有的样子，跑在现在的代码上多半对不上。
"""

import threading

from vecpage import MappingConflict, PageTable


def scenario_sane_path():
    print("=== 场景零：正常路径（翻页取当前版本） ===")
    t = PageTable()
    t.map(7, 100, 1)
    t.map(7, 200, 2)
    print("  page 7 版本 1 落到 frame 100，版本 2 换到 frame 200")
    print("  walk(7, 2) ->", t.walk(7, 2))
    print("  期望：200")


def scenario_stale_walk():
    print("=== 场景一：翻页翻到了最新版本 ===")
    t = PageTable()
    t.map(7, 100, 1)
    t.map(7, 200, 2)
    print("  同样这张表，按版本 1 去翻")
    print("  walk(7, 1) ->", t.walk(7, 1))
    print("  期望：按请求版本回溯，该是 100")


def scenario_unmap_wipes_history():
    print("=== 场景二：取消映射把历史版本一起抹掉 ===")
    t = PageTable()
    t.map(9, 300, 1)
    t.map(9, 301, 2)
    t.unmap(9)
    print("  page 9 版本 1 是 frame 300，版本 2 换到 301，随后取消映射")
    print("  取消后当前版本翻页 walk(9, %d) ->" % t.version(), t.walk(9, t.version()))
    print("  回看历史版本 walk(9, 1) ->", t.walk(9, 1))
    print("  期望：取消只从新版本起生效，历史版本仍然读得到 300")


def scenario_rollback_keeps_new_value():
    print("=== 场景三：回滚之后页表项还是新值 ===")
    t = PageTable()
    t.map(3, 10, 1)
    t.map(3, 20, 2)
    t.rollback(1)
    print("  page 3 版本 1 是 frame 10，版本 2 换到 20，再回滚到版本 1")
    print("  walk(3, 1) ->", t.walk(3, 1))
    print("  期望：回到回滚点当时的帧，该是 10")


def scenario_conflicting_map():
    print("=== 场景四：同页同版本并发映射到不同帧 ===")
    t = PageTable()
    barrier = threading.Barrier(2)
    results = []
    guard = threading.Lock()

    def writer(frame):
        barrier.wait()
        try:
            t.map(5, frame, 4)
            outcome = "accepted"
        except MappingConflict:
            outcome = "conflict"
        with guard:
            results.append(outcome)

    threads = [threading.Thread(target=writer, args=(f,)) for f in (40, 41)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    accepted = results.count("accepted")
    print("  两路写入几乎同时到，都想把 page 5 在版本 4 映射到自己的帧")
    print("  被接受的写入次数 =", accepted,
          "，报冲突的次数 =", len(results) - accepted)
    print("  walk(5, 4) ->", t.walk(5, 4))
    print("  期望：恰好一路被接受、一路报冲突，同帧重复映射不算冲突")


def main():
    scenario_sane_path()
    print()
    scenario_stale_walk()
    print()
    scenario_unmap_wipes_history()
    print()
    scenario_rollback_keeps_new_value()
    print()
    scenario_conflicting_map()


if __name__ == "__main__":
    main()
