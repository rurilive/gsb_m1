"""按版本维护的页表。

页面在哪个版本被放到了哪个帧上，全部记在一张表里；读取时按
调用方请求的版本回溯，历史版本的映射随时可以查回来。内部一把
锁保护，多路写入同时进来也不会把表写坏。
"""

import threading
from bisect import bisect_right


class MappingConflict(Exception):
    """同一个页面在同一个版本上被映射到了不同的帧。"""


class PageTable:
    """版本化页表。

    每个页面维护一串 (版本号, 帧号) 记录，按版本号升序排；帧号为
    None 表示从该版本起取消映射（墓碑记录）。walk 读出页面在请求
    版本上对应的帧，没有映射时返回 None。

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
        """把 page 在 ver 版本上映射到 frame。

        同页同版本再映射到同一个帧是幂等的；映射到不同帧抛
        MappingConflict，后到的写入不会盖掉先前的。
        """
        with self._lock:
            entries = self._log.setdefault(page, [])
            versions = [v for v, _ in entries]
            pos = bisect_right(versions, ver)
            if pos > 0 and versions[pos - 1] == ver:
                old_frame = entries[pos - 1][1]
                if old_frame != frame:
                    raise MappingConflict(
                        "page %r 在版本 %r 上已映射到帧 %r，不能再映射到 %r"
                        % (page, ver, old_frame, frame)
                    )
            else:
                entries.insert(pos, (ver, frame))
            self._now = max(self._now, ver)

    def walk(self, page, ver):
        """读出 page 在 ver 版本对应的帧，没有映射时返回 None。

        取版本号不大于 ver 的最后一条记录：记录可能落在更早的版本，
        映射一直有效到被后一条记录取代；取到墓碑记录时帧就是 None。
        """
        with self._lock:
            entries = self._log.get(page)
            if not entries:
                return None
            pos = bisect_right([v for v, _ in entries], ver)
            if pos == 0:
                return None
            return entries[pos - 1][1]

    def unmap(self, page):
        """取消 page 的映射，返回是否真的取消掉了。

        只追加一条打在新版本 now+1 上的墓碑记录，历史记录原样保留，
        所以历史版本照样读得到；当前已经是未映射状态则返回 False。
        """
        with self._lock:
            entries = self._log.get(page)
            if not entries or entries[-1][1] is None:
                return False
            self._now += 1
            entries.append((self._now, None))
            return True

    def rollback(self, ver):
        """把页表回滚到 ver 版本，丢掉该版本之后的记录。

        只保留版本号不大于 ver 的记录，回滚点之后的换帧和取消全部
        作废，读出来就是回滚点当时的帧（或当时的未映射状态）。
        """
        with self._lock:
            for page in list(self._log):
                entries = self._log[page]
                kept = [(v, f) for v, f in entries if v <= ver]
                if not kept:
                    del self._log[page]
                else:
                    self._log[page] = kept
            self._now = min(self._now, ver)

    def version(self):
        """最近一次写入用到的版本号。"""
        with self._lock:
            return self._now
