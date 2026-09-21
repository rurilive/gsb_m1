"""块级增量传输：内容寻址块仓，加上发送端与接收端。

思路：文件按 block_size 切块，逐块算 sha256 当名字。接收端仓里已有的
块一概不传，只把缺的块请过来；校验不过的块只回请那一块。所有读写都
按块流式进行，任何时刻内存里只有有限几块在飞，峰值不随文件大小涨。
"""

import hashlib
import json
import os
import tempfile

DEFAULT_BLOCK_SIZE = 1 << 16
SERVE_BATCH = 16


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _request_frame(digests):
    return b"REQ " + json.dumps(list(digests)).encode("ascii")


def _parse_request(frame):
    if not frame.startswith(b"REQ "):
        raise ValueError("not a request frame: %r" % frame[:16])
    return json.loads(frame[4:].decode("ascii"))


def _block_frame(digest, payload):
    return b"BLK %s %d\n" % (digest.encode("ascii"), len(payload)) + payload


def _parse_block(frame):
    header, sep, payload = frame.partition(b"\n")
    if not sep:
        raise ValueError("not a block frame: %r" % frame[:16])
    parts = header.split(b" ")
    if len(parts) != 3 or parts[0] != b"BLK":
        raise ValueError("not a block frame: %r" % frame[:16])
    digest = parts[1].decode("ascii")
    if len(payload) != int(parts[2]):
        raise ValueError("block frame payload truncated")
    return digest, payload


class BlockIndex:
    """按校验和存块的内容寻址块仓，同内容只存一份，跨文件复用。"""

    def __init__(self, block_size=DEFAULT_BLOCK_SIZE):
        if block_size <= 0:
            raise ValueError("block_size must be positive")
        self.block_size = block_size
        self._blocks = {}

    def put(self, data):
        """存一块，返回它的校验和；同内容重复 put 只占一份。"""
        data = bytes(data)
        digest = _hash(data)
        self._blocks.setdefault(digest, data)
        return digest

    def get(self, digest):
        """按校验和取块，仓里没有抛 KeyError。"""
        return self._blocks[digest]

    def has(self, digest):
        """仓里有没有这一块。"""
        return digest in self._blocks

    def stats(self):
        """仓里存了多少块、共多少字节。"""
        return {
            "blocks": len(self._blocks),
            "bytes": sum(len(b) for b in self._blocks.values()),
        }


class Sender:
    """发送端：出块清单，按请求把仓里缺的块推过通道。"""

    def __init__(self, index, channel):
        self.index = index
        self.channel = channel

    def plan(self, path):
        """流式扫一遍文件出块清单，内存里只留摘要，不整份读入。"""
        digests = []
        with open(path, "rb") as fh:
            while True:
                block = fh.read(self.index.block_size)
                if not block:
                    break
                digests.append(_hash(block))
        return {
            "path": path,
            "size": os.path.getsize(path),
            "block_size": self.index.block_size,
            "blocks": digests,
        }

    def push(self, manifest, max_blocks=SERVE_BATCH):
        """回应通道里滞留的取块请求，只推接收端仓里缺的块。

        优先从自己的块仓取，没缓存就流式重读源文件按摘要匹配，
        一次最多推 max_blocks 块，通道里不会堆满整份文件。
        返回本次推出的块数。
        """
        wanted = []
        seen = set()
        for frame in self.channel.drain():
            for digest in _parse_request(frame):
                if digest not in seen:
                    seen.add(digest)
                    wanted.append(digest)
        sent = 0
        todo = []
        for digest in wanted:
            if sent >= max_blocks:
                break
            if self.index.has(digest):
                self.channel.send(_block_frame(digest, self.index.get(digest)))
                sent += 1
            else:
                todo.append(digest)
        if todo and sent < max_blocks:
            missing = set(todo)
            with open(manifest["path"], "rb") as fh:
                while missing and sent < max_blocks:
                    block = fh.read(self.index.block_size)
                    if not block:
                        break
                    digest = _hash(block)
                    if digest in missing:
                        self.channel.send(_block_frame(digest, block))
                        missing.discard(digest)
                        sent += 1
            if missing and sent < max_blocks:
                raise ValueError(
                    "source file no longer contains %d requested block(s)"
                    % len(missing))
        return sent


class Receiver:
    """接收端：收块入仓，块齐了就重建目标文件。"""

    def __init__(self, index, channel):
        self.index = index
        self.channel = channel
        self._stale = set()

    def apply(self, manifest, dst):
        """推进一轮重建，dst 已是最新返回 True，还缺块返回 False。

        先收下通道里滞留的块帧，校验通过才入仓，校验不过的不入仓、
        下一轮只回请那一块；还缺块就发取块请求。块齐了之后若 dst
        内容已经与清单一致就直接收工（已确认的块不重传也不重写），
        否则写临时文件再原子替换，失败与并发写都不会在 dst 留半截。
        """
        digests = manifest["blocks"]
        wanted = set(digests)
        for frame in self.channel.drain():
            digest, payload = _parse_block(frame)
            if digest in wanted and _hash(payload) == digest:
                self.index.put(payload)
        key = (os.path.abspath(dst), hash(tuple(digests)))
        if key not in self._stale:
            if self._dst_matches(manifest, dst):
                return True
            self._stale.add(key)
        missing = [d for d in dict.fromkeys(digests) if not self.index.has(d)]
        if missing:
            self.channel.send(_request_frame(missing))
            return False
        self._rebuild(digests, dst)
        return True

    def _dst_matches(self, manifest, dst):
        """流式核对 dst 现有内容是否已与清单一致。"""
        if not os.path.isfile(dst):
            return False
        if os.path.getsize(dst) != manifest["size"]:
            return False
        with open(dst, "rb") as fh:
            for digest in manifest["blocks"]:
                if _hash(fh.read(manifest["block_size"])) != digest:
                    return False
            return fh.read(1) == b""

    def _rebuild(self, digests, dst):
        """从块仓逐块写到同目录临时文件，再原子替换成 dst。"""
        parent = os.path.dirname(os.path.abspath(dst))
        os.makedirs(parent, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".snapwire-", dir=parent)
        try:
            with os.fdopen(fd, "wb") as out:
                for digest in digests:
                    out.write(self.index.get(digest))
                out.flush()
                os.fsync(out.fileno())
            os.replace(tmp, dst)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
