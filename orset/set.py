"""基础集合：支持 add、remove 与 contains。

当前能力仅限于单个副本本地使用：集合把元素写成普通集合，
remove 直接把元素从集合里删掉，contains 即成员判断。
没有副本标识、没有版本信息，因此两个副本各自本地改动后，
无法把状态带回去合并，删除与并发新增之间的先后也无从谈起。
纯标准库，无外部依赖。
"""


class SetError(Exception):
    """集合使用不当或状态非法时抛出的异常。"""


class ORSet:
    """仅支持本地增删查的基础集合。

    内部用一个普通集合保存元素。add 加入一个元素并返回自身；
    remove 删除一个元素，元素本就不在时按无操作处理，同样返回自身；
    contains 返回元素是否在集合里。elements 给出当前元素集合的副本。
    """

    def __init__(self, elements=None):
        self._items = set(elements or ())

    def add(self, element):
        """加入元素，返回自身。"""
        if not isinstance(element, str):
            raise SetError("element must be a string")
        self._items.add(element)
        return self

    def remove(self, element):
        """删除元素，元素不在时按无操作处理，返回自身。"""
        if not isinstance(element, str):
            raise SetError("element must be a string")
        self._items.discard(element)
        return self

    def contains(self, element):
        """元素是否在集合里。"""
        return element in self._items

    def elements(self):
        """当前元素的集合副本，改动它不影响集合自身。"""
        return set(self._items)

    def __len__(self):
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __repr__(self):
        return f"ORSet({sorted(self._items)!r})"