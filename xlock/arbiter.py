"""集中式仲裁的参考实现。

拿锁的决定全部由一个单线程服务端串行做出：任意时刻只有一把锁在外面，
客户端连上来发请求拿锁，连接断开（包括进程被杀）就等于释放。接口语义
和 FileLock 对齐：acquire 返回 True/False，release 释放，is_held 查询
现在有没有人持有。这个实现只用来做测试里的对照基准，线上路径不依赖它。
"""

import os
import socket
import socketserver
import threading
import time


class CentralArbiter:
    """单仲裁者服务端，start() 之后用 ArbiterClient 连它。"""

    def __init__(self, socket_path):
        self.socket_path = socket_path
        self.holder = None
        self._cond = threading.Condition()
        self._server = None
        self._thread = None

    def start(self):
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        self._server = _Server(self.socket_path, _Handler)
        self._server.arbiter = self
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            kwargs={"poll_interval": 0.05}, daemon=True)
        self._thread.start()
        return self

    def stop(self):
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)

    # ---- 归属判定，全部在这里串行做 ----

    def acquire(self, who, timeout):
        with self._cond:
            if self.holder in (None, who):
                self.holder = who
                return True
            if timeout is None:
                while self.holder not in (None, who):
                    self._cond.wait()
                self.holder = who
                return True
            deadline = time.monotonic() + timeout
            while self.holder not in (None, who):
                left = deadline - time.monotonic()
                if left <= 0:
                    return False
                self._cond.wait(left)
            self.holder = who
            return True

    def release(self, who):
        with self._cond:
            if self.holder == who:
                self.holder = None
                self._cond.notify_all()

    def held(self):
        with self._cond:
            return self.holder is not None


class _Server(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        who = id(self.request)
        try:
            while True:
                line = self.rfile.readline()
                if not line:
                    return
                parts = line.decode("ascii").split()
                if not parts:
                    continue
                arbiter = self.server.arbiter
                if parts[0] == "LOCK":
                    timeout = None if parts[1] == "-" else float(parts[1])
                    ok = arbiter.acquire(who, timeout)
                    self._reply("OK" if ok else "TIMEOUT")
                elif parts[0] == "UNLOCK":
                    arbiter.release(who)
                    self._reply("OK")
                elif parts[0] == "HELD":
                    self._reply("YES" if arbiter.held() else "NO")
                else:
                    self._reply("ERR")
        except (ConnectionError, OSError, ValueError):
            return
        finally:
            self.server.arbiter.release(who)

    def _reply(self, text):
        self.wfile.write((text + "\n").encode("ascii"))
        self.wfile.flush()


class ArbiterClient:
    """仲裁器的客户端，接口和 FileLock 对齐。"""

    def __init__(self, socket_path, timeout=None):
        self.socket_path = socket_path
        self.timeout = timeout
        self._sock = None

    def acquire(self, timeout=None):
        if timeout is None:
            timeout = self.timeout
        arg = "-" if timeout is None else "%.6f" % float(timeout)
        return self._request("LOCK " + arg) == "OK"

    def release(self):
        if self._sock is not None:
            self._request("UNLOCK")

    def is_held(self):
        """现在有没有人持有。"""
        return self._request("HELD") == "YES"

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def _request(self, line):
        sock = self._connect()
        sock.sendall((line + "\n").encode("ascii"))
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(64)
            if not chunk:
                raise ConnectionError("arbiter connection closed")
            buf += chunk
        return buf.decode("ascii").strip()

    def _connect(self):
        if self._sock is None:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(max(30.0, float(self.timeout or 0) + 5.0))
            sock.connect(self.socket_path)
            self._sock = sock
        return self._sock
