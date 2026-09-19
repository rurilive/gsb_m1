"""归档条目对象。"""


class ArchiveEntry(object):
    """归档里的一个条目。"""

    def __init__(self, name, data):
        if not isinstance(name, str):
            raise TypeError("entry name must be str")
        if not isinstance(data, bytes):
            raise TypeError("entry data must be bytes")
        self.name = name
        self.data = data

    def __eq__(self, other):
        if not isinstance(other, ArchiveEntry):
            return NotImplemented
        return self.name == other.name and self.data == other.data

    def __repr__(self):
        return "ArchiveEntry(name=%r, data=%d bytes)" % (self.name, len(self.data))
