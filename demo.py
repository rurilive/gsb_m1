"""retrykit 的线上使用样子（demo 输出格式别动）。"""

import time

from retrykit import RetryError, retry


def note(attempt, exc, wait):
    print("  retry #%d: %s" % (attempt, exc))


print("== fixed ==")
calls = []


def fetch_job():
    calls.append(1)
    if len(calls) < 3:
        raise ValueError("queue busy")
    return "job-42"


print(retry(fetch_job, attempts=5, strategy="fixed", delay=0.05, on_retry=note))
print("calls:", len(calls))

print("== expo, give up ==")


def dead_service():
    raise ValueError("db down")


try:
    retry(dead_service, attempts=3, strategy="expo", delay=0.05)
except RetryError as e:
    print("caught:", e)

print("== jitter, flaky once ==")
n = [0]


def flaky_once():
    n[0] += 1
    if n[0] == 1:
        raise TimeoutError("slow")
    return "done"


print(retry(flaky_once, attempts=4, strategy="jitter", delay=0.1))

print("== non-retryable ==")


def broken():
    raise KeyError("fatal")


try:
    retry(broken, attempts=3, strategy="fixed", delay=0.05, retry_on=(ValueError,))
except KeyError as e:
    print("propagated:", e)

print("== budget ==")


def slow_db():
    time.sleep(0.06)
    raise ValueError("db down")


try:
    retry(slow_db, attempts=5, strategy="fixed", delay=0.5, timeout=0.05)
except RetryError as e:
    print("caught:", e)
