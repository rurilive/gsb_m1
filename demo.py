"""confy 现状演示：内置单层配置的读取。

第二段注释：分层配置实现后的演示位子。
"""

from confy import MissingKeyError, describe, get, missing, require, section


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

    # TODO(分层配置): load() 实现后，在这里补第二段演示：
    # 默认层被 JSON 文件覆盖、再被 CONFY_ 环境变量覆盖，
    # 并演示 typed 严格访问、validate 的 ConfigErrors 汇总、
    # source_of 的来源追溯。


if __name__ == "__main__":
    main()
