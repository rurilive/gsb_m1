"""按层模拟执行 / 计划 + 报告。

执行是纯模拟：不运行任何真实命令，每个目标按名字哈希得到一个
1..9ms 的确定性模拟耗时，逐层推进。失败与跳过的级联语义：

- 命中 fail_targets 的目标 -> failed（已经"跑过"，仍消耗模拟耗时）
- 依赖里出现 failed 或 skip 的目标 -> skip（没有执行，耗时计 0）

plan 是 run 的"只看计划"变体：走同一套分层推进与阶段钩子，但每个
目标直接落定 plan 态、耗时计 0，不读 fail_targets，没有失败注入与
级联跳过；分层结果与 run 完全一致。

StageVisitor 是执行过程的阶段钩子：层开始 / 目标落定 / 层结束 /
收尾四个回调，把实例传给 Executor.run/plan(visitor=...) 即可同步
观察推进过程；报告数据由执行器直接汇总，不经过钩子。
"""

import hashlib
from dataclasses import dataclass

from .graph import layer_targets


def target_cost_ms(name):
    """确定性模拟耗时：由目标名决定，1..9ms，同名恒同值。"""
    digest = hashlib.md5(name.encode("utf-8")).hexdigest()
    return 1 + int(digest[:8], 16) % 9


@dataclass(frozen=True)
class Record:
    """一个目标的执行记录。"""

    layer: int  # 1-based 层号
    name: str
    status: str  # ok / skip / failed / plan
    cost_ms: int


class Report:
    """执行报告：分层 + 逐目标记录 + 汇总。

    kind 为 "plan" 时是执行计划：首行换 plan 头（只有目标数与层数，
    不带计数与总耗时），目标行状态列固定 plan、无耗时列。
    """

    def __init__(self, layers, records, counts, total_ms, kind="run"):
        self.layers = layers
        self.records = records
        self.counts = counts
        self.total_ms = total_ms
        self.kind = kind

    @property
    def text(self):
        if self.kind == "plan":
            header = (
                f"plan: {len(self.records)} target(s)"
                f" in {len(self.layers)} layer(s)"
            )
        else:
            header = (
                f"report: {len(self.records)} target(s)"
                f" in {len(self.layers)} layer(s)"
                f" | ok={self.counts['ok']} skip={self.counts['skip']}"
                f" failed={self.counts['failed']} | total {self.total_ms}ms"
            )
        lines = [header]
        records_by_layer = {}
        for r in self.records:
            records_by_layer.setdefault(r.layer, []).append(r)
        for index, layer in enumerate(self.layers, 1):
            lines.append(f"[{index}/{len(self.layers)}] " + " ".join(layer))
            for r in records_by_layer.get(index, []):
                if self.kind == "plan":
                    lines.append(f"  {r.status:<7}{r.name}")
                else:
                    lines.append(f"  {r.status:<7}{r.name} {r.cost_ms:>3}ms")
        return "\n".join(lines) + "\n"


class StageVisitor:
    """执行过程的阶段钩子。全部为观察回调，返回值被忽略。"""

    def on_layer_start(self, index, total, targets):
        """一层开始推进。index/total 从 1 计，targets 是该层并行组。"""

    def on_target_finish(self, name, status, cost_ms):
        """一个目标落定。status: ok / skip / failed / plan。"""

    def on_layer_finish(self, index):
        """该层全部目标落定后回调。"""

    def on_run_finish(self, counts, total_ms):
        """所有层结束后回调一次。"""


class Executor:
    """依赖图执行器：解析后的清单 -> 拓扑分层 -> 按层模拟执行 -> 报告。"""

    def __init__(self, fail_targets=()):
        self.fail_targets = frozenset(fail_targets)

    def run(self, manifest, visitor=None) -> Report:
        return self._advance(manifest, visitor, plan_only=False)

    def plan(self, manifest, visitor=None) -> Report:
        """只产出执行计划，不执行任何模拟动作。

        与 run 走同一套分层推进与阶段钩子，分层结果完全一致；但全部
        目标都是 plan 态、耗时计 0，不读 fail_targets，没有失败注入
        与级联跳过。清单校验与 run 相同，原样抛 ManifestError /
        GraphError。
        """
        return self._advance(manifest, visitor, plan_only=True)

    def _advance(self, manifest, visitor, plan_only) -> Report:
        layers = layer_targets(manifest)
        records = []
        failed = set()
        skipped = set()
        listeners = [visitor] if visitor is not None else []
        total = len(layers)

        for index, layer in enumerate(layers, 1):
            for v in listeners:
                v.on_layer_start(index, total, list(layer))
            for name in layer:
                if plan_only:
                    status = "plan"
                    cost = 0
                else:
                    deps = manifest.targets[name].deps
                    cost = target_cost_ms(name)
                    if failed.intersection(deps) or skipped.intersection(deps):
                        status = "skip"
                        cost = 0
                        skipped.add(name)
                    elif name in self.fail_targets:
                        status = "failed"
                        failed.add(name)
                    else:
                        status = "ok"
                records.append(Record(index, name, status, cost))
                for v in listeners:
                    v.on_target_finish(name, status, cost)
            for v in listeners:
                v.on_layer_finish(index)

        if plan_only:
            counts = {"plan": len(records)}
        else:
            counts = {"ok": 0, "skip": 0, "failed": 0}
            for r in records:
                counts[r.status] += 1
        total_ms = sum(r.cost_ms for r in records)
        for v in listeners:
            v.on_run_finish(counts, total_ms)
        kind = "plan" if plan_only else "run"
        return Report(layers, records, counts, total_ms, kind=kind)
