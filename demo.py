"""三方合并基本用法演示（配置发布联调用的那套）。"""

from diff3x.diff3 import merge

base = """[service]
timeout = 30
retries = 3
endpoint = api.example.com
log_level = info
"""

a = """[service]
timeout = 45
retries = 3
endpoint = api.example.com
log_level = info
"""

b = """[service]
timeout = 30
retries = 5
endpoint = api.example.com
log_level = info
"""

result = merge(base, a, b)
print("clean:", result.clean)
print("--- 合并结果 ---")
print("\n".join(result.lines))
print("--- 冲突数:", len(result.conflicts))
