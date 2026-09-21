"""tstore 的异常类型。"""


class TsStoreError(Exception):
    """本包所有异常的基类。"""


class OutOfOrderError(TsStoreError):
    """时间戳相对上一条回退，写入被拒绝。"""


class TsFormatError(TsStoreError):
    """文件头或文件长度不符合磁盘布局。"""
