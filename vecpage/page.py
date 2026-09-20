"""按版本维护的页表。

页面在哪个版本被放到了哪个帧上，全部记在一张表里；读取时按
调用方请求的版本回溯，历史版本的映射随时可以查回来。内部一把
锁保护，多路写入同时进来也不会把表写坏。
"""

import threading


class MappingConflict(Exception):
    """同一个页面在同一个版本上被映射到了不同的帧。"""


class PageTable:
    """版本化页表。

    每个页面维护一串 (版本号, 帧号) 记录，按版本号升序排；帧号为
    None 表示从该版本起取消映射。walk 读出页面在请求版本上对应的
    帧，没有映射时返回 None。

    version() 是最近一次写入用到的版本号，unmap 产生的取消记录打
    在递增之后的新版本上。
    """

    def __init__(self):
        self._lock = threading.Lock()
        # page -> [(ver, frame), ...]，按 ver 升序
        self._log = {}
        # 最近一次写入用到的版本号
        self._now = 0

    def map(self, page, frame, ver):
        """把 page 在 ver 版本上映射到 frame。"""
        with self._lock:
            entries = self._log.setdefault(page, [])
            entries.append((ver, frame))
            self._now = max(self._now, ver)

    def walk(self, page, ver):
        """读出 page 在 ver 版本对应的帧，没有映射时返回 None。"""
        with self._lock:
            entries = self._log.get(page)
            if not entries:
                return None
            return entries[-1][1]

    def unmap(self, page):
        """取消 page 的映射，返回是否真的取消掉了。"""
        with self._lock:
            if page not in self._log:
                return False
            del self._log[page]
            return True

    def rollback(self, ver):
        """把页表回滚到 ver 版本，丢掉该版本之后的记录。"""
        with self._lock:
            for page in list(self._log):
                entries = self._log[page]
                kept = [(v, f) for v, f in entries if v <= ver]
                if not kept:
                    del self._log[page]
                    continue
                kept[-1] = (kept[-1][0], entries[-1][1])
                self._log[page] = kept
            self._now = min(self._now, ver)

    def version(self):
        """最近一次写入用到的版本号。"""
        with self._lock:
            return self._now
