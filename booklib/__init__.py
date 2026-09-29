"""booklib：一个纯标准库的订单簿包。

眼下只提供最朴素的订单簿 FlatBook：买卖各一条订单列表，
所有查询都靠线性扫描，既不聚合价位，也不能撮合。
"""

from .orderbook import BUY, SELL, BookError, FlatBook

__all__ = ["BUY", "SELL", "BookError", "FlatBook"]
