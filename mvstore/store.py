"""单机 KV 存储，JSON 行 append 日志持久化。

每次 put/delete 追加一条 JSON 记录，重启时按文件序重放恢复。
当前没有事务概念，读-改-写序列之间没有任何隔离。
"""

import json
import os
import threading


class Store:
    """单机 KV。

    path 为空时纯内存；给了 path 则所有写操作追加一份 JSON 行日志，
    重新打开同一 path 即恢复到最近状态。value 须可 JSON 序列化。
    """

    def __init__(self, path=None):
        self._lock = threading.Lock()
        self._data = {}
        self._path = path
        if path is not None:
            self._replay()

    def _replay(self):
        if not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                if rec["op"] == "put":
                    self._data[rec["key"]] = rec["value"]
                elif rec["op"] == "del":
                    self._data.pop(rec["key"], None)

    def _append(self, record):
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
            f.write("\n")

    def get(self, key):
        with self._lock:
            return self._data.get(key)

    def put(self, key, value):
        with self._lock:
            self._data[key] = value
        if self._path is not None:
            self._append({"op": "put", "key": key, "value": value})

    def delete(self, key):
        with self._lock:
            existed = key in self._data
            if existed:
                del self._data[key]
        if existed and self._path is not None:
            self._append({"op": "del", "key": key})
        return existed
