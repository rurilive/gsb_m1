"""replug 现状演示：造一个小插件目录，装载后打几条请求看状态变化。

热重载的演示位子见文末注释。
"""

import os
import tempfile

from replug import PluginRuntime, ReplugError

GREETER = '''\
PLUGIN = {"name": "greeter", "version": "1.0.0", "description": "打招呼"}


def init(ctx):
    return {"hits": 0}


def handle(state, request):
    state["hits"] += 1
    return "你好 %s，第 %d 次" % (request["who"], state["hits"])
'''

COUNTER = '''\
PLUGIN = {"name": "counter", "version": "2.1.0"}


def init(ctx):
    return {"total": 0}


def handle(state, request):
    state["total"] += request.get("delta", 1)
    return state["total"]
'''


def write_plugin(directory, name, source):
    path = os.path.join(directory, name + ".py")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(source)
    return path


def main():
    workdir = tempfile.mkdtemp(prefix="replug-demo-")
    write_plugin(workdir, "greeter", GREETER)
    write_plugin(workdir, "counter", COUNTER)

    runtime = PluginRuntime(workdir)
    print("=== 装载 ===")
    print("  load_all -> %s" % runtime.load_all())
    for name in runtime.plugin_names():
        manifest = runtime.manifest_of(name)
        print("  %-8s 版本 %s  描述 %r" % (name, manifest.version,
                                           manifest.description))

    print("=== 派发请求 ===")
    for who in ("运维", "值班", "运维"):
        print("  %s" % runtime.request("greeter", {"who": who}))
    print("  counter +5 -> %s" % runtime.request("counter", {"delta": 5}))
    print("  counter +2 -> %s" % runtime.request("counter", {"delta": 2}))
    print("  两个插件的活状态: greeter=%s counter=%s"
          % (runtime.state_of("greeter"), runtime.state_of("counter")))

    print("=== 换文件后整体重装 ===")
    write_plugin(workdir, "greeter", GREETER.replace("1.0.0", "1.1.0"))
    runtime.load_all()
    print("  greeter 现在是 %s，状态回到 %s"
          % (runtime.version_of("greeter"), runtime.state_of("greeter")))

    print("=== 坏插件不让宿主停摆 ===")
    write_plugin(workdir, "greeter", "PLUGIN = {}\n")
    try:
        runtime.load_all()
    except ReplugError as exc:
        print("  重装失败: %s" % exc)
    print("  宿主照常服务: %s" % runtime.request("greeter", {"who": "值班"}))

    # TODO(热重载): 热重载落地后，在这里补最后一段演示：
    # 往目录里写一份新版 greeter，reload 之后看版本切换与状态迁移；
    # 再写一份坏的新版，看重载失败后旧版本继续服务、状态没被动过。


if __name__ == "__main__":
    main()
