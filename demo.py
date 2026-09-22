"""nestrun 现状演示：单层太平，多层派生一上就露馅。

每个场景用注入的手动时钟把时间推到指定时刻，打出实际观察到的结果，
再跟一行修复之后应该出现的样子对照。跑在现在的代码上，嵌套和取消
相关的场景多半对不上。
"""

from nestrun import ManualClock, Scheduler


class Recorder:
    """记录每次落定回调，用计数说话。"""

    def __init__(self):
        self.calls = []

    def __call__(self, task):
        self.calls.append(task)

    def count(self, task):
        return sum(1 for item in self.calls if item is task)


def make_scheduler():
    clock = ManualClock()
    return Scheduler(clock=clock), clock


def advance(scheduler, clock, seconds):
    clock.advance(seconds)
    return scheduler.run()


def show_states(tasks):
    return ", ".join("{}={}".format(task.name, task.state) for task in tasks)


def scenario_single_level():
    print("=== 场景一：单层任务，延迟开工加总预算超时 ===")
    sched, clock = make_scheduler()
    rec = Recorder()
    task = sched.submit("巡检", lambda task: None, delay=1.0, timeout=5.0, on_done=rec)
    sched.run()
    print("  t=0 状态:", task.state)
    advance(sched, clock, 1.0)
    advance(sched, clock, 30.0)
    print("  最终:", task.state, "回调", rec.count(task), "次",
          "残留定时器", sched.armed_timers(), "个")
    print("  期望: succeeded，回调 1 次，残留定时器 0 个")


def scenario_nested_success():
    print("=== 场景二：父任务等两个子任务都成功 ===")
    sched, clock = make_scheduler()
    rec = Recorder()

    def body(task):
        task.spawn("解析", lambda t: None, delay=1.0, on_done=rec)
        task.spawn("落库", lambda t: None, delay=2.0, on_done=rec)

    root = sched.submit("编排", body, on_done=rec)
    advance(sched, clock, 0.2)
    print("  子任务开工前 父任务:", root.state)
    advance(sched, clock, 3.0)
    print("  最终:", show_states([root] + root.children),
          "父任务回调", rec.count(root), "次")
    print("  期望: 父任务 succeeded，子任务都 succeeded，父任务回调 1 次")


def scenario_cancel_parent():
    print("=== 场景三：取消父任务，子任务已经派生出去了 ===")
    sched, clock = make_scheduler()
    rec = Recorder()

    def body(task):
        task.spawn("解析", lambda t: None, delay=1.0, on_done=rec)
        task.spawn("落库", lambda t: None, delay=2.0, on_done=rec)

    root = sched.submit("编排", body, on_done=rec)
    sched.run()
    advance(sched, clock, 0.5)
    root.cancel("值班取消整条编排")
    print("  取消后立刻:", show_states([root] + root.children))
    advance(sched, clock, 5.0)
    print("  等子任务的自然工期过去后:", show_states([root] + root.children))
    print("  父任务 state:", root.state, "history:", root.history)
    print("  父任务回调", rec.count(root), "次")
    print("  期望: 父子全部 cancelled，父任务 history 到 cancelled 为止，回调 1 次")


def scenario_child_failure():
    print("=== 场景四：子任务失败，父任务没人收尾 ===")
    sched, clock = make_scheduler()
    rec = Recorder()

    def boom(task):
        raise RuntimeError("磁盘满了")

    def body(task):
        task.spawn("写盘", boom, delay=1.0, on_done=rec)
        task.spawn("备份", lambda t: None, delay=2.0, on_done=rec)

    root = sched.submit("批量入库", body, on_done=rec)
    sched.run()
    advance(sched, clock, 5.0)
    print("  最终:", show_states([root] + root.children))
    print("  父任务 error:", root.error, "回调", rec.count(root), "次")
    print("  期望: 父任务 failed，error 是子任务那个 RuntimeError，回调 1 次")


def scenario_cancel_at_completion():
    print("=== 场景五：取消和任务完成落在同一时刻 ===")
    sched, clock = make_scheduler()
    rec = Recorder()
    target = sched.submit("结账", lambda task: None, delay=1.0, on_done=rec)
    sched.submit("值班叫停", lambda task: target.cancel("值班临场叫停"), delay=1.0)
    advance(sched, clock, 1.0)
    print("  结账 state:", target.state, "history:", target.history)
    print("  结账回调", rec.count(target), "次")
    print("  期望: 结账先完成，迟到的取消应当无效，state 保持 succeeded，回调 1 次")


def scenario_timeout_revocation():
    print("=== 场景六：取消过的任务，名下的定时器没有撤掉 ===")
    sched, clock = make_scheduler()
    rec = Recorder()
    task = sched.submit("对账", lambda t: None, delay=1.0, timeout=5.0, on_done=rec)
    sched.run()
    task.cancel("值班提前叫停")
    print("  取消后还挂着的定时器:", sched.armed_timers(), "个")
    advance(sched, clock, 6.0)
    print("  时间推过原来的开工点和超时点后:",
          "state", task.state,
          "回调", rec.count(task), "次",
          "取消原因", task.error.reason if task.error else None)
    print("  期望: 残留定时器 0 个，state 保持 cancelled，回调 1 次，")
    print("        取消原因一直是值班提前叫停，不该被 timeout 盖掉")


def main():
    scenario_single_level()
    print()
    scenario_nested_success()
    print()
    scenario_cancel_parent()
    print()
    scenario_child_failure()
    print()
    scenario_cancel_at_completion()
    print()
    scenario_timeout_revocation()


if __name__ == "__main__":
    main()
