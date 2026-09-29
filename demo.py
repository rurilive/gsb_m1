"""mutexly 现状演示。

第一段：朴素本地锁的获取、释放与持有者校验。
第二段：预留的分布式互斥演示位子（见文末注释）。
"""

from mutexly import LocalLock


def main():
    print("=== 朴素本地锁 ===")
    lock = LocalLock()
    print(f"  acquire(t1)   = {lock.acquire('t1')}")
    print(f"  acquire(t2)   = {lock.acquire('t2')}")
    print(f"  holder()      = {lock.holder()}")
    print(f"  release(t2)   = {lock.release('t2')}")
    print(f"  release(t1)   = {lock.release('t1')}")
    print(f"  is_locked()   = {lock.is_locked()}")

    # TODO(分布式互斥改造): Lamport 面包店互斥实现后，在这里加一段演示：
    # 建三个进程，配一个可注入的确定调度队列，让三者交替进入临界区，
    # 观察广播请求、按时间戳回授权、释放出队与最终全部跑完的授权次序。


if __name__ == "__main__":
    main()
