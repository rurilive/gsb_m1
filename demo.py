"""unseal 现状演示：正常包先走一遍，再把审计翻出来的几段现场摆出来。

每段都关在临时目录里，不外溢；带“期望”的那行是修好之后该有的样子，
跑在现在的代码上多半对不上。
"""

import os
import tempfile

from unseal import KIND_DIR, KIND_SYMLINK, Extractor
from unseal.reference import Forged, forge_tar, forge_zip


def normal_zip():
    print("=== 场景一：一个正常的小 zip ===")
    with tempfile.TemporaryDirectory(prefix="unseal-demo-") as tmp:
        path = os.path.join(tmp, "pack.zip")
        forge_zip(path, [
            Forged("readme.txt", data=b"hello unseal"),
            Forged("docs/", kind=KIND_DIR),
            Forged("docs/guide.txt", data=b"guide"),
        ])
        report = Extractor(os.path.join(tmp, "dest")).run(path)
        print("   %s" % report.summary())


def normal_tar():
    print("=== 场景二：一个正常的小 tar，里面有个包内软链 ===")
    with tempfile.TemporaryDirectory(prefix="unseal-demo-") as tmp:
        path = os.path.join(tmp, "pack.tar")
        forge_tar(path, [
            Forged("data/", kind=KIND_DIR),
            Forged("data/real.txt", data=b"payload"),
            Forged("data/soft", kind=KIND_SYMLINK, target="real.txt"),
        ])
        dest = os.path.join(tmp, "dest")
        report = Extractor(dest).run(path)
        print("   %s" % report.summary())
        link = os.path.join(dest, "data", "soft")
        with open(link, "rb") as handle:
            landed = handle.read()
        print("   data/soft 指向 %r，跟链读到 %r" % (os.readlink(link), landed))


def scene_parent_escape():
    print("=== 场景三：条目名里带 .. 的包 ===")
    with tempfile.TemporaryDirectory(prefix="unseal-demo-") as tmp:
        path = os.path.join(tmp, "evil.zip")
        forge_zip(path, [
            Forged("docs/readme.txt", data=b"ok"),
            Forged("../escaped.txt", data=b"landed outside"),
        ])
        report = Extractor(os.path.join(tmp, "dest")).run(path)
        print("   %s" % report.summary())
        print("   目标目录外多出 escaped.txt：%s"
              % os.path.exists(os.path.join(tmp, "escaped.txt")))
        print("   期望：拒掉这条，外面干净")


def scene_link_write_through():
    print("=== 场景四：先落一条指向外面的软链，再顺着它写 ===")
    with tempfile.TemporaryDirectory(prefix="unseal-demo-") as tmp:
        outside = os.path.join(tmp, "outside")
        os.makedirs(outside)
        path = os.path.join(tmp, "evil.tar")
        forge_tar(path, [
            Forged("data/", kind=KIND_DIR),
            Forged("data/out", kind=KIND_SYMLINK, target=outside),
            Forged("data/out/planted.txt", data=b"planted"),
        ])
        report = Extractor(os.path.join(tmp, "dest")).run(path)
        planted = os.path.join(outside, "planted.txt")
        print("   %s" % report.summary())
        print("   外面被写了 planted.txt：%s" % os.path.exists(planted))
        print("   期望：这条软链整条拒掉，外面干净")


def scene_half_file():
    print("=== 场景五：上次中断留下的半截文件 ===")
    with tempfile.TemporaryDirectory(prefix="unseal-demo-") as tmp:
        payload = b"id,name\n1,alpha\n2,beta\n"
        path = os.path.join(tmp, "pack.zip")
        forge_zip(path, [Forged("report.csv", data=payload)])
        dest = os.path.join(tmp, "dest")
        os.makedirs(dest)
        with open(os.path.join(dest, "report.csv"), "wb") as handle:
            handle.write(payload[:8])
        report = Extractor(dest).run(path)
        landed = os.path.getsize(os.path.join(dest, "report.csv"))
        print("   %s" % report.summary())
        print("   盘上现在是 %d 字节，包里有 %d 字节" % (landed, len(payload)))
        print("   期望：补齐或重写，不许当成完整跳过")


def scene_declared_size():
    print("=== 场景六：声明尺寸和实际不符的包 ===")
    with tempfile.TemporaryDirectory(prefix="unseal-demo-") as tmp:
        payload = b"\0" * (256 * 1024)
        path = os.path.join(tmp, "bomb.zip")
        forge_zip(path, [Forged("big.bin", data=payload, declared=1 << 30)])
        dest = os.path.join(tmp, "dest")
        report = Extractor(dest, max_entry_bytes=1 << 20).run(path)
        print("   声明 1 GiB，单条上限 1 MiB，实写 %d 字节" % report.bytes)
        print("   期望：看声明就该拒，一个字节都不写")


def main():
    for scene in (normal_zip, normal_tar, scene_parent_escape,
                  scene_link_write_through, scene_half_file,
                  scene_declared_size):
        scene()
        print()


if __name__ == "__main__":
    main()
