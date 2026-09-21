"""整份同步，以及模拟传输用的内存通道。"""

import os
from collections import deque

from snapwire.hashing import READ_CHUNK


class ChannelBroken(Exception):
    """通道被切断，或者通道里已经取不到帧。"""


class Channel:
    """内存传输通道，两侧都能收发，统计累计搬运的字节数。

    limit 不为 None 时模拟线路中断：再收一帧就会超限的那次 send 抛
    ChannelBroken，此前已经进通道的帧仍然能被对端取走，
    正好等于 limit 的发送不算超限。
    """

    def __init__(self, limit=None):
        self._frames = deque()
        self._moved = 0
        self._limit = limit
        self._broken = False

    @property
    def bytes_moved(self):
        """至今进入通道的字节总数。"""
        return self._moved

    @property
    def broken(self):
        """通道是否已经被切断。"""
        return self._broken

    def send(self, frame):
        """把一帧推入通道，字节数计入 bytes_moved。"""
        if self._broken:
            raise ChannelBroken("channel already broken")
        frame = bytes(frame)
        if self._limit is not None and self._moved + len(frame) > self._limit:
            self._broken = True
            raise ChannelBroken(
                "cut after %d bytes, frame of %d rejected"
                % (self._moved, len(frame)))
        self._frames.append(frame)
        self._moved += len(frame)

    def recv(self):
        """取走最早的一帧，通道里没有帧时抛 ChannelBroken。"""
        if not self._frames:
            raise ChannelBroken("no frame in channel")
        return self._frames.popleft()

    def pending(self):
        """通道里滞留的帧数。"""
        return len(self._frames)

    def drain(self):
        """取走全部滞留帧，返回列表。"""
        frames = list(self._frames)
        self._frames.clear()
        return frames


def sync_full(src, dst, channel, chunk_size=READ_CHUNK):
    """把 src 整份搬给 dst 的参考实现。

    按 chunk_size 切帧推入通道，随即取回顺序落盘，返回本次搬运的
    字节数。通道中途断裂抛 ChannelBroken，这时 dst 只写了一半。
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    before = channel.bytes_moved
    parent = os.path.dirname(os.path.abspath(dst))
    os.makedirs(parent, exist_ok=True)
    with open(src, "rb") as fh, open(dst, "wb") as out:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            channel.send(chunk)
            out.write(channel.recv())
    return channel.bytes_moved - before
