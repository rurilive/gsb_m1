"""网关配置分层的日常样子（线上演示脚本，输出格式别动）。"""

import json
import os
import tempfile

from cfgstack import (
    MissingKeyError,
    load_config,
    merge_profiles,
    required_subset,
)

DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 80, "timeout": 30},
    "log": {"level": "info"},
}

FILE_LAYER = {
    "server": {"port": 8080},
    "features": {"beta": True},
}


def main():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "gateway.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(FILE_LAYER, f)
        os.environ["GW__server__timeout"] = "15"
        os.environ["GW__log__level"] = "debug"
        stack = load_config(DEFAULTS, path, "GW")
        print("layers:", stack.layers())
        print("merged:", json.dumps(stack.as_dict(), sort_keys=True))
        print("port:", stack.require_int("server.port"))
        print("timeout:", stack.require_int("server.timeout"))
        print("beta:", stack.get("features.beta"))
        print("profiles:", merge_profiles({"retry": {"n": 3}}, {"retry": {"backoff": 2}}))
        print("subset:", required_subset(stack.as_dict().get("log", {}), ["level"], source="log"))
        try:
            stack.require("db.url")
        except MissingKeyError as e:
            print("err:", e)
        try:
            stack.require_int("features.beta")
        except ValueError as e:
            print("err:", e)
        del os.environ["GW__server__timeout"]
        del os.environ["GW__log__level"]


main()
