"""confy 演示：内置单层读取 + 三层配置（默认 < JSON 文件 < 环境变量）。"""

import json
import os
import tempfile

from confy import (
    ConfigErrors,
    MissingKeyError,
    describe,
    get,
    load,
    missing,
    require,
    section,
    source_of,
    typed,
    validate,
)


def main():
    print("=== 内置配置（单层 dict） ===")
    for line in describe():
        print(f"  {line}")

    print("\n=== section 分支读取 ===")
    print(f"  db -> {section('db')}")

    print("\n=== get 带默认 / require 必配 ===")
    print(f"  get('log.level') = {get('log.level')!r}")
    print(f"  get('nope.enabled', default=True) = {get('nope.enabled', True)!r}")
    try:
        require("mail.smtp.password")
    except MissingKeyError as exc:
        print(f"  require missing -> MissingKeyError: {exc.args[0]}")
    absent = missing(["log.level", "mail.smtp.password"])
    print(f"  missing(['log.level', 'mail.smtp.password']) = {absent}")

    # 分层配置演示：默认层被 JSON 文件覆盖、再被 CONFY_ 环境变量覆盖。
    print("\n=== 分层：默认 < JSON 文件 < 环境变量 ===")
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"db": {"pool_size": 32}, "cache": {"ttl_seconds": 30}}, fh)
    environ = {
        "CONFY_DB__POOL_SIZE": "64",      # 环境变量再盖一层
        "CONFY_CACHE__ENABLED": "false",  # 推断为 bool
        "CONFY_HTTP__REQUEST_TIMEOUT": "9.5",  # 推断为 float
        "PATH": "/usr/bin",               # 非 CONFY_ 前缀，忽略
    }
    load([path], environ)
    for key in ("db.pool_size", "cache.ttl_seconds", "cache.enabled",
                "http.request_timeout", "app.name"):
        print(f"  {key} = {get(key)!r}  <- {source_of(key)}")
    os.unlink(path)

    print("\n=== typed 严格访问 ===")
    print(f"  typed('db.pool_size', int) = {typed('db.pool_size', int)}")
    try:
        typed("app.debug", int)  # bool 不算 int
    except TypeError as exc:
        print(f"  typed('app.debug', int) -> TypeError: {exc}")

    print("\n=== validate 汇总校验 ===")
    try:
        validate({"db.pool_size": int, "app.name": int, "mail.smtp.password": str})
    except ConfigErrors as exc:
        print(f"  {exc}")
        for err in exc.errors:
            print(f"    key={err.key} reason={err.reason} layer={err.layer}")


if __name__ == "__main__":
    main()
