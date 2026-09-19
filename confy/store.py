"""confy 的内置配置：一份启动时写死的扁平 dict。

键用点号分层（如 "db.pool_size"），叶子值类型任意。
"""

CONFIG = {
    "app.name": "orders",
    "app.debug": False,
    "app.tags": ["core", "web"],
    "db.host": "127.0.0.1",
    "db.port": 5432,
    "db.pool_size": 8,
    "db.options": {"ssl": False, "timeout": 3.5},
    "log.level": "info",
    "log.file": "/var/log/orders.log",
    "worker.concurrency": 4,
    "worker.queues": ["default", "mail"],
    "http.request_timeout": 5.5,
    "http.max_redirects": 5,
    "cache.ttl_seconds": 120,
    "cache.enabled": True,
    "report.retention_days": 30,
    "report.rows_per_page": 100,
}


def is_branch(key):
    """key 是否是其它键的分支前缀（"db" 之于 "db.port"）。"""
    prefix = key + "."
    return any(k.startswith(prefix) for k in CONFIG)


def leaf_keys():
    """全部叶子键，按定义顺序。"""
    return [k for k in CONFIG if not is_branch(k)]


def child_keys(prefix):
    """prefix 分支下的直接子键名（不带前缀），按定义顺序去重。

    例如 child_keys("app") -> ["name", "debug", "tags"]；
    未知前缀返回空列表。
    """
    stem = prefix + "."
    seen = []
    for k in CONFIG:
        if k.startswith(stem):
            child = k[len(stem):].split(".")[0]
            if child not in seen:
                seen.append(child)
    return seen
