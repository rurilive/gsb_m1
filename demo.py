"""chunkmime 现状演示。

同一份上传先用整块喂一遍,再按网络到达的块喂一遍,把两边解析
出来的东西摆在一起看;最后看一下带转义引号的 filename 现在的
样子。
"""

from chunkmime import MultipartParser, PartCollector
from chunkmime.headers import parse_params
from chunkmime.reference import parse_all

BOUNDARY = b"abc123"

TITLE_HEAD = (
    b'Content-Disposition: form-data; name="title"\r\n'
    b"Content-Type: text/plain"
)
UPLOAD_HEAD = (
    b'Content-Disposition: form-data; name="upload"; filename="%s"\r\n'
    b"Content-Type: application/octet-stream"
)


def build(body_of_upload, filename=b"note.txt"):
    """拼一份两字段的上传:title 文本 + upload 文件。"""
    out = bytearray()
    out += b"--" + BOUNDARY + b"\r\n" + TITLE_HEAD + b"\r\n\r\n"
    out += b"monthly upload"
    out += b"\r\n--" + BOUNDARY + b"\r\n" + UPLOAD_HEAD % filename + b"\r\n\r\n"
    out += body_of_upload
    out += b"\r\n--" + BOUNDARY + b"--\r\n"
    return bytes(out)


def run_chunked(body, cuts):
    collector = PartCollector()
    parser = MultipartParser(BOUNDARY, collector)
    pos = 0
    for cut in cuts:
        parser.feed(body[pos:cut])
        pos = cut
    parser.feed(body[pos:])
    parser.finish()
    return collector.parts()


def show(parts):
    if not parts:
        print("    (什么都没解析出来)")
    for i, part in enumerate(parts, 1):
        print("    %d. name=%r filename=%r 正文 %d 字节 %r"
              % (i, part.name, part.filename, len(part.data), part.data[:40]))


def compare(label, whole, chunked):
    if whole == chunked:
        print("  %s: 分块解析与整块解析一致" % label)
    else:
        print("  %s: 分块解析与整块解析对不上" % label)


def main():
    print("=== 1. 整块解析(小表单, 一切正常) ===")
    body = build(b"file payload")
    whole = run_chunked(body, [])
    show(whole)
    print("  整块结果同时和 reference 对过: %s"
          % (parse_all(body, BOUNDARY) == whole))

    print()
    print("=== 2. 文件正文里带着分隔行的半截前缀, 块正好切在那一截后面 ===")
    payload = b"payload-1\r\n--abc12 follows more bytes\r\npayload-2"
    body = build(payload)
    whole = run_chunked(body, [])
    cut = body.index(b"\r\n--abc12 ") + len(b"\r\n--abc12")
    print("  切点在第 %d 字节, 两边各喂一块" % cut)
    chunked = run_chunked(body, [cut])
    print("  整块:")
    show(whole)
    print("  分块:")
    show(chunked)
    compare("正文带半截前缀", whole, chunked)

    print()
    print("=== 3. 收尾分隔行被切成两块 ===")
    body = build(b"file payload")
    whole = run_chunked(body, [])
    cut = body.rindex(b"\r\n--abc123--\r\n") + len(b"\r\n--abc123")
    print("  切点在第 %d 字节, 收尾的 -- 落在第二块" % cut)
    chunked = run_chunked(body, [cut])
    print("  整块:")
    show(whole)
    print("  分块:")
    show(chunked)
    compare("收尾分隔行切开", whole, chunked)

    print()
    print("=== 4. 带转义引号的 filename ===")
    body = build(b"file payload", filename=b'a\\"b.txt')
    print("  整块解析出来: %r" % (run_chunked(body, [])[-1].filename,))
    print("  reference 算出: %r"
          % (parse_all(body, BOUNDARY)[-1].filename,))
    print("  直接过一遍参数解析: %r"
          % (parse_params('form-data; name="upload"; filename="a\\"b.txt"'),))


if __name__ == "__main__":
    main()
