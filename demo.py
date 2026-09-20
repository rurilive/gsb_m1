"""stackvm 现状演示：汇编 -> 反汇编 -> 执行。"""

from stackvm import CallOverflow, VM, assemble, disasm

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

FIB = """
# 递归 fib(n)：n 存本帧局部段 0；n < 2 时直接返回 n，
# 否则递归 fib(n-1) 与 fib(n-2) 后 ADD。
# 每次 CALL 都是全新局部段，所以两层递归互不踩 n。
PUSH 10
CALL fib
PRINT
HALT
fib:
STORE_LOCAL 0        # 参数 n 落在当前帧的局部段
LOAD_LOCAL 0
PUSH 2
LT
JZ rec
LOAD_LOCAL 0
RET                  # 基准分支：返回 n
rec:
LOAD_LOCAL 0
PUSH 1
SUB
CALL fib             # fib(n-1)
LOAD_LOCAL 0
PUSH 2
SUB
CALL fib             # fib(n-2)，本帧的局部段 0 仍是 n
ADD
RET
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

    print("\n=== CALL/RET 反汇编（fib 前 5 行） ===")
    fib_code = assemble(FIB)
    print("\n".join(disasm(fib_code).splitlines()[:5]))

    print("\n=== 执行递归 fib(10)（调用帧 + 局部段隔离） ===")
    vm = VM()
    print("  output:", vm.run(fib_code))

    print("\n=== 调用栈深度上限（max_call_depth=3 跑 fib 触发 CallOverflow） ===")
    try:
        VM(max_call_depth=3).run(fib_code)
    except CallOverflow as exc:
        print("  CallOverflow:", exc)


if __name__ == "__main__":
    main()
