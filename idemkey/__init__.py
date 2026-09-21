"""idemkey: 支付链路里按幂等键记住请求结果的小库。"""

from idemkey.store import IdempotencyStore, TruncatedResult

__all__ = ["IdempotencyStore", "TruncatedResult"]
