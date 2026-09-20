"""stackvm 现有行为的锁定测试。"""

import unittest

from stackvm import VM, VmError, assemble, disasm


class TestAssemble(unittest.TestCase):
    def test_simple_encoding(self):
        self.assertEqual(assemble("PUSH 1\nHALT"), bytes([0x10, 0x01, 0x00, 0x27]))

    def test_operand_little_endian(self):
        self.assertEqual(assemble("PUSH 258"), bytes([0x10, 0x02, 0x01]))

    def test_comments_and_blank_lines(self):
        src = "# 注释\nPUSH 2  # 行内注释\n\nHALT\n"
        self.assertEqual(assemble(src), assemble("PUSH 2\nHALT"))

    def test_labels_forward_and_backward(self):
        src = "JMP skip\nPUSH 9\nPRINT\nskip:\nHALT\n"
        code = assemble(src)
        vm = VM()
        self.assertEqual(vm.run(code), [])

    def test_backward_label_loop(self):
        src = ("PUSH 0\nSTORE_LOCAL 0\n"
               "top:\nLOAD_LOCAL 0\nPUSH 3\nLT\nJZ end\n"
               "LOAD_LOCAL 0\nPRINT\nLOAD_LOCAL 0\nPUSH 1\nADD\nSTORE_LOCAL 0\n"
               "JMP top\nend:\nHALT\n")
        self.assertEqual(VM().run(assemble(src)), ["0", "1", "2"])

    def test_unknown_mnemonic(self):
        with self.assertRaises(VmError):
            assemble("FROB 1")

    def test_missing_operand(self):
        with self.assertRaises(VmError):
            assemble("PUSH")

    def test_operand_on_no_operand_op(self):
        with self.assertRaises(VmError):
            assemble("HALT 3")

    def test_operand_out_of_range(self):
        with self.assertRaises(VmError):
            assemble("PUSH 65536")
        with self.assertRaises(VmError):
            assemble("JMP -1")

    def test_unknown_label(self):
        with self.assertRaises(VmError):
            assemble("JMP nowhere")

    def test_disasm_offset_column_ignored_on_reassemble(self):
        code = assemble("PUSH 5\nDUP\nADD\nPRINT\nHALT")
        again = assemble(disasm(code))
        self.assertEqual(code, again)


class TestDisasm(unittest.TestCase):
    def test_text_format(self):
        text = disasm(assemble("PUSH 7\nPRINT\nHALT"))
        self.assertEqual(text, "0000  PUSH 7\n0003  PRINT\n0004  HALT")

    def test_unknown_opcode(self):
        with self.assertRaises(VmError):
            disasm(bytes([0x00]))

    def test_truncated_operand(self):
        with self.assertRaises(VmError):
            disasm(bytes([0x10, 0x01]))

    def test_disasm_matches_source_semantics(self):
        src = "PUSH 3\nPUSH 4\nADD\nPRINT\nHALT"
        self.assertEqual(VM().run(assemble(disasm(assemble(src)))), ["7"])


class TestArith(unittest.TestCase):
    def run_src(self, src):
        return VM().run(assemble(src))

    def test_add_sub_mul(self):
        self.assertEqual(self.run_src("PUSH 10\nPUSH 4\nSUB\nPRINT\nHALT"), ["6"])
        self.assertEqual(self.run_src("PUSH 6\nPUSH 7\nMUL\nPRINT\nHALT"), ["42"])
        self.assertEqual(self.run_src("PUSH 2\nPUSH 3\nADD\nPRINT\nHALT"), ["5"])

    def test_eq_lt_gt_push_bools(self):
        self.assertEqual(self.run_src("PUSH 1\nPUSH 1\nEQ\nPRINT\nHALT"), ["True"])
        self.assertEqual(self.run_src("PUSH 1\nPUSH 2\nLT\nPRINT\nHALT"), ["True"])
        self.assertEqual(self.run_src("PUSH 1\nPUSH 2\nGT\nPRINT\nHALT"), ["False"])

    def test_dup_and_pop(self):
        self.assertEqual(self.run_src("PUSH 5\nDUP\nADD\nPRINT\nHALT"), ["10"])
        self.assertEqual(self.run_src("PUSH 5\nPUSH 6\nPOP\nPRINT\nHALT"), ["5"])


