"""CookieJar：多线程网关共用的罐子，按 (name, domain, path) 存取。"""

import threading
from datetime import datetime, timezone
from urllib.parse import urlsplit

from .cookie import Cookie


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CookieJar:

    def __init__(self, clock=None):
        """clock 可注入，返回 aware datetime，便于测试。"""
        self._cookies = {}
        self._lock = threading.RLock()
        self._clock = clock or _utcnow

    def add(self, cookie: Cookie) -> None:
        """同 (name, domain, path) 已存在时覆盖。"""
        with self._lock:
            self._cookies[(cookie.name, cookie.domain, cookie.path)] = cookie

    def set_cookie(self, name, value, domain, path="/",
                   expires=None, secure=False, http_only=False) -> None:
        """便捷入口：构造 Cookie 并入罐。"""
        self.add(Cookie(name, value, domain, path, expires, secure, http_only))

    def remove(self, name, domain, path="/") -> None:
        with self._lock:
            self._cookies.pop((name, domain, path), None)

    def snapshot(self) -> list:
        """当前全部 cookie 的快照。"""
        with self._lock:
            return list(self._cookies.values())

    def match_for(self, url: str) -> list:
        """该请求应携带的 cookie，path 长的优先。"""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        path = parts.path or "/"
        scheme = parts.scheme.lower()
        now = self._clock()
        found = []
        with self._lock:
            for cookie in self._cookies.values():
                if cookie.is_expired(now):
                    continue
                if not _domain_match(host, cookie.domain):
                    continue
                if not _path_match(path, cookie.path):
                    continue
                if cookie.secure and scheme != "https":
                    continue
                found.append(cookie)
        found.sort(key=lambda c: len(c.path), reverse=True)
        return found

    def dump(self, path) -> None:
        """导出到 JSON，网关重启前调用。"""
        from .serial import dump
        dump(self, path)

    def load(self, path) -> None:
        """从 JSON 恢复，网关启动时调用。"""
        from .serial import load
        load(self, path)


def _domain_match(host: str, domain: str) -> bool:
    if not domain:
        return True
    domain = domain.lower()
    if host == domain:
        return True
    return host.endswith(domain)


def _path_match(request_path: str, cookie_path: str) -> bool:
    if not request_path:
        request_path = "/"
    return request_path.startswith(cookie_path)
