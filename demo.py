"""pluginhost 现状演示：注册三个插件，跑两轮 dispatch。"""

from pluginhost import PluginHost
from pluginhost.plugins import AuditTrail, FooterSigner, KeywordMask


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

    # TODO(宿主改造): unregister 与错误隔离实现后，在这里补一段演示：
    # 注销一个插件再 dispatch，展示它不再出现在链上；再注册一个
    # on_message 会抛错的插件，展示 dispatch 不被打断、错误被记录下来。


if __name__ == "__main__":
    main()
