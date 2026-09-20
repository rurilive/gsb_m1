"""CALL/RET 调用帧语义测试：嵌套调用、局部段隔离、深度边界、RET 落点。"""

import unittest

from stackvm import CallOverflow, VM, VmError, assemble, disasm


def run(src, **kwargs):
    return VM(**kwargs).run(assemble(src))


class TestCallRet(unittest.TestCase):
    def test_simple_call_and_return(self):
        # 主程序调用子程序：子程序压 42 打印，返回后主程序压 7 打印
        src = ("CALL sub\nPUSH 7\nPRINT\nHALT\n"
               "sub:\nPUSH 42\nPRINT\nRET\n")
        self.assertEqual(run(src), ["42", "7"])

    def test_ret_lands_at_instruction_after_call(self):
        # RET 必须精确落在 CALL 的下一条指令上：两个 PUSH 都要执行
        src = ("CALL sub\nPUSH 1\nPRINT\nPUSH 2\nPRINT\nHALT\n"
               "sub:\nPUSH 0\nPRINT\nRET\n")
        self.assertEqual(run(src), ["0", "1", "2"])

    def test_nested_calls(self):
        # 主 -> a -> b，按 b、a、主的顺序各打印一个值
        src = ("CALL a\nPUSH 3\nPRINT\nHALT\n"
               "a:\nCALL b\nPUSH 2\nPRINT\nRET\n"
               "b:\nPUSH 1\nPRINT\nRET\n")
        self.assertEqual(run(src), ["1", "2", "3"])

    def test_subroutine_called_twice(self):
        # 同一子程序连续两次调用，验证每次 RET 回到各自的下一条指令
        src = ("CALL sub\nCALL sub\nHALT\n"
               "sub:\nPUSH 9\nPRINT\nRET\n")
        self.assertEqual(run(src), ["9", "9"])

    def test_loop_calling_subroutine(self):
        # CALL 在循环里反复执行：循环变量经操作数栈传参，子程序返回其两倍
        src = ("PUSH 0\nSTORE_LOCAL 0\n"
               "top:\nLOAD_LOCAL 0\nPUSH 3\nLT\nJZ end\n"
               "LOAD_LOCAL 0\nCALL twice\n"
               "LOAD_LOCAL 0\nPUSH 1\nADD\nSTORE_LOCAL 0\nJMP top\n"
               "end:\nHALT\n"
               "twice:\nDUP\nADD\nPRINT\nRET\n")
        self.assertEqual(run(src), ["0", "2", "4"])


class TestLocalIsolation(unittest.TestCase):
    def test_subroutine_locals_not_visible_to_caller(self):
        # 子程序写的局部 0 回到主程序后必须读不到（新 run 的主帧也是全新的）
        vm = VM()
        vm.run(assemble("CALL sub\nHALT\nsub:\nPUSH 55\nSTORE_LOCAL 0\nRET\n"))
        with self.assertRaises(VmError):
            vm.run(assemble("LOAD_LOCAL 0\nPRINT\nHALT"))

    def test_caller_locals_not_visible_to_callee(self):
        src = ("PUSH 11\nSTORE_LOCAL 0\nCALL sub\nHALT\n"
               "sub:\nLOAD_LOCAL 0\nPRINT\nRET\n")
        with self.assertRaises(VmError):
            run(src)

    def test_caller_locals_restored_after_return(self):
        # 子程序也写局部 0，返回后主程序看到的仍是自己的 11
        src = ("PUSH 11\nSTORE_LOCAL 0\nCALL sub\n"
               "LOAD_LOCAL 0\nPRINT\nHALT\n"
               "sub:\nPUSH 22\nSTORE_LOCAL 0\nLOAD_LOCAL 0\nPRINT\nRET\n")
        self.assertEqual(run(src), ["22", "11"])

    def test_each_sibling_call_gets_fresh_locals(self):
        # 两次调用之间局部段全新：第二次调用读不到第一次写入的编号
        src = ("CALL first\nCALL second\nHALT\n"
               "first:\nPUSH 1\nSTORE_LOCAL 5\nRET\n"
               "second:\nLOAD_LOCAL 5\nPRINT\nRET\n")
        with self.assertRaises(VmError):
            run(src)

    def test_deep_frames_have_independent_locals(self):
        # 每层帧都写同一个局部编号，返回时逐层恢复自己的值
        src = ("PUSH 1\nSTORE_LOCAL 0\nCALL a\n"
               "LOAD_LOCAL 0\nPRINT\nHALT\n"
               "a:\nPUSH 2\nSTORE_LOCAL 0\nCALL b\n"
               "LOAD_LOCAL 0\nPRINT\nRET\n"
               "b:\nPUSH 3\nSTORE_LOCAL 0\nLOAD_LOCAL 0\nPRINT\nRET\n")
        self.assertEqual(run(src), ["3", "2", "1"])


