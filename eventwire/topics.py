"""层级主题的切分与匹配。

主题是按点号分段的字符串，比如 gateway.retry.done。订阅时用模式挑主题：
普通段必须逐字相等，星号只顶一段，双星号只能放最后、能顶零段或多段。
主题本身不许出现通配段，空段和半个通配段（如 a*b）一律拒绝。
"""


def split_topic(topic):
    """把主题切成段元组，非法主题报 ValueError。"""
    if not isinstance(topic, str):
        raise TypeError(f"主题必须是 str，收到 {type(topic).__name__}")
    segments = topic.split(".")
    if topic == "" or any(segment == "" for segment in segments):
        raise ValueError(f"主题分段不能为空: {topic!r}")
    if any("*" in segment for segment in segments):
        raise ValueError(f"主题里不能出现通配段: {topic!r}")
    return tuple(segments)


def split_pattern(pattern):
    """把订阅模式切成段元组，非法模式报 ValueError。"""
    if not isinstance(pattern, str):
        raise TypeError(f"模式必须是 str，收到 {type(pattern).__name__}")
    segments = pattern.split(".")
    if pattern == "" or any(segment == "" for segment in segments):
        raise ValueError(f"模式分段不能为空: {pattern!r}")
    for index, segment in enumerate(segments):
        if segment in ("*", "**"):
            if segment == "**" and index != len(segments) - 1:
                raise ValueError(f"** 只能放在模式末尾: {pattern!r}")
            continue
        if "*" in segment:
            raise ValueError(f"通配段只能整段写 * 或 **: {pattern!r}")
    return tuple(segments)


def matches(pattern, topic):
    """模式能否覆盖主题，末尾的双星号可以一段都不顶。"""
    pattern_segments = split_pattern(pattern)
    topic_segments = split_topic(topic)
    for index, segment in enumerate(pattern_segments):
        if segment == "**":
            return True
        if index >= len(topic_segments):
            return False
        if segment != "*" and segment != topic_segments[index]:
            return False
    return len(pattern_segments) == len(topic_segments)
