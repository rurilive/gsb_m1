"""依赖解析主体：闭包收集、版本择优、拓扑排序。"""

from .version import parse_requirement, parse_version, satisfies


class ResolveError(Exception):
    """解析失败基类。"""


class UnknownPackageError(ResolveError):
    pass


class CircularDependencyError(ResolveError):
    def __init__(self, chain):
        super().__init__("循环依赖: " + " -> ".join(chain))
        self.chain = chain


class ConflictError(ResolveError):
    pass


class Resolver:

    def __init__(self, manifest, enabled=None):
        self._manifest = manifest
        self._enabled = set(enabled or ())
        self._constraints = {}   # name -> [(constraints, requirer)]
        self._chosen = {}        # name -> version
        self._order = []         # 拓扑序（后序）
        self._done = set()
        self._visiting = []      # DFS 路径栈

    def resolve(self, requests):
        """返回拓扑序的 "name@version" 列表。"""
        seen = set()
        for name in requests:
            if name in seen:
                continue
            seen.add(name)
            self._visit(name)
        for name in self._order:
            self._chosen[name] = self._select_version(name)
        return [f"{name}@{self._chosen[name]}" for name in self._order]

    def _visit(self, name):
        if name not in self._manifest:
            raise UnknownPackageError(f"请求了不存在的包 {name}")
        if name in self._done:
            return
        if name in self._visiting:
            chain = self._visiting[self._visiting.index(name):] + [name]
            raise CircularDependencyError(chain)
        self._visiting.append(name)
        for dep in self._direct_deps(name):
            req_name, constraints = parse_requirement(dep)
            if req_name not in self._manifest:
                raise UnknownPackageError(f"{name} 依赖了不存在的包 {req_name}")
            self._constraints.setdefault(req_name, []).append((constraints, name))
            self._visit(req_name)
        self._visiting.remove(name)
        self._done.add(name)
        self._order.append(name)

    def _direct_deps(self, name):
        spec = self._manifest[name]
        deps = list(spec.get("depends") or [])
        optional = spec.get("optional_depends") or []
        if optional:
            deps.extend(d for d in optional if parse_requirement(d)[0] in self._enabled)
        return deps

    def _select_version(self, name):
        versions = self._manifest[name].get("versions") or []
        if not versions:
            raise UnknownPackageError(f"{name} 没有可用版本")
        constraints = self._constraints.get(name) or []
        candidates = [
            version
            for version in versions
            if all(satisfies(version, constraint) for constraint, _ in constraints)
        ]
        if not candidates:
            detail = ", ".join(
                f"{requirer} 要求 {name}{self._format_constraint(constraint)}"
                for constraint, requirer in constraints
            )
            raise ConflictError(f"{name}: 没有版本能同时满足全部约束（{detail}）")
        return max(candidates, key=parse_version)

    @staticmethod
    def _format_constraint(constraint):
        if not constraint:
            return "（任意版本）"
        return ",".join(f"{op}{'.'.join(str(p) for p in target)}" for op, target in constraint)
