"""后台单任务执行：独立线程跑一段工作，可等待、可超时、可回调。"""

import threading


def run_detached(fn, *args, timeout=None):
    """在独立后台线程执行 fn(*args)，阻塞至其结束。

    正常结束返回 fn 的返回值；线程内抛的异常在调用方原样重抛；
    timeout 秒内没结束抛 TimeoutError，线程留在后台继续跑。
    """
    box = {}

    def _target():
        try:
            box["value"] = fn(*args)
        except BaseException as exc:  # 跨线程搬运，原样重抛
            box["error"] = exc

    t = threading.Thread(target=_target, name="tracectx-detached", daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        raise TimeoutError("detached task not finished in %ss" % timeout)
    if "error" in box:
        raise box["error"]
    return box["value"]


def async_call(fn, *args, on_done=None, on_error=None):
    """fire-and-forget：起线程后立刻返回线程句柄。

    成功时在后台线程调用 on_done(result)，失败时调用 on_error(exc)；
    两个回调都缺省时，结果与异常静默丢弃。
    """

    def _target():
        try:
            value = fn(*args)
        except Exception as exc:
            if on_error is not None:
                on_error(exc)
            return
        if on_done is not None:
            on_done(value)

    t = threading.Thread(target=_target, name="tracectx-async", daemon=True)
    t.start()
    return t
