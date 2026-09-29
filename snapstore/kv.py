"""snapstore 现有的逐键 KV 实现，纯标准库，无外部依赖。

这是改造前的基线：只有一个逐键独立读写的键值存储，每个键各自读、各自写，
键与键之间没有任何一致性关系。写入即生效，读到的永远是最后一次写入的值。

现有对外能力：
  put(key, value)   写入一个键的值，键已存在则覆盖
  get(key)          返回键当前的值，键不存在返回 None
  delete(key)       删除一个键，返回该键此前是否存在
  keys()            当前存在的键，按升序
  __contains__(key) 键是否当前存在

暂时没有：跨键的原子写入、一致性快照、写时复制、写写冲突检测、快照回收。
本文件的行为由 tests/test_store.py 锁住，一字不许改；新能力另建模块与测试。
"""

import threading


class KeyValueStore:
    """一个单机的逐键内存 KV。

    内部结构：_data 是键到值的普通字典。所有读写都在一把可重入锁下进行，
    键与值都不做拷贝，取出的值与原对象同一。
    """

    def __init__(self):
        self._data = {}
        self._lock = threading.RLock()

    def put(self, key, value):
        """写入一个键的值，键已存在则覆盖，返回 None。"""
        with self._lock:
            self._data[key] = value

    def get(self, key):
        """返回键当前的值，键不存在返回 None。"""
        with self._lock:
            return self._data.get(key)

    def delete(self, key):
        """删除一个键，返回该键删除前是否存在。"""
        with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            return existed

    def keys(self):
        """当前存在的键，按升序返回。"""
        with self._lock:
            return sorted(self._data)

    def __contains__(self, key):
        with self._lock:
            return key in self._data