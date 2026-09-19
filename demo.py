"""pluginhost 演示：注册三个插件跑 dispatch，再演示注销与错误隔离。"""

from pluginhost import Plugin, PluginHost
from pluginhost.plugins import AuditTrail, FooterSigner, KeywordMask


class Flaky(Plugin):
    """演示用故障插件：on_message 必抛错。"""

    name = "flaky"
    priority = 60

    def on_message(self, message):
        raise RuntimeError("flaky 又炸了")

    def on_error(self, diag):
        print("  [on_error]", diag)


def build_host():
    host = PluginHost()
    audit = AuditTrail()
    host.register(audit)
    host.register(KeywordMask(["密码"]))
    host.register(FooterSigner(" -- 已签名"))
    return host, audit


def show(host, message):
    print("in : %r" % message)
    out = host.dispatch("on_message", message)
    print("out: %r" % out)
    print("链上插件:", [p.name for p in host.plugins])
    print()


def main():
    host, audit = build_host()

    print("=== 正常消息：沿链签名 ===")
    show(host, "今晚发版窗口 22:00")

    print("=== 命中关键词：被中间的合规插件遮蔽 ===")
    show(host, "我的密码是 123456")
    print("audit 见过的消息:", audit.seen)

    print("=== 注销 mask：不再遮蔽，重复注销静默返回 ===")
    mask = host.plugin("mask")
    host.unregister(mask)
    host.unregister(mask)  # 幂等
    show(host, "我的密码是 123456")

    print("=== 错误隔离：flaky 抛错只跳过自己，链不断 ===")
    host.register(Flaky())
    show(host, "今晚发版窗口 22:00")
    print("diagnostics:", host.diagnostics)


if __name__ == "__main__":
    main()
