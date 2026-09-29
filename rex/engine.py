"""rex 当前实现：只做字面量相等判断的朴素匹配器。

真实引擎应把模式解析成语法树、再用 Thompson 构造编译成 NFA，
最后以状态集合模拟跑匹配。本文件目前只有一个占位实现：
模式本身就是要匹配的整段文本，相等才算命中，其余语法元字符
一概不认识。
"""


def match(pattern, text):
    """从开头匹配。当前实现只要求整个文本等于模式。

    命中返回 (start, end)，失败返回 None。
    """
    if text == pattern:
        return (0, len(text))
    return None


def search(pattern, text):
    """在任意起点搜索。当前实现退化为起点 0 的相等判断。"""
    return match(pattern, text)


def findall(pattern, text):
    """返回全部命中文本。当前实现至多给一个结果。"""
    if text == pattern:
        return [text]
    return []