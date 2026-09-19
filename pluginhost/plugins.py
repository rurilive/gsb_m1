"""内置示例插件：演示钩子链的真实用法，demo 与测试共用。"""

from pluginhost.plugin import Plugin


class AuditTrail(Plugin):
    """审计：记录见过的每条消息，不改写内容。"""

    name = "audit"
    priority = 10

    def __init__(self):
        self.seen = []

    def on_message(self, message):
        self.seen.append(message)
        return None


class KeywordMask(Plugin):
    """合规：命中关键词的消息整体替换为占位符。"""

    name = "mask"
    priority = 50

    def __init__(self, keywords):
        self.keywords = list(keywords)

    def on_message(self, message):
        for word in self.keywords:
            if word in message:
                return "<masked>"
        return None


class FooterSigner(Plugin):
    """署名：给消息追加尾缀。"""

    name = "signer"
    priority = 90

    def __init__(self, suffix):
        self.suffix = suffix

    def on_message(self, message):
        return message + self.suffix


class CollapseRepeats(Plugin):
    """降噪：连续重复的消息只放行第一条，重复的返回 None 透传。"""

    name = "dedup"
    priority = 30

    def __init__(self):
        self._last = None

    def on_message(self, message):
        if message == self._last:
            return None
        self._last = message
        return message
