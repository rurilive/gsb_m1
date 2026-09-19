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

    print("\n=== 分层配置：默认 < JSON 文件 < 环境变量 ===")
    overrides = {"db.pool_size": 16, "log.level": "debug", "cache.enabled": False}
    fh = tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(overrides, fh)
    fh.close()
    environ = dict(os.environ)
    environ["CONFY_DB__POOL_SIZE"] = "32"
    environ["CONFY_HTTP__REQUEST_TIMEOUT"] = "9.5"
    try:
        load(paths=[fh.name], environ=environ)
        for key in ("db.pool_size", "log.level", "http.request_timeout", "app.name"):
            print(f"  {key} = {get(key)!r}  (source: {source_of(key)})")

        print("\n=== typed 严格访问 ===")
        print(f"  typed('db.pool_size', int) = {typed('db.pool_size', int)}")
        try:
            typed("cache.enabled", int)  # bool 不算 int
        except TypeError as exc:
            print(f"  typed('cache.enabled', int) -> TypeError: {exc}")

        print("\n=== validate 汇总 ConfigErrors ===")
        try:
            validate({
                "db.pool_size": int,
                "cache.enabled": int,        # 类型不符（file 层）
                "mail.smtp.password": str,   # 缺失
            })
        except ConfigErrors as exc:
            print(f"  ConfigErrors ({len(exc)} 项):")
            for err in exc:
                print(f"    - {err}")
    finally:
        os.unlink(fh.name)
        load(paths=[], environ={})  # 复位为纯默认层


if __name__ == "__main__":
    main()
