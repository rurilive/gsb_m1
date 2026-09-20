"""CALL/RET 新行为测试：嵌套调用、局部段隔离、深度边界、RET 落点。"""

import unittest

from stackvm import CallOverflow, VM, VmError, assemble, disasm


class TestCallEncoding(unittest.TestCase):
    def test_call_ret_encoding(self):
        self.assertEqual(assemble("CALL sub\nHALT\nsub:\nRET\n"),
                         bytes([0x28, 0x04, 0x00, 0x27, 0x29]))

    def test_ret_rejects_operand(self):
        with self.assertRaises(VmError):
            assemble("RET 1")

    def test_call_requires_operand(self):
        with self.assertRaises(VmError):
            assemble("CALL")

    def test_disasm_roundtrip(self):
        src = "CALL sub\nHALT\nsub:\nRET\n"
        code = assemble(src)
        self.assertEqual(assemble(disasm(code)), code)
        self.assertEqual(disasm(code),
                         "0000  CALL 4\n0003  HALT\n0004  RET")


class TestCallReturn(unittest.TestCase):
    def test_call_returns_to_next_instruction(self):
        # 子程序 PRINT 一次；CALL 返回后必须落到其后的 PRINT，而非回到 CALL
        src = ("CALL sub\nPUSH 2\nPRINT\nHALT\n"
               "sub:\nPUSH 1\nPRINT\nRET\n")
        self.assertEqual(VM().run(assemble(src)), ["1", "2"])

    def test_nested_calls(self):
        # 调用顺序 main -> a -> b；按 PRINT 轨迹验证每层 RET 的落点
        src = ("PUSH 0\nPRINT\n"          # 0: main 开始
               "CALL a\n"
               "PUSH 4\nPRINT\n"          # 4: main 恢复
               "HALT\n"
               "a:\nPUSH 1\nPRINT\n"      # a 开始
               "CALL b\n"
               "PUSH 3\nPRINT\n"          # 3: a 恢复
               "RET\n"
               "b:\nPUSH 2\nPRINT\nRET\n")
        self.assertEqual(VM().run(assemble(src)),
                         ["0", "1", "2", "3", "4"])

    def test_arguments_via_shared_operand_stack(self):
        # 操作数栈跨帧共享：调用前压参数，子程序里运算，返回后取结果
        src = ("PUSH 20\nPUSH 22\nCALL add\nPRINT\nHALT\n"
               "add:\nADD\nRET\n")
        self.assertEqual(VM().run(assemble(src)), ["42"])

    def test_ret_from_main_frame_raises(self):
        with self.assertRaises(VmError):
            VM().run(assemble("RET"))

    def test_ret_from_main_after_calls_return_raises(self):
        # 所有 CALL 都 RET 回来后，栈帧应只剩主程序帧
        src = "CALL sub\nRET\nsub:\nRET\n"
        with self.assertRaises(VmError):
            VM().run(assemble(src))


class TestLocalIsolation(unittest.TestCase):
    def test_sub_locals_do_not_leak_to_caller(self):
        src = ("PUSH 7\nSTORE_LOCAL 0\n"
               "CALL sub\n"
               "LOAD_LOCAL 0\nPRINT\n"      # 主帧局部 0 仍是 7
               "HALT\n"
               "sub:\nPUSH 9\nSTORE_LOCAL 0\n"
               "LOAD_LOCAL 0\nPRINT\nRET\n")
        self.assertEqual(VM().run(assemble(src)), ["9", "7"])

    def test_uninitialized_local_in_fresh_frame_raises(self):
        src = ("PUSH 5\nSTORE_LOCAL 0\n"
               "CALL sub\nHALT\n"
               "sub:\nLOAD_LOCAL 0\nRET\n")
        with self.assertRaises(VmError):
            VM().run(assemble(src))

    def test_locals_isolated_between_sibling_calls(self):
        # 同一子程序连续两次调用：第二次拿不到第一次 STORE 的局部变量
        src = ("CALL sub\nCALL sub\nHALT\n"
               "sub:\nLOAD_LOCAL 0\nRET\n")
        with self.assertRaises(VmError):
            VM().run(assemble(src))

    def test_nested_locals_independent(self):
        # 主帧与两层子帧都使用 0 号局部，互不干扰
        src = ("PUSH 1\nSTORE_LOCAL 0\n"
               "CALL a\n"
               "LOAD_LOCAL 0\nPRINT\nHALT\n"
               "a:\nPUSH 2\nSTORE_LOCAL 0\n"
               "CALL b\n"
               "LOAD_LOCAL 0\nPRINT\nRET\n"
               "b:\nPUSH 3\nSTORE_LOCAL 0\n"
               "LOAD_LOCAL 0\nPRINT\nRET\n")
        self.assertEqual(VM().run(assemble(src)), ["3", "2", "1"])


class TestCallDepth(unittest.TestCase):
    def _chain_src(self, calls):
        # main -> f0 -> f1 -> ... 共 calls 层嵌套，每层在深层返回后 PRINT
        lines = ["CALL f0", "PUSH 99", "PRINT", "HALT"]
        for i in range(calls):
            lines.append("f%d:" % i)
            if i + 1 < calls:
                lines.append("CALL f%d" % (i + 1))
                lines.append("PUSH %d" % i)
                lines.append("PRINT")
            lines.append("RET")
        return "\n".join(lines)

    def test_depth_at_limit_allowed(self):
        # max_call_depth=2：允许 2 个子帧，最深帧里的第 3 个 CALL 才超限
        vm = VM(max_call_depth=2)
        output = vm.run(assemble(self._chain_src(2)))
        self.assertEqual(output, ["0", "99"])

    def test_depth_one_over_limit_overflows(self):
        with self.assertRaises(CallOverflow):
            VM(max_call_depth=2).run(assemble(self._chain_src(3)))

    def test_depth_boundary_zero(self):
        # max_call_depth=0：主程序帧之外一个 CALL 都不允许
        with self.assertRaises(CallOverflow):
            VM(max_call_depth=0).run(assemble("CALL sub\nHALT\nsub:\nRET\n"))

    def test_overflow_is_vm_error(self):
        self.assertTrue(issubclass(CallOverflow, VmError))

    def test_default_depth_blocks_deep_recursion(self):
        # 默认深度 64：无限递归（无基准分支）必然 CallOverflow 而非死循环
        src = "f:\nCALL f\nRET\n"
        with self.assertRaises(CallOverflow):
            VM().run(assemble(src))


class TestRecursiveFib(unittest.TestCase):
    # fib(n)：递归子程序，n 存局部段 0；基准分支 n<2 返回 n
    FIB = """
PUSH 10
CALL fib
PRINT
HALT
fib:
STORE_LOCAL 0
LOAD_LOCAL 0
PUSH 2
LT
JZ rec
LOAD_LOCAL 0
RET
rec:
LOAD_LOCAL 0
PUSH 1
SUB
CALL fib
LOAD_LOCAL 0
PUSH 2
SUB
CALL fib
ADD
RET
"""

    def test_fib_10(self):
        self.assertEqual(VM().run(assemble(self.FIB)), ["55"])

    def test_fib_too_shallow_depth(self):
        # 深度 3 跑不完 fib(10) 的最深递归路径
        with self.assertRaises(CallOverflow):
            VM(max_call_depth=3).run(assemble(self.FIB))


if __name__ == "__main__":
    unittest.main()
