"""Cookie 值对象与 Set-Cookie 解析。"""

from datetime import datetime

_MONTHS = {
    "Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
    "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12,
}


class Cookie:
    """一条 cookie。expires 为过期时刻，可空。"""

    __slots__ = ("name", "value", "domain", "path", "expires", "secure", "http_only")

    def __init__(self, name, value, domain, path="/",
                 expires=None, secure=False, http_only=False):
        self.name = name
        self.value = value
        self.domain = domain
        self.path = path
        self.expires = expires
        self.secure = secure
        self.http_only = http_only

    def is_expired(self, now: datetime) -> bool:
        if self.expires is None:
            return False
        return now.timestamp() > self.expires.timestamp()

    def __repr__(self):
        flags = []
        if self.secure:
            flags.append("Secure")
        if self.http_only:
            flags.append("HttpOnly")
        return ("Cookie({}={}; domain={}; path={}; flags={})".format(
            self.name, self.value, self.domain, self.path,
            "|".join(flags) or "-"))


def parse_expires(value: str):
    """解析 Expires 字段（RFC 1123，形如 Wed, 21 Oct 2015 07:28:00 GMT）。"""
    parts = value.strip().split()
    if len(parts) < 5:
        return None
    try:
        day = int(parts[1])
        month = _MONTHS[parts[2]]
        year = int(parts[3])
        hh, mm, ss = (int(x) for x in parts[4].split(":"))
    except (KeyError, ValueError):
        return None
    return datetime(year, month, day, hh, mm, ss)


def parse_set_cookie(header: str) -> Cookie:
    """解析 Set-Cookie 头（网关收到上游响应时调用）。"""
    parts = [p.strip() for p in header.split(";")]
    name, _, value = parts[0].partition("=")
    cookie = Cookie(name, value, domain="", path="/")
    for attr in parts[1:]:
        key, _, val = attr.partition("=")
        key = key.lower()
        if key == "domain":
            cookie.domain = val.strip().lower()
        elif key == "path":
            cookie.path = val.strip() or "/"
        elif key == "expires":
            cookie.expires = parse_expires(val)
        elif key == "secure":
            cookie.secure = True
        elif key == "httponly":
            cookie.http_only = True
    return cookie
