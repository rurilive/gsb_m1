"""朴素前缀集合: 一切查询都退化成一个字符串列表上的线性扫描。

这是改造前的基线实现。内部只保存一份字符串列表, 插入是追加, 删除是按值
移除, 前缀判定与前缀计数都靠 startswith 逐个字符串比较, 通配符匹配对每个
字符串逐字符朴素匹配, 字典序遍历靠排序后再输出。集合一大就随字符串个数
和长度线性膨胀。
"""


class TrieError(Exception):
    """本包全部自定义错误的基类。"""


class EmptyError(TrieError):
    """空集合上执行了需要至少一个字符串的操作。"""


class NotFoundError(TrieError):
    """要删除的字符串不在集合里。"""


class FlatPrefixSet:
    """用一个字符串列表保存元素, 每次查询都扫全表。

    - insert / remove: 把字符串追加进列表 / 从列表里按值移除一个。
    - has_prefix: 逐个字符串用 startswith 判断是否存在该前缀。
    - count_prefix: 逐个字符串用 startswith 计数。
    - contains: 逐个字符串做相等比较。
    - words_with_prefix: 逐个字符串挑出以该前缀开头的, 排序后返回。
    - longest_common_prefix: 空集抛 EmptyError, 否则逐列比较全部字符串。
    - match_pattern: 对每个字符串做朴素的逐字符通配匹配, 排序后返回。
    - all_words: 返回排序后的全部字符串。
    """

    def __init__(self):
        self._items = []

    def __len__(self):
        """返回集合中的字符串个数, 含重复。"""
        return len(self._items)

    def insert(self, word):
        """加入字符串 word, 可重复加入同一串。"""
        if not isinstance(word, str):
            raise TrieError("word must be str")
        self._items.append(word)

    def remove(self, word):
        """删除一个值等于 word 的元素; 不存在时抛 NotFoundError。"""
        if not isinstance(word, str):
            raise TrieError("word must be str")
        for i, w in enumerate(self._items):
            if w == word:
                del self._items[i]
                return
        raise NotFoundError("word not present")

    def contains(self, word):
        """判断 word 是否作为完整字符串在集合中。"""
        if not isinstance(word, str):
            raise TrieError("word must be str")
        for w in self._items:
            if w == word:
                return True
        return False

    def has_prefix(self, prefix):
        """判断是否存在以 prefix 开头的字符串。"""
        if not isinstance(prefix, str):
            raise TrieError("prefix must be str")
        for w in self._items:
            if w.startswith(prefix):
                return True
        return False

    def count_prefix(self, prefix):
        """统计以 prefix 开头的字符串个数, 含重复。"""
        if not isinstance(prefix, str):
            raise TrieError("prefix must be str")
        n = 0
        for w in self._items:
            if w.startswith(prefix):
                n += 1
        return n

    def words_with_prefix(self, prefix):
        """返回以 prefix 开头的全部字符串, 按字典序升序, 含重复。"""
        if not isinstance(prefix, str):
            raise TrieError("prefix must be str")
        out = [w for w in self._items if w.startswith(prefix)]
        out.sort()
        return out

    def all_words(self):
        """返回全部字符串, 按字典序升序, 含重复。"""
        return sorted(self._items)

    def longest_common_prefix(self):
        """返回全部字符串的最长公共前缀; 空集时抛 EmptyError。"""
        if not self._items:
            raise EmptyError("empty collection")
        first = self._items[0]
        n = len(first)
        for w in self._items[1:]:
            n = min(n, len(w))
        i = 0
        while i < n:
            ch = first[i]
            for w in self._items[1:]:
                if w[i] != ch:
                    return first[:i]
            i += 1
        return first[:i]

    def match_pattern(self, pattern):
        """返回与通配模式匹配的全部字符串, 按字典序升序, 含重复。

        模式里点号通配任意单个字符, 其余字符按字面匹配, 串长必须与模式等长。
        """
        if not isinstance(pattern, str):
            raise TrieError("pattern must be str")
        out = []
        for w in self._items:
            if len(w) != len(pattern):
                continue
            ok = True
            for i in range(len(pattern)):
                p = pattern[i]
                if p != "." and p != w[i]:
                    ok = False
                    break
            if ok:
                out.append(w)
        out.sort()
        return out
