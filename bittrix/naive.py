"""bittrix 的整数位操作工具（改造前的现状）。

现在只有一条路：求二进制里一的个数、求最低位一的位置、判断是否二的幂、求最
高位一的位置、求二进制逆序、求两数二进制公共前缀长度、判断二进制表示里是否
存在相邻互不相同的一对，全靠在二进制字符串上逐字符比对，或对整数的每一位逐
位右移判最低位。结果都对，但位数一多、数一多，循环次数就随位宽线性涨上去，
批量求每位置位计数更是要用双重循环。位技巧做法见任务描述。
"""


class Erro(Exception):
    """本模块所有对外异常的公共基类。"""


class BitError(Erro):
    """位操作工具收到的非法输入。"""


def _check_int(value, name="value"):
    """取值必须是整数，布尔值不算整数。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise BitError("%s must be an int" % name)
    return value


def _check_width(width):
    """位宽必须是大于等于零的整数。"""
    if isinstance(width, bool) or not isinstance(width, int):
        raise BitError("width must be an int")
    if width < 0:
        raise BitError("width must not be negative")
    return width


def _check_non_negative(value, name="value"):
    """取值必须是非负整数。"""
    _check_int(value, name)
    if value < 0:
        raise BitError("%s must not be negative" % name)
    return value


def _bits(value, width):
    """把整数写成定宽二进制串，最高位在左；位宽不足时截断高位。"""
    if width == 0:
        return ""
    return format(value, "0%db" % width)[-width:]


def popcount_str(value):
    """求二进制里一的个数，朴素做法：转成二进制串后逐字符数一。"""
    _check_non_negative(value, "value")
    count = 0
    for ch in bin(value)[2:]:
        if ch == "1":
            count += 1
    return count


def popcount_loop(value):
    """求二进制里一的个数，朴素做法：反复右移并判最低位。"""
    _check_non_negative(value, "value")
    count = 0
    while value:
        count += value & 1
        value >>= 1
    return count


def lowest_set_bit(value):
    """求最低位一的位置（零起），朴素做法：逐位右移直到最低位为一。

    零没有最低位一，抛 BitError。
    """
    _check_non_negative(value, "value")
    if value == 0:
        raise BitError("zero has no set bit")
    pos = 0
    while value & 1 == 0:
        value >>= 1
        pos += 1
    return pos


def highest_set_bit(value):
    """求最高位一的位置（零起），朴素做法：逐位右移直到数变成零。

    零没有最高位一，抛 BitError。
    """
    _check_non_negative(value, "value")
    if value == 0:
        raise BitError("zero has no set bit")
    pos = -1
    while value:
        value >>= 1
        pos += 1
    return pos


def is_power_of_two(value):
    """判断是否二的幂，朴素做法：数一的个数是否等于一。"""
    _check_non_negative(value, "value")
    if value == 0:
        return False
    return popcount_str(value) == 1


def reverse_bits(value, width):
    """把整数按定位宽做二进制逆序，朴素做法：位串切片翻转再转回整数。"""
    _check_non_negative(value, "value")
    _check_width(width)
    bits = _bits(value, width)
    flipped = bits[::-1]
    if flipped == "":
        return 0
    return int(flipped, 2)


def common_prefix_length(a, b, width):
    """两数在定位宽下二进制公共前缀的长度，朴素做法：逐字符比对位串。

    比较宽度取两者二进制串中较短的长度，再与位宽上限取小。
    """
    _check_non_negative(a, "a")
    _check_non_negative(b, "b")
    _check_width(width)
    if width == 0:
        return 0
    limit = width
    ba = _bits(a, width)
    bb = _bits(b, width)
    n = min(len(ba), len(bb), limit)
    length = 0
    for i in range(n):
        if ba[i] != bb[i]:
            break
        length += 1
    return length


def has_adjacent_alternating(value, width):
    """二进制表示里是否存在相邻互不相同的一对，朴素做法：逐位比对。"""
    _check_non_negative(value, "value")
    _check_width(width)
    if width < 2:
        return False
    bits = _bits(value, width)
    for i in range(len(bits) - 1):
        if bits[i] != bits[i + 1]:
            return True
    return False


def all_adjacent_pairs_differ(value, width):
    """二进制表示里是否每一对相邻的位都互不相同，朴素做法：逐位比对。"""
    _check_non_negative(value, "value")
    _check_width(width)
    if width < 2:
        return True
    bits = _bits(value, width)
    for i in range(len(bits) - 1):
        if bits[i] == bits[i + 1]:
            return False
    return True


def gray_adjacent_one_bit(value, width):
    """是否与相邻整数恰好相差一个位，朴素做法：位串逐字符比对。

    零与全一之间按回环相邻处理；位宽小于一时恒为真。
    """
    _check_non_negative(value, "value")
    _check_width(width)
    if width == 0:
        return True
    mask = (1 << width) - 1
    neighbor = (value + 1) & mask
    bits_a = _bits(value, width)
    bits_b = _bits(neighbor, width)
    diff = 0
    for i in range(width):
        if bits_a[i] != bits_b[i]:
            diff += 1
    return diff == 1


def bit_position_counts(values, width):
    """对一个整数集合批量求每位的置位计数，朴素做法：逐数逐位累加。"""
    _check_width(width)
    counts = [0] * width
    for value in values:
        _check_non_negative(value, "value")
        bits = _bits(value, width)
        for i in range(width):
            if bits[i] == "1":
                counts[i] += 1
    return counts


def interleave_check(a, b, width):
    """独立做法印证口：两数在定位宽下的位串是否逐位相同，朴素逐字符比对。"""
    _check_non_negative(a, "a")
    _check_non_negative(b, "b")
    _check_width(width)
    ba = _bits(a, width)
    bb = _bits(b, width)
    return ba == bb


class BitTools:
    """绑定一个位宽的位操作工具，只有朴素逐位与位串比对这一条路。

    求一的个数、最低位一、最高位一、二的幂判定、逆序、公共前缀、相邻位判定、
    批量每位置位计数都提供方法，并累计访问位的次数，供与位技巧做法对照规模。
    位宽在构造时校验并固定。
    """

    def __init__(self, width):
        self._width = _check_width(width)
        self._visit_count = 0

    def width(self):
        """返回绑定的位宽。"""
        return self._width

    def reset_visit_count(self):
        """把访问位计数清零。"""
        self._visit_count = 0

    def visit_count(self):
        """自上次清零以来累计访问了多少个位。"""
        return self._visit_count

    def _visit(self, n):
        """累计一次访问若干位。"""
        self._visit_count += n

    def popcount(self, value):
        """朴素求一的个数：逐位右移判最低位，访问位计数随位宽累加。"""
        _check_non_negative(value, "value")
        count = 0
        while value:
            self._visit(1)
            count += value & 1
            value >>= 1
        return count

    def popcount_by_string(self, value):
        """朴素求一的个数：转二进制串逐字符数一。"""
        _check_non_negative(value, "value")
        bits = bin(value)[2:]
        self._visit(len(bits))
        return sum(1 for ch in bits if ch == "1")

    def lowest_set_bit(self, value):
        """朴素求最低位一位置：逐位右移。"""
        _check_non_negative(value, "value")
        if value == 0:
            raise BitError("zero has no set bit")
        pos = 0
        while value & 1 == 0:
            self._visit(1)
            value >>= 1
            pos += 1
        return pos

    def highest_set_bit(self, value):
        """朴素求最高位一位置：逐位右移。"""
        _check_non_negative(value, "value")
        if value == 0:
            raise BitError("zero has no set bit")
        pos = -1
        while value:
            self._visit(1)
            value >>= 1
            pos += 1
        return pos

    def is_power_of_two(self, value):
        """朴素判断二的幂：数一的个数是否等于一。"""
        _check_non_negative(value, "value")
        if value == 0:
            return False
        return self.popcount_by_string(value) == 1

    def reverse_bits(self, value):
        """朴素按绑定位宽逆序：位串切片翻转。"""
        _check_non_negative(value, "value")
        bits = _bits(value, self._width)
        self._visit(len(bits))
        if bits == "":
            return 0
        return int(bits[::-1], 2)

    def common_prefix_length(self, a, b):
        """朴素求两数公共前缀长度：逐字符比对位串。"""
        _check_non_negative(a, "a")
        _check_non_negative(b, "b")
        width = self._width
        ba = _bits(a, width)
        bb = _bits(b, width)
        self._visit(min(len(ba), len(bb)))
        length = 0
        for i in range(min(len(ba), len(bb))):
            if ba[i] != bb[i]:
                break
            length += 1
        return length

    def has_adjacent_alternating(self, value):
        """朴素判断是否存在相邻互不相同的一对：逐位比对。"""
        _check_non_negative(value, "value")
        if self._width < 2:
            return False
        bits = _bits(value, self._width)
        self._visit(len(bits))
        for i in range(len(bits) - 1):
            if bits[i] != bits[i + 1]:
                return True
        return False

    def gray_adjacent_one_bit(self, value):
        """朴素判断与相邻整数是否恰好相差一个位：逐位比对。"""
        _check_non_negative(value, "value")
        width = self._width
        if width == 0:
            return True
        mask = (1 << width) - 1
        neighbor = (value + 1) & mask
        ba = _bits(value, width)
        bb = _bits(neighbor, width)
        self._visit(width)
        diff = 0
        for i in range(width):
            if ba[i] != bb[i]:
                diff += 1
        return diff == 1

    def bit_position_counts(self, values):
        """朴素批量求每位置位计数：逐数逐位累加。"""
        width = self._width
        counts = [0] * width
        for value in values:
            _check_non_negative(value, "value")
            bits = _bits(value, width)
            self._visit(width)
            for i in range(width):
                if bits[i] == "1":
                    counts[i] += 1
        return counts
