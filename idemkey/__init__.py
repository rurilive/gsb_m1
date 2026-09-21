"""idemkey: 支付链路里按幂等键记住请求结果的小库。"""

from idemkey.store import IdempotencyStore

__all__ = ["IdempotencyStore"]
