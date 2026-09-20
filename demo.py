"""stackvm 现状演示：汇编 -> 反汇编 -> 执行。"""

from stackvm import VM, assemble, disasm

SUM10 = """
# 求 1+2+...+10，结果存全局段 0 号槽
PUSH 0
STORE_G 0      # 累加器
PUSH 1
STORE_G 1      # i
loop:
LOAD_G 1
PUSH 10
GT             # i > 10 ?
JZ body        # 还没超过就继续循环
JMP done
body:
LOAD_G 0
LOAD_G 1
ADD
STORE_G 0
LOAD_G 1
PUSH 1
ADD
STORE_G 1
JMP loop
done:
LOAD_G 0
PRINT
HALT
"""

ORDER = """
# 演示局部段：算 (20+22)*2
PUSH 20
STORE_LOCAL 0
PUSH 22
STORE_LOCAL 1
LOAD_LOCAL 0
LOAD_LOCAL 1
ADD
PUSH 2
MUL
PRINT
HALT
"""


def main():
    print("=== SUM10 反汇编（前 6 行） ===")
    code = assemble(SUM10)
    print("\n".join(disasm(code).splitlines()[:6]))

    print("\n=== 执行 SUM10 ===")
    vm = VM()
    print("  output:", vm.run(code), " globals[0]:", vm.globals[0])

    print("\n=== 执行 ORDER（局部段用法） ===")
    print("  output:", VM().run(assemble(ORDER)))

    # TODO(下个版本): CALL/RET 落地后，在这里加一段递归程序（比如 fib），
    # 演示调用帧、局部段隔离与调用栈深度上限的报错路径。


if __name__ == "__main__":
    main()
