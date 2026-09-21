"""replug 演示：装载、派请求，再用 reload 不重启热切换并接住旧状态。"""

import os
import tempfile

from replug import PluginRuntime, ReplugError

GREETER = '''\
PLUGIN = {"name": "greeter", "version": "1.0.0",
          "description": "打招呼", "requires": ["counter"]}


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

    print("=== 热重载：不重启，旧状态接着用 ===")
    hits_before = runtime.state_of("greeter")["hits"]
    write_plugin(workdir, "greeter", GREETER_MIGRATE.replace("1.0.0", "1.2.0"))
    runtime.reload("greeter")
    print("  greeter 现在是 %s，状态从旧版接住: %s"
          % (runtime.version_of("greeter"), runtime.state_of("greeter")))
    print("  hits 没归零（重载前 %d），还多了 lang 字段: %s"
          % (hits_before, runtime.request("greeter", {"who": "热重载"})))

    print("=== 坏迁移作废整次重载，旧版本继续值班 ===")
    write_plugin(workdir, "greeter", GREETER_MIGRATE_BAD)
    try:
        runtime.reload("greeter")
    except ReplugError as exc:
        print("  重载失败: %s" % exc)
    print("  还是 %s，旧状态没被改坏: %s"
          % (runtime.version_of("greeter"), runtime.state_of("greeter")))
    print("  宿主照常服务: %s" % runtime.request("greeter", {"who": "值班"}))

    print("=== 只重载被依赖者：counter 换新，greeter 报不一致 ===")
    write_plugin(workdir, "counter", COUNTER.replace("2.1.0", "2.2.0"))
    runtime.reload("counter")
    print("  counter 现在是 %s，一致性报告: %s"
          % (runtime.version_of("counter"), runtime.consistency_report()))
    write_plugin(workdir, "greeter",
                 GREETER_MIGRATE.replace("1.0.0", "1.4.0"))
    runtime.reload("greeter")
    print("  greeter 也重载后，一致性报告: %s"
          % runtime.consistency_report())


GREETER_MIGRATE = '''\
PLUGIN = {"name": "greeter", "version": "1.0.0",
          "description": "打招呼", "requires": ["counter"]}


def init(ctx):
    return {"hits": 0}


def migrate(old_state):
    old_state["lang"] = "zh"
    return old_state


def handle(state, request):
    state["hits"] += 1
    return "你好 %s，第 %d 次（%s）" % (
        request["who"], state["hits"], state.get("lang", "?"))
'''

GREETER_MIGRATE_BAD = '''\
PLUGIN = {"name": "greeter", "version": "1.3.0",
          "requires": ["counter"]}


def migrate(old_state):
    old_state["tampered"] = True
    raise RuntimeError("迁移途中炸了")


def handle(state, request):
    return "不该上岗的一版"
'''


if __name__ == "__main__":
    main()
