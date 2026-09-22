"""缓存与直连上游的对拍。

build_trace 用固定种子生成一串请求（先推进时钟再查域名），run_diff
把同一串请求跑两遍：一遍不经过缓存、每条都打上游，作为参考；一遍走
ResolverCache。两边的返回逐条比对，同时统计各自打了几次上游，缓存的
调用数必须压到直连的 RATIO_BOUND 以内。

请求序列先生成好再回放，生成用的随机数跟被测实现内部用的随机数互不
干扰，同一个种子永远得到同一串请求。
"""

import random

from .cache import ResolverCache
from .clock import ManualClock
from .upstream import Answer, FakeUpstream, UpstreamError

DEFAULT_SEED = 20260921
DEFAULT_STEPS = 600
HEALTHY_DOMAINS = 60
POISONED_DOMAINS = 6
REPEAT_PROBABILITY = 0.85
GAP_CHOICES = (0.0, 1.0, 2.0)
RATIO_BOUND = 0.6
START_TIME = 1000.0
MAX_REPORTED_MISMATCHES = 10

HEALTHY_TTL_RANGE = (20, 40)
POISONED_TTL = 15.0


def build_zone(rng):
    """造一份 zone：多数域名正常，少数几个标成一直解析失败。"""
    zone = {}
    failing = []
    for i in range(HEALTHY_DOMAINS):
        name = "node%02d.svc.internal" % i
        ttl = float(rng.randint(HEALTHY_TTL_RANGE[0], HEALTHY_TTL_RANGE[1]))
        zone[name] = ("10.0.%d.%d" % (i // 250, i % 250 + 1), ttl)
    for i in range(POISONED_DOMAINS):
        name = "dead%02d.svc.internal" % i
        zone[name] = ("10.9.9.%d" % (i + 1), POISONED_TTL)
        failing.append(name)
    return zone, failing


def build_trace(rng, zone, steps=DEFAULT_STEPS):
    """生成请求序列，元素是 (时钟推进秒数, 域名)。

    访问有明显的时间局部性：大概率接着查上一个域名。
    """
    names = sorted(zone)
    trace = []
    current = rng.choice(names)
    for _ in range(steps):
        if rng.random() >= REPEAT_PROBABILITY:
            current = rng.choice(names)
        trace.append((rng.choice(GAP_CHOICES), current))
    return trace


def _attempt(resolve, name):
    """把一次解析归一化成可比较的结果。

    resolve 是直连上游的 resolve 或者缓存的 lookup；上游返回 Answer，
    缓存返回地址字符串，这里统一取地址来比。
    """
    try:
        result = resolve(name)
    except UpstreamError:
        return ("error",)
    if isinstance(result, Answer):
        return ("ok", result.address)
    return ("ok", result)


class DiffReport:
    """一次对拍的结果。"""

    def __init__(self, seed, steps, mismatches, cache_calls, direct_calls):
        self.seed = seed
        self.steps = steps
        self.mismatches = mismatches
        self.cache_calls = cache_calls
        self.direct_calls = direct_calls

    @property
    def ratio(self):
        if not self.direct_calls:
            return 1.0
        return self.cache_calls / float(self.direct_calls)

    def ok(self, ratio_bound=RATIO_BOUND):
        """没有不一致、且上游调用数压在上界以内才算过。"""
        return not self.mismatches and self.ratio <= ratio_bound

    def summary(self):
        return (
            "seed=%d steps=%d mismatches=%d 上游调用: 缓存=%d 直连=%d "
            "比值=%.3f 上界=%.2f"
            % (self.seed, self.steps, len(self.mismatches), self.cache_calls,
               self.direct_calls, self.ratio, RATIO_BOUND)
        )


def run_diff(seed=DEFAULT_SEED, steps=DEFAULT_STEPS):
    """跑一轮对拍，返回 DiffReport。"""
    rng = random.Random(seed)
    zone, failing = build_zone(rng)
    trace = build_trace(rng, zone, steps)

    ref_upstream = FakeUpstream(zone)
    ref_clock = ManualClock(START_TIME)
    direct = []
    for gap, name in trace:
        ref_clock.advance(gap)
        direct.append(_attempt(ref_upstream.resolve, name))

    cache_upstream = FakeUpstream(zone)
    cache_clock = ManualClock(START_TIME)
    cache = ResolverCache(cache_upstream, clock=cache_clock)
    through = []
    for gap, name in trace:
        cache_clock.advance(gap)
        through.append(_attempt(cache.lookup, name))

    mismatches = []
    for index, (want, got) in enumerate(zip(direct, through)):
        if want != got and len(mismatches) < MAX_REPORTED_MISMATCHES:
            mismatches.append((index, want, got))

    return DiffReport(
        seed=seed,
        steps=steps,
        mismatches=mismatches,
        cache_calls=cache_upstream.stats()["calls"],
        direct_calls=ref_upstream.stats()["calls"],
    )
