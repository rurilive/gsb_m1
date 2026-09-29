"""deltafy 的最朴素实现：逐行相等比较器。

现状只做一件事：把两段文本按行切开，从第一行起逐行比对，两侧行数一致时
相同位置内容不同就记一条替换，相同位置内容一致就记一条相同。没有最长公共
子序列，没有增删对齐，没有补丁，也没有把改动应用回去的能力。
"""


class LineDiff(object):
    """逐行相等比较器，只按位置比对，不做对齐。"""

    def __init__(self, old, new):
        self.old_lines = old.splitlines()
        self.new_lines = new.splitlines()

    def operations(self):
        """从第一行起逐行比对，返回替换与相同两类操作。

        操作是形如 ("replace", line_no, old_line, new_line) 或
        ("same", line_no, line, line) 的元组，line_no 从 1 开始。
        两侧行数不同时，多出来的行直接记成替换，旧侧缺失的 old_line
        或新侧缺失的 new_line 用 None 占位。
        """
        ops = []
        total = max(len(self.old_lines), len(self.new_lines))
        for index in range(total):
            line_no = index + 1
            old_line = self.old_lines[index] if index < len(self.old_lines) else None
            new_line = self.new_lines[index] if index < len(self.new_lines) else None
            if old_line == new_line:
                ops.append(("same", line_no, old_line, new_line))
            else:
                ops.append(("replace", line_no, old_line, new_line))
        return ops

    def changed_count(self):
        """返回被记成替换的行数。"""
        return sum(1 for op in self.operations() if op[0] == "replace")

    def same_count(self):
        """返回被记成相同的行数。"""
        return sum(1 for op in self.operations() if op[0] == "same")
