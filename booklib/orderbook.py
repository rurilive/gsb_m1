"""booklib.orderbook：朴素订单簿（改造前基线）。

FlatBook 用两张订单列表分别存放买盘与卖盘，一切查询都靠线性扫描：
问最优价要扫全表，累加价位数量要扫全表，撤销也要扫全表。
订单一旦变多，每次取最优价都会白扫一遍，而且它根不支持撮合。
"""

BUY = "buy"
SELL = "sell"

_SIDES = (BUY, SELL)


class BookError(Exception):
    """订单簿相关异常的统一基类。"""


class FlatBook:
    """朴素订单簿：买卖各一条订单列表，所有操作线性扫描。"""

    def __init__(self):
        self._bids = []
        self._asks = []
        self._seq = 0

    def _book(self, side):
        if side == BUY:
            return self._bids
        if side == SELL:
            return self._asks
        raise BookError("未知的买卖方向: %r" % (side,))

    def add(self, side, price, qty):
        """追加一条订单，返回它的订单号。"""
        if side not in _SIDES:
            raise BookError("未知的买卖方向: %r" % (side,))
        if price < 0:
            raise BookError("价格不能为负数: %r" % (price,))
        if qty <= 0:
            raise BookError("数量必须为正: %r" % (qty,))
        self._seq += 1
        order_id = self._seq
        self._book(side).append((order_id, price, qty))
        return order_id

    def best_bid(self):
        """买盘最高价；空盘返回 None。线性扫描。"""
        best = None
        for _, price, _ in self._bids:
            if best is None or price > best:
                best = price
        return best

    def best_ask(self):
        """卖盘最低价；空盘返回 None。线性扫描。"""
        best = None
        for _, price, _ in self._asks:
            if best is None or price < best:
                best = price
        return best

    def qty_at(self, side, price):
        """该价位上的订单总量。线性累加。"""
        total = 0
        for _, p, qty in self._book(side):
            if p == price:
                total += qty
        return total

    def cancel(self, order_id):
        """按订单号撤销；撤销成功返回 True，不存在返回 False。线性查找。"""
        for book in (self._bids, self._asks):
            for i, (oid, _, _) in enumerate(book):
                if oid == order_id:
                    book.pop(i)
                    return True
        return False

    def orders(self, side):
        """该侧的订单快照，按加入先后给出。"""
        return [(oid, price, qty) for oid, price, qty in self._book(side)]

    def __len__(self):
        return len(self._bids) + len(self._asks)
