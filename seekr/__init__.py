"""seekr: 内存里的朴素子串检索。

当前只有逐文档扫子串的实现，见 seekr/scan.py。
分词与倒排、布尔检索、短语检索、评分排序、取词位置与增删一致性
见任务描述。
"""

from seekr.scan import Corpus

__all__ = ["Corpus"]
