"""argmini 的线上使用样子（demo 输出格式别动）。"""

from argmini import ArgsError, Parser

p = Parser("pack", "打包工具")
p.add("-v", "--verbose", action="store_true", help="详细输出")
p.add("-o", "--out", default="a.out", help="输出文件")
p.add("--level", type=int, default=1, help="压缩等级")
p.add("-I", "--include", action="append", help="包含目录")
p.add("src", help="源文件")
p.add("files", nargs="*", help="更多文件")

args = p.parse(["-v", "-I", "inc1", "--include=inc2", "--level=9",
                "-o", "x.bin", "a.txt", "b.txt", "c.txt"])
print("verbose:", args["verbose"])
print("out:", args["out"])
print("level:", args["level"])
print("include:", args["include"])
print("src:", args["src"])
print("files:", args["files"])

try:
    p.parse(["--level=abc", "a.txt"])
except ArgsError as e:
    print("error:", e)

try:
    p.parse(["--frob", "a.txt"])
except ArgsError as e:
    print("error:", e)

try:
    p.parse([])
except ArgsError as e:
    print("error:", e)

print("--- help ---")
print(p.help())