class TestCallDepth(unittest.TestCase):
    def test_depth_at_limit_succeeds(self):
        # max_calls=1：一次 CALL 合法，子程序 RET 后再次 CALL 仍合法
        src = ("CALL sub\nCALL sub\nHALT\n"
               "sub:\nPUSH 1\nPRINT\nRET\n")
        self.assertEqual(run(src, max_calls=1), ["1", "1"])

    def test_depth_over_limit_raises_call_overflow(self):
        # max_calls=1：a 里再 CALL b 时已有 1 帧，第 2 帧超限
        src = ("CALL a\nHALT\n"
               "a:\nCALL b\nRET\n"
               "b:\nPUSH 1\nPRINT\nRET\n")
        with self.assertRaises(CallOverflow):
            run(src, max_calls=1)

    def test_exact_boundary(self):
        # max_calls=2：主 -> a -> b 恰好 2 帧，刚好不超限
        src = ("CALL a\nHALT\n"
               "a:\nCALL b\nRET\n"
               "b:\nPUSH 1\nPRINT\nRET\n")
        self.assertEqual(run(src, max_calls=2), ["1"])

    def test_zero_max_calls_overflow(self):
        with self.assertRaises(CallOverflow):
            run("CALL sub\nHALT\nsub:\nRET\n", max_calls=0)

    def test_infinite_recursion_hits_default_limit(self):
        src = "f:\nCALL f\nRET\n"
        with self.assertRaises(CallOverflow):
            run(src)

    def test_infinite_recursion_respects_custom_limit(self):
        src = "f:\nCALL f\nRET\n"
        with self.assertRaises(CallOverflow):
            run(src, max_calls=5)

    def test_call_overflow_is_vm_error(self):
        self.assertTrue(issubclass(CallOverflow, VmError))
        with self.assertRaises(VmError):
            run("f:\nCALL f\nRET\n", max_calls=2)

    def test_frames_reset_between_runs(self):
        # 正常 RET 后主程序帧不残留；同 VM 再跑深递归仍按上限触发
        vm = VM(max_calls=1)
        self.assertEqual(vm.run(assemble("CALL sub\nHALT\nsub:\nPUSH 8\nPRINT\nRET\n")),
                         ["8"])
        with self.assertRaises(CallOverflow):
            vm.run(assemble("f:\nCALL f\nRET\n"))


class TestRetInMain(unittest.TestCase):
    def test_ret_in_main_raises_vm_error(self):
        with self.assertRaises(VmError):
            run("RET\n")
        with self.assertRaises(VmError):
            run("PUSH 1\nRET\n")


class TestCallEncoding(unittest.TestCase):
    def test_call_encoding(self):
        # CALL 占操作码 0x28 + u16 小端，RET 占 0x29
        self.assertEqual(assemble("CALL 3\nRET\n"),
                         bytes([0x28, 0x03, 0x00, 0x29]))

    def test_call_supports_label(self):
        src = "CALL sub\nHALT\nsub:\nPUSH 1\nPRINT\nRET\n"
        self.assertEqual(run(src), ["1"])

    def test_call_missing_operand(self):
        with self.assertRaises(VmError):
            assemble("CALL\n")

    def test_ret_rejects_operand(self):
        with self.assertRaises(VmError):
            assemble("RET 1\n")

    def test_disasm_roundtrip(self):
        src = "CALL sub\nHALT\nsub:\nRET\n"
        code = assemble(src)
        text = disasm(code)
        self.assertIn("CALL", text)
        self.assertIn("RET", text)
        self.assertEqual(assemble(disasm(code)), code)
        self.assertEqual(VM().run(assemble(disasm(code))), [])


if __name__ == "__main__":
    unittest.main()