class TestControlFlow(unittest.TestCase):
    def test_halt_stops_execution(self):
        # HALT 之后的字节不会执行（哪怕是垃圾）
        code = assemble("HALT") + bytes([0x00])
        self.assertEqual(VM().run(code), [])

    def test_falling_off_end_raises(self):
        with self.assertRaises(VmError):
            VM().run(assemble("PUSH 1"))

    def test_jz_jumps_on_false(self):
        src = "PUSH 0\nJZ skip\nPUSH 1\nPRINT\nskip:\nPUSH 2\nPRINT\nHALT"
        self.assertEqual(VM().run(assemble(src)), ["2"])

    def test_jz_falls_through_on_true(self):
        src = "PUSH 1\nJZ skip\nPUSH 1\nPRINT\nskip:\nHALT"
        self.assertEqual(VM().run(assemble(src)), ["1"])

    def test_pc_out_of_range_via_jmp(self):
        code = assemble("PUSH 1\nJMP 500")
        with self.assertRaises(VmError):
            VM().run(code)

    def test_max_steps(self):
        vm = VM(max_steps=100)
        with self.assertRaises(VmError):
            vm.run(assemble("loop:\nJMP loop"))

    def test_stack_underflow(self):
        with self.assertRaises(VmError):
            VM().run(assemble("ADD"))
        with self.assertRaises(VmError):
            VM().run(assemble("PRINT"))

    def test_unknown_opcode_in_run(self):
        with self.assertRaises(VmError):
            VM().run(bytes([0x7F]))


class TestSegments(unittest.TestCase):
    def test_globals_roundtrip(self):
        src = "PUSH 33\nSTORE_G 2\nLOAD_G 2\nPRINT\nHALT"
        vm = VM()
        self.assertEqual(vm.run(assemble(src)), ["33"])

    def test_globals_slot_out_of_range(self):
        with self.assertRaises(VmError):
            VM().run(assemble("PUSH 1\nSTORE_G 16"))
        with self.assertRaises(VmError):
            VM(globals_size=4).run(assemble("LOAD_G 4"))

    def test_globals_survive_across_runs(self):
        vm = VM()
        vm.run(assemble("PUSH 7\nSTORE_G 0\nHALT"))
        self.assertEqual(vm.globals[0], 7)
        self.assertEqual(vm.run(assemble("LOAD_G 0\nPRINT\nHALT")), ["7"])

    def test_locals_roundtrip(self):
        src = "PUSH 9\nSTORE_LOCAL 3\nLOAD_LOCAL 3\nPRINT\nHALT"
        self.assertEqual(VM().run(assemble(src)), ["9"])

    def test_unset_local_read_raises(self):
        with self.assertRaises(VmError):
            VM().run(assemble("LOAD_LOCAL 0"))

    def test_stack_and_locals_cleared_between_runs(self):
        vm = VM()
        vm.run(assemble("PUSH 1\nSTORE_LOCAL 0\nHALT"))
        self.assertEqual(vm.output, [])
        with self.assertRaises(VmError):
            vm.run(assemble("LOAD_LOCAL 0"))

    def test_output_is_fresh_list_per_run(self):
        vm = VM()
        first = vm.run(assemble("PUSH 1\nPRINT\nHALT"))
        second = vm.run(assemble("PUSH 2\nPRINT\nHALT"))
        self.assertEqual(first, ["1"])
        self.assertEqual(second, ["2"])


if __name__ == "__main__":
    unittest.main()
