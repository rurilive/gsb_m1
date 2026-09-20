"""虚拟机执行核心：decode -> dispatch，全局段 / 操作数栈 / 局部段。"""

from stackvm.errors import VmError
from stackvm.opcodes import BY_CODE, OPS


class VM:
    """栈式虚拟机。内存分三块：

    - 全局段 globals：构造时定长的槽位列表，跨 run 保留
    - 操作数栈：指令间传值，run 开始时清空
    - 局部段 locals：按编号存取的临时变量，run 开始时清空
    """

    def __init__(self, globals_size=16, max_steps=100000):
        self.globals = [0] * globals_size
        self.max_steps = max_steps
        self.output = []
        self._stack = []
        self._locals = {}
        self._pc = 0
        self._prog = b""
        # 分发表由编码表驱动：每个操作码对应一个 _op_<小写名称> 方法
        self._dispatch = {name: getattr(self, "_op_" + name.lower()) for name in OPS}

    def run(self, program):
        """执行字节码直到 HALT，返回输出列表（元素为字符串）。

        程序没有 HALT 就跑出末尾、或步数超过 max_steps，都抛 VmError。
        """
        self._prog = program
        self._stack = []
        self._locals = {}
        self.output = []
        self._pc = 0
        steps = 0
        while True:
            if self._pc >= len(program):
                raise VmError("程序计数器越界: %#06x" % self._pc)
            name, arg, next_pc = self._decode(self._pc)
            self._pc = next_pc  # 跳转类指令在处理器里改写 self._pc
            self._dispatch[name](arg)
            steps += 1
            if steps > self.max_steps:
                raise VmError("超过最大步数 %d，疑似死循环" % self.max_steps)
            if name == "HALT":
                return self.output

    def _decode(self, pc):
        op = self._prog[pc]
        if op not in BY_CODE:
            raise VmError("未知操作码 %#04x @ %#06x" % (op, pc))
        name, layout = BY_CODE[op]
        if layout == "u16":
            if pc + 3 > len(self._prog):
                raise VmError("%s 操作数被截断 @ %#06x" % (name, pc))
            return name, int.from_bytes(self._prog[pc + 1:pc + 3], "little"), pc + 3
        return name, None, pc + 1

    def _pop(self):
        if not self._stack:
            raise VmError("操作数栈下溢")
        return self._stack.pop()

    # ---- 处理器：名称必须与编码表一致（_op_ + 小写助记符） ----

    def _op_push(self, arg):
        self._stack.append(arg)

    def _op_pop(self, arg):
        self._pop()

    def _op_dup(self, arg):
        if not self._stack:
            raise VmError("操作数栈下溢: DUP")
        self._stack.append(self._stack[-1])

    def _binary(self, fn):
        b = self._pop()
        a = self._pop()
        self._stack.append(fn(a, b))

    def _op_add(self, arg):
        self._binary(lambda a, b: a + b)

    def _op_sub(self, arg):
        self._binary(lambda a, b: a - b)

    def _op_mul(self, arg):
        self._binary(lambda a, b: a * b)

    def _op_eq(self, arg):
        b = self._pop()
        self._stack.append(self._pop() == b)

    def _op_lt(self, arg):
        self._binary(lambda a, b: a < b)

    def _op_gt(self, arg):
        self._binary(lambda a, b: a > b)

    def _op_jmp(self, arg):
        self._pc = arg

    def _op_jz(self, arg):
        if not self._pop():
            self._pc = arg

    def _check_slot(self, arg):
        if not 0 <= arg < len(self.globals):
            raise VmError("全局段槽位越界: %d（共 %d 槽）" % (arg, len(self.globals)))

    def _op_load_g(self, arg):
        self._check_slot(arg)
        self._stack.append(self.globals[arg])

    def _op_store_g(self, arg):
        self._check_slot(arg)
        self.globals[arg] = self._pop()

    def _op_load_local(self, arg):
        if arg not in self._locals:
            raise VmError("读取未初始化的局部变量 %d" % arg)
        self._stack.append(self._locals[arg])

    def _op_store_local(self, arg):
        self._locals[arg] = self._pop()

    def _op_print(self, arg):
        self.output.append(str(self._pop()))

    def _op_halt(self, arg):
        pass
