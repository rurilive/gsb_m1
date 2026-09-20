"""溢写文件（run）的编码、读写与句柄预算。

每个 run 文件是若干行，每行一条记录，格式为 序号 + 制表符 + 原始记录
（记录本身必须是单行文本）。seq 是记录进入排序器时的全局序号，key
相同的记录靠它判定输入先后。
"""

import os


class TooManyOpenRuns(RuntimeError):
    """同时打开的 run 文件数超过 fd_limit，相当于系统句柄耗尽。"""


class RunFileGuard:
    """run 文件的句柄预算。

    进程里所有 run 文件（包括归并产生的中间输出和最终输出）的打开
    都要经过这里；同时打开数超过 fd_limit 就抛 TooManyOpenRuns。
    归并至少需要两个输入加一个输出，因此 fd_limit 不得小于 3。
    """

    def __init__(self, fd_limit):
        if fd_limit < 3:
            raise ValueError("fd_limit 至少为 3")
        self.fd_limit = fd_limit
        self.open_count = 0
        self.peak = 0

    def acquire(self):
        if self.open_count >= self.fd_limit:
            raise TooManyOpenRuns(
                "run 文件同时打开 %d 个，达到上限 %d" % (self.open_count, self.fd_limit)
            )
        self.open_count += 1
        if self.open_count > self.peak:
            self.peak = self.open_count

    def release(self):
        if self.open_count <= 0:
            raise RuntimeError("句柄预算失衡")
        self.open_count -= 1


def encode_record(seq, record):
    """把一条记录编码成一行文本。"""
    return "%d\t%s\n" % (seq, record)


def decode_record(line):
    """把一行文本解回 (seq, record)。"""
    seq_text, record = line.split("\t", 1)
    return int(seq_text), record.rstrip("\n")


def write_run(path, entries, guard):
    """把 (seq, record) 序列写成 run 文件，返回写入条数。

    entries 是按序的迭代器，逐条写出，不会整段留在内存。
    """
    guard.acquire()
    try:
        count = 0
        with open(path, "w", encoding="utf-8") as fh:
            for seq, record in entries:
                fh.write(encode_record(seq, record))
                count += 1
        return count
    finally:
        guard.release()


class RunReader:
    """顺序读取一个 run 文件。

    构造时占用一个句柄，close() 释放；读完整个文件后再 close 也可以。
    """

    def __init__(self, path, guard):
        self.path = path
        self._guard = guard
        self._guard.acquire()
        try:
            self._fh = open(path, "r", encoding="utf-8")
        except Exception:
            self._guard.release()
            raise

    def next(self):
        """取下一条 (seq, record)，读完返回 None。"""
        if self._fh is None:
            return None
        line = self._fh.readline()
        if not line:
            return None
        return decode_record(line)

    def close(self):
        if self._fh is not None:
            self._fh.close()
            self._fh = None
            self._guard.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False


def remove_file(path):
    """删掉一个文件，不存在就忽略。"""
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
