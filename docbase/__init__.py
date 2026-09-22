"""docbase：工单知识库用的本地文档模块。"""

from .library import DocLibrary
from .text import chunks, is_cjk, tokens

__all__ = ["DocLibrary", "chunks", "is_cjk", "tokens"]
