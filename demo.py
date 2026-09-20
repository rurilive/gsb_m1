"""stackvm 演示：汇编 -> 反汇编 -> 执行，含 CALL/RET 递归子程序。"""

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

# 递归 fib：入口时栈顶为参数 n，返回时栈顶为 fib(n)。
# n 存进本帧局部段 0，每层调用帧的局部段相互隔离。
FIB = """
fib:
STORE_LOCAL 0      # 本帧的 n
LOAD_LOCAL 0
PUSH 2
LT                 # n < 2 ?
JZ rec
LOAD_LOCAL 0       # 基例：fib(n) = n
RET
rec:
LOAD_LOCAL 0
PUSH 2
SUB
CALL fib           # 压栈 fib(n-2)
LOAD_LOCAL 0
PUSH 1
SUB
CALL fib           # 压栈 fib(n-1)
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

    print("\n=== CALL/RET：递归 fib(10) ===")
    fib_code = assemble("PUSH 10\nCALL fib\nPRINT\nHALT\n" + FIB)
    call_ret = [line for line in disasm(fib_code).splitlines()
                if "CALL" in line or "RET" in line]
    print("  反汇编片段:", call_ret[0], "/", call_ret[-1])
    print("  output:", VM().run(fib_code))

    print("\n=== 调用栈深度上限：max_calls=10 时递归 fib(20) ===")
    deep = assemble("PUSH 20\nCALL fib\nPOP\nHALT\n" + FIB)
    try:
        VM(max_calls=10).run(deep)
    except CallOverflow as exc:
        print("  捕获 CallOverflow(VmError 子类):", exc)


if __name__ == "__main__":
    main()
