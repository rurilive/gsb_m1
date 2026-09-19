"""cookiest 现状演示：会话签发、请求匹配、重启恢复。"""

import os
import tempfile

from cookiest import CookieJar, parse_set_cookie


def main():
    jar = CookieJar()
    jar.add(parse_set_cookie(
        "sessionid=s-7f3a; Domain=example.com; Path=/; Secure; HttpOnly"))
    jar.add(parse_set_cookie("csrf=tok-1; Domain=example.com; Path=/pay"))
    jar.add(parse_set_cookie("theme=dark; Domain=example.com; Path=/"))

    print("=== 各请求携带的 cookie ===")
    for url in ["https://www.example.com/index",
                "https://evil-example.com/index",
                "https://www.example.com/pay/confirm",
                "https://www.example.com/paypal/checkout"]:
        names = [c.name for c in jar.match_for(url)]
        print(f"  {url}  ->  {names}")

    print("\n=== 会话过期时间 ===")
    sess = jar.match_for("https://www.example.com/index")[0]
    print(f"  {sess.name}: expires = {sess.expires}")

    print("\n=== 重启恢复 ===")
    path = os.path.join(tempfile.mkdtemp(prefix="cookiest-"), "cookies.json")
    jar.dump(path)
    jar2 = CookieJar()
    jar2.load(path)
    for c in jar2.snapshot():
        print(f"  {c.name}: secure={c.secure} http_only={c.http_only}")


if __name__ == "__main__":
    main()
