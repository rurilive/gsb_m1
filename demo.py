"""packlex 现状演示。

第一段：用朴素恒等编码把一段文字编码再解码，看输出长度与还原结果。
第二段：预留的字典式压缩与解码还原演示位子（见文末注释）。
"""

from packlex import IdentityCodec


def main():
    print("=== 朴素恒等编码（现有能力） ===")
    codec = IdentityCodec()
    text = b"packlex packlex packlex, a tiny byte codec"
    encoded = codec.encode(text)
    print("  原始长度 ->", len(text))
    print("  编码长度 ->", len(encoded))
    print("  长度不变 ->", len(encoded) == len(text))
    print("  编码结果 ->", encoded)
    decoded = codec.decode(encoded)
    print("  解码还原 ->", decoded)
    print("  往返一致 ->", decoded == text)

    # TODO(字典压缩改造): 字典式压缩就位后在这里补一段演示：
    # 编码一段有明显重复的字节，打印原始长度与压缩后长度，直观看出压缩
    # 后更短；再对同一段做解码，打印还原结果并确认与原始逐字节一致。
    # 可以顺带打印一次回溯引用解出的片段与滑动窗口的边界效果，让压缩率
    # 与无损还原这两点直接看得见。


if __name__ == "__main__":
    main()
