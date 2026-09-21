"""基线测试共用的样例调用链数据。

tr-1 的形状（括号里是耗时）：

    handle (100)          root, api
      auth (25)           c1, authd
        cache (13)        g1, redis
      query (40)          c2, mysql
"""


def span_record(span_id, parent_id, start_ms, end_ms, trace_id="tr-1",
                name=None, service="svc"):
    return {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_id": parent_id,
        "name": name or span_id,
        "service": service,
        "start_ms": start_ms,
        "end_ms": end_ms,
    }


TRACE = [
    span_record("root", None, 0, 100, name="handle", service="api"),
    span_record("c1", "root", 10, 35, name="auth", service="authd"),
    span_record("g1", "c1", 15, 28, name="cache", service="redis"),
    span_record("c2", "root", 50, 90, name="query", service="mysql"),
]

RENDER = "\n".join([
    "handle (100ms)",
    "  auth (25ms)",
    "    cache (13ms)",
    "  query (40ms)",
])

SNAPSHOT = "\n".join([
    "trace tr-1",
    "root api 100ms",
    "  c1 authd 25ms",
    "    g1 redis 13ms",
    "  c2 mysql 40ms",
])
