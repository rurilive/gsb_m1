"""ID 生成器演示。"""
from idgen import IdGenerator

g = IdGenerator()
for i in [g.next_id() for _ in range(5)]:
    print(i, "->", i >> 16, i & 0xFFFF)

# 第二段：多实例演示（留给实现者补）
