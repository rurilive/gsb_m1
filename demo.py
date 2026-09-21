"""演示：起一个调度器，注册两个任务跑 6 秒。用于本地快速确认模块可用。"""
import time
from datetime import timedelta

from scheduler import IntervalTrigger, Scheduler, SystemClock


def beat():
    print(f"[beat]  心跳  {time.strftime('%H:%M:%S')}")


def slow():
    time.sleep(0.5)
    print(f"[slow]  慢任务完成  {time.strftime('%H:%M:%S')}")


def main():
    sched = Scheduler(SystemClock(), worker_count=1, tick=0.2, misfire_grace=2.0)
    sched.add("heartbeat", IntervalTrigger(timedelta(seconds=2)), beat)
    sched.add("slow-job", IntervalTrigger(timedelta(seconds=3)), slow)
    sched.start()
    time.sleep(6)
    sched.stop()
    print("演示结束")


if __name__ == "__main__":
    main()
