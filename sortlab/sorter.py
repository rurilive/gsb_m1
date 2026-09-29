"""最朴素的整数排序器。

NaiveSorter 用选择排序对整数序列按数值大小直接排序，作为基数排序与外部排序
改造前的基线实现。它不做分桶、不保证稳定性，也不接受键函数。
"""


class NaiveSorter:
    """对整个列表直接排序的天真排序器。

    sort 返回一个新的升序列表，不修改入参；比较只用整数的大小关系。
    """

    def sort(self, values):
        """返回 values 的升序副本。

        参数 values 为整数可迭代对象；返回新的列表，入参保持不变。
        """
        data = list(values)
        n = len(data)
        for i in range(n - 1):
            min_index = i
            for j in range(i + 1, n):
                if data[j] < data[min_index]:
                    min_index = j
            if min_index != i:
                data[i], data[min_index] = data[min_index], data[i]
        return data

    def sorted(self, values):
        """sort 的别名，便于以属性风格调用。"""
        return self.sort(values)
