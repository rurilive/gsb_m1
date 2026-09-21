"""JSONL 记录文件：一条记录一行，追加即落盘。

写给进程内的事件链路用：每条记录是一行 JSON，append 写完就 flush；
读回时跳过空行，文件末尾没写完的残行（进程被杀在写一半的现场）忽略，
中间出现读不动的行说明文件坏了，直接报 ValueError，不许悄悄少读。
"""

import json
import threading


class Journal:
    """按行追加的 JSON 记录文件，path 由调用方指定。"""

    def __init__(self, path):
        if not isinstance(path, str) or not path:
            raise ValueError("path 必须是非空 str")
        self._path = path
        self._lock = threading.Lock()
        self._handle = open(path, "a", encoding="utf-8")

    @property
    def path(self):
        return self._path

    def append(self, record):
        """追加一条 dict 记录，一行 JSON，写完就 flush。"""
        if not isinstance(record, dict):
            raise TypeError(f"记录必须是 dict，收到 {type(record).__name__}")
        line = json.dumps(record, ensure_ascii=False, sort_keys=True)
        with self._lock:
            if self._handle is None:
                raise ValueError("Journal 已经关掉了，不能继续追加")
            self._handle.write(line + "\n")
            self._handle.flush()

    def read(self):
        """读回全部记录，最后一行没写完就丢掉那一行。"""
        with self._lock:
            if self._handle is not None:
                self._handle.flush()
            with open(self._path, encoding="utf-8") as handle:
                text = handle.read()
        if not text:
            return []
        torn = not text.endswith("\n")
        lines = text.split("\n")
        tail = lines.pop() if torn else None
        if not torn:
            lines.pop()  # 结尾换行带出的空串
        records = []
        for index, line in enumerate(lines):
            if not line.strip():
                continue
            records.append(self._parse(line, index + 1))
        if torn and tail and tail.strip():
            try:
                records.append(self._parse(tail, len(lines) + 1))
            except ValueError:
                pass  # 末尾残行，写到一半就被杀了，丢
        return records

    @staticmethod
    def _parse(line, position):
        try:
            record = json.loads(line)
        except ValueError:
            raise ValueError(
                f"第 {position} 行读不出来，文件可能坏了: {line[:40]!r}"
            ) from None
        if not isinstance(record, dict):
            raise ValueError(f"第 {position} 行不是 JSON 对象")
        return record

    def truncate(self):
        """清空文件重来，句柄重开。"""
        with self._lock:
            if self._handle is not None:
                self._handle.close()
            with open(self._path, "w", encoding="utf-8"):
                pass
            self._handle = open(self._path, "a", encoding="utf-8")

    def close(self):
        """关掉句柄，可重复调用；关掉后 append 报错，read 照常读盘。"""
        with self._lock:
            if self._handle is not None:
                self._handle.close()
                self._handle = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
