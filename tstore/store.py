"""时间点仓库门面：按文件魔数选裸存后端或压缩块后端。

已有裸存文件（TSRAW01）继续走 RawStore，追加规矩照旧、不迁移；
新文件走 BlockStore 块压缩。block_size 只对新建的块文件生效，
重开已有块文件时以文件头里记的块大小为准。
"""

import os

from .blocks import BLOCK_MAGIC
from .blockstore import DEFAULT_BLOCK_SIZE, BlockStore
from .layout import HEADER
from .raw import RawStore


class TsStore:
    """本地文件里的时间点序列，自动兼容裸存与块压缩两种格式。"""

    def __init__(self, path, block_size=DEFAULT_BLOCK_SIZE):
        path = str(path)
        backend = None
        if os.path.exists(path) and os.path.getsize(path) > 0:
            with open(path, "rb") as fh:
                magic = fh.read(len(HEADER))
            if magic == HEADER:
                backend = RawStore(path)
            elif magic == BLOCK_MAGIC:
                backend = BlockStore(path, block_size=block_size)
            else:
                # 交给后端报 TsFormatError，错误信息保持与基线一致。
                backend = RawStore(path)
        else:
            backend = BlockStore(path, block_size=block_size)
        self._backend = backend

    def append(self, ts, value):
        self._backend.append(ts, value)

    def append_many(self, pairs):
        self._backend.append_many(pairs)

    def read_at(self, index):
        return self._backend.read_at(index)

    def find(self, ts):
        return self._backend.find(ts)

    def __iter__(self):
        return iter(self._backend)

    def read_all(self):
        return self._backend.read_all()

    def __len__(self):
        return len(self._backend)

    @property
    def path(self):
        return self._backend.path

    @property
    def last_ts(self):
        return self._backend.last_ts

    @property
    def block_size(self):
        """块文件的每块条数；裸存文件返回 None。"""
        return getattr(self._backend, "block_size", None)

    def stats(self):
        return self._backend.stats()

    def close(self):
        self._backend.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False
