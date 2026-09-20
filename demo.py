"""idemretry 演示：幂等提交、同键回放、瞬时故障重试。"""

from idemretry import IdempotentClient, TransientError


class Downstream:
    """假的扣款下游：记下收到的每一笔，按 payload 先抖几下再成功。"""

    def __init__(self):
        self.seen = []
        self.flaky = {}

    def __call__(self, key, payload):
        self.seen.append((key, payload))
        left = self.flaky.get(payload, 0)
        if left:
            self.flaky[payload] = left - 1
            raise TransientError("下游抖动")
        return {"accepted": payload}


def main():
    downstream = Downstream()
    client = IdempotentClient(downstream, ttl=60.0, max_attempts=3)

    print("=== 1. 首次提交 ===")
    print("  回执:", client.submit("order-1001", "扣款 100"))

    print("=== 2. 幂等窗口内同键重复提交 ===")
    print("  回执:", client.submit("order-1001", "扣款 100"))
    print("  下游真正收到:", len(downstream.seen), "笔")

    print("=== 3. 瞬时故障自动重试 ===")
    downstream.flaky["扣款 200"] = 1
    print("  回执:", client.submit("order-1002", "扣款 200"))

    print("演示结束")


if __name__ == "__main__":
    main()
