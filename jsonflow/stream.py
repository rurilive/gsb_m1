"""入库批处理用的文件读写口子。

批处理要的是吞吐，数字不再留字面量包装，直接落成 Python 数。
"""

import re

from .encoder import dumps
from .parser import Parser

_NUMBER_SCAN = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")

# 最近一次 load 在全文里扫到的数字个数，归档日志要报这个指标。
_LAST_NUMBER_COUNT = 0


class ArchiveParser(Parser):
    """归档解析器：数字落成 Python 数，重复键以先出现的为准。"""

    def make_number(self, raw):
        return float(raw)

    def make_object(self, pairs):
        obj = {}
        for key, value in pairs:
            if key not in obj:
                obj[key] = value
        return obj


def load(fp, chunk_size=1 << 16):
    """从文件对象读一份 JSON。"""
    global _LAST_NUMBER_COUNT
    data = fp.read()
    if isinstance(data, (bytes, bytearray)):
        data = data.decode("utf-8")
    _LAST_NUMBER_COUNT = len(_NUMBER_SCAN.findall(data))
    return ArchiveParser(data).parse_document()


def dump(obj, fp, chunk_size=1 << 16):
    """把一个对象写进文件对象。"""
    fp.write(dumps(obj))
