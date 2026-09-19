"""任务执行器状态机演示（运维巡检脚本用的那套）。"""

from fsmguard import Machine

approved = {"flag": False}


def need_approval(m):
    return approved["flag"]


fsm = Machine("idle", name="job-runner")
fsm.add_transition("start", "idle", "running")
fsm.add_transition("pause", "running", "paused")
fsm.add_transition("resume", "paused", "running", guard=need_approval)
fsm.add_transition("finish", "running", "done")
fsm.add_transition("fail", "running", "failed")
fsm.on_exit("idle", lambda m: print("  [exit idle]"))
fsm.on_enter("running", lambda m: print("  [enter running]"))
fsm.on_enter("done", lambda m: print("  [enter done]"))

print("fire start  ->", fsm.fire("start"))
print("fire pause  ->", fsm.fire("pause"))
print("fire resume ->", fsm.fire("resume"), "(未批准)")
approved["flag"] = True
print("fire resume ->", fsm.fire("resume"), "(已批准)")
print("fire finish ->", fsm.fire("finish"))
print("state:", fsm.state)
print("history:", fsm.history)
