"""朴素回文子串工具：内部一个字符串，全部靠枚举子串当场判断。

BrutePalTree 把一段文本存在自己身上，所有回文相关的事实都从枚举子串
现算：判断某个子串是否回文用双指针从两端往中间比，枚举全部回文子串就
把所有下标区间过一遍再挑出回文的，统计某位置为结尾的回文个数就把以该
位置结尾的每个区间都判一次，判断某个回文是否出现也把全文本的区间扫一
遍。没有任何预处理，没有共享状态，代价随文本长度的平方增长。

回文树（回文自动机）那套失配链与双根结构见任务描述。
"""


class PalTreeError(Exception):
    """本模块所有异常的基类，便于调用方一把兜住。"""


class IllegalArgument(PalTreeError):
    """参数类型或取值非法。"""


class NotASubstring(PalTreeError):
    """给出的串并不是当前文本的子串。"""


class IndexOutOfRange(PalTreeError):
    """位置下标越界。"""


class BrutePalTree(object):
    """朴素回文子串结构，内部持有单个字符串，一切现算。"""

    def __init__(self, text):
        if not isinstance(text, str):
            raise IllegalArgument("文本必须是字符串")
        self._text = text

    @property
    def text(self):
        return self._text

    def __len__(self):
        return len(self._text)

    def _check_index(self, i):
        if not isinstance(i, int) or isinstance(i, bool):
            raise IllegalArgument("下标必须是整数")
        if i < 0 or i >= len(self._text):
            raise IndexOutOfRange("下标越界: %r" % (i,))

    def _is_pal_slice(self, start, end):
        """判断 [start, end) 这段区间是否回文。"""
        left = start
        right = end - 1
        while left < right:
            if self._text[left] != self._text[right]:
                return False
            left += 1
            right -= 1
        return True

    @staticmethod
    def _is_palindrome(s):
        """单纯的镜像判断，不涉及文本归属。"""
        left = 0
        right = len(s) - 1
        while left < right:
            if s[left] != s[right]:
                return False
            left += 1
            right -= 1
        return True

    def is_pal(self, s):
        """判断给定子串是否回文；不是当前文本的子串则报错。"""
        if not isinstance(s, str):
            raise IllegalArgument("待判断的必须是字符串")
        if s == "":
            raise IllegalArgument("空串不作为子串判断")
        if s not in self._text:
            raise NotASubstring("不是当前文本的子串: %r" % (s,))
        return self._is_palindrome(s)

    def palindromic_substrings(self):
        """枚举全部子串并挑出回文，按起点、再由短到长收集成列表。

        同一个回文在文本里出现几次就收几次，不做去重。
        """
        result = []
        n = len(self._text)
        for start in range(n):
            for end in range(start + 1, n + 1):
                if self._is_pal_slice(start, end):
                    result.append(self._text[start:end])
        return result

    def pal_count_by_end(self, i):
        """统计以位置 i 结尾（含单字符本身）的回文子串个数。"""
        self._check_index(i)
        count = 0
        for start in range(i + 1):
            if self._is_pal_slice(start, i + 1):
                count += 1
        return count

    def contains_pal(self, x):
        """判断给定回文是否作为子串出现；非回文直接报错。"""
        if not isinstance(x, str):
            raise IllegalArgument("待判断的必须是字符串")
        if x == "":
            raise IllegalArgument("空串不作为回文判断")
        if not self._is_palindrome(x):
            raise IllegalArgument("给定串本身不是回文: %r" % (x,))
        return x in self._text
