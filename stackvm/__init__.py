"""stackvm: 内嵌栈式虚拟机，自带汇编与反汇编。"""

from stackvm.asm import assemble, disasm
from stackvm.errors import CallOverflow, VmError
from stackvm.vm import VM

__all__ = ["VM", "assemble", "disasm", "VmError", "CallOverflow"]
