"""演示：一个令牌桶的基本借还。用 FakeClock 手动推进时钟观察补充与拒绝。"""
from bucketd import FakeClock, TokenBucket


def main():
    clock = FakeClock(start=1000.0)
    bucket = TokenBucket(rate=2.0, burst=10.0, clock=clock)

    print("=== 连续取 10 个（burst 内应全放行） ===")
    for i in range(10):
        print(f"  第{i + 1}个: {'放行' if bucket.try_allow() else '拒绝'}")
    print(f"  第11个: {'放行' if bucket.try_allow() else '拒绝'}（余额已空）")

    print("\n=== 推进 3 秒后（rate=2/s） ===")
    clock.advance(3.0)
    print(f"  当前余额: {bucket.available():.1f}")
    for i in range(3):
        print(f"  第{i + 1}个: {'放行' if bucket.try_allow() else '拒绝'}")

    print("\n=== 一次扣 5 个的大额请求 ===")
    print(f"  结果: {'放行' if bucket.try_allow(5) else '拒绝'}")
    print("演示结束")


if __name__ == "__main__":
    main()
