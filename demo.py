"""pluginhost 演示：注册三个插件跑 dispatch，再演示注销与错误隔离。"""

from pluginhost import Plugin, PluginHost
from pluginhost.plugins import AuditTrail, CollapseRepeats, FooterSigner, KeywordMask


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

    print("=== 注销：mask 下线后不再参与，也不触发任何回调 ===")
    mask = host.plugin("mask")
    host.unregister(mask)
    host.unregister(mask)  # 幂等：重复注销静默返回
    show(host, "我的密码是 123456")

    print("=== 错误隔离：抛错的插件只跳过自己，错误进 diagnostics ===")

    class FlakyDedup(CollapseRepeats):
        name = "flaky-dedup"

        def on_message(self, message):
            if "密码" in message:
                raise RuntimeError("dedup 存储抖动")
            return super().on_message(message)

    class ErrorLog(Plugin):
        name = "errlog"
        priority = 95

        def on_error(self, diag):
            print("on_error 收到: %r" % (diag,))

    host.register(FlakyDedup())
    host.register(ErrorLog())
    show(host, "我的密码是 123456")  # flaky-dedup 抛错，signer 照常签名
    print("diagnostics:", host.diagnostics)


if __name__ == "__main__":
    main()
