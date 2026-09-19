"""演示：把几段字节流喂给解码器，打印解出的文本与 consumed。"""
from utf8stream import Utf8Decoder


def show(title, chunks, errors="replace"):
    dec = Utf8Decoder(errors=errors)
    parts = [dec.feed(c) for c in chunks]
    parts.append(dec.flush())
    text = "".join(parts)
    print("=== %s ===" % title)
    for c in chunks:
        print("  feed(%r)" % c)
    print("  -> %r    consumed=%d" % (text, dec.consumed))


def main():
    zh = "网关流式转码完成".encode()
    show("单块 ASCII", [b"hello gateway"])
    show("中文按块拆开", [zh[:5], zh[5:]])
    show("带 BOM 的流", [b"\xef\xbb\xbf\xef\xbb\xbf" + "带字节序标记".encode()])
    show("emoji", ["告警：服了🔥".encode()])
    show("含非法字节", [b"ok\xffmore"])
    print("演示结束")


if __name__ == "__main__":
    main()
