"""本地点位索引。

点按单层固定边长格网分桶，精确坐标查询只扫候选格；全量遍历按登记顺序。
id 用任意可哈希对象，查询结果一律按登记顺序返回。
"""

from .cells import DEFAULT_CELL_DEG, cell_of, check_cell_deg
from .errors import DuplicateId, UnknownId
from .geo import check_lat, check_lon, normalize_lon


class PointIndex:
    """经纬度点位集合：精确坐标查询加全量遍历。"""

    def __init__(self, cell_deg=DEFAULT_CELL_DEG):
        self.cell_deg = check_cell_deg(cell_deg)
        self._cells = {}
        self._points = {}
        self._lookups = 0
        self._hits = 0

    def add(self, pid, lat, lon):
        """登记点 pid；经度归一化后入库，重复 id 报 DuplicateId。"""
        lat = check_lat(lat)
        lon = normalize_lon(check_lon(lon))
        if pid in self._points:
            raise DuplicateId("点 %r 已在索引里" % (pid,))
        self._points[pid] = (lat, lon)
        self._cells.setdefault(cell_of(lat, lon, self.cell_deg), []).append(pid)

    def remove(self, pid):
        """摘除点 pid，返回归一化后的坐标；不在索引里报 UnknownId。"""
        if pid not in self._points:
            raise UnknownId("索引里没有点 %r" % (pid,))
        lat, lon = self._points.pop(pid)
        key = cell_of(lat, lon, self.cell_deg)
        bucket = self._cells[key]
        bucket.remove(pid)
        if not bucket:
            del self._cells[key]
        return (lat, lon)

    def at(self, lat, lon):
        """返回坐标与查询点完全相同的全部 id，按登记顺序。"""
        lat = check_lat(lat)
        lon = normalize_lon(check_lon(lon))
        self._lookups += 1
        target = (lat, lon)
        bucket = self._cells.get(cell_of(lat, lon, self.cell_deg), ())
        found = [pid for pid in bucket if self._points[pid] == target]
        if found:
            self._hits += 1
        return found

    def scan(self):
        """按登记顺序返回全部 (pid, lat, lon)。"""
        return [(pid, lat, lon) for pid, (lat, lon) in self._points.items()]

    def __len__(self):
        return len(self._points)

    def __contains__(self, pid):
        return pid in self._points

    def stats(self):
        """索引状态快照。"""
        max_cell = max((len(bucket) for bucket in self._cells.values()), default=0)
        return {
            "points": len(self._points),
            "cells": len(self._cells),
            "max_cell": max_cell,
            "lookups": self._lookups,
            "hits": self._hits,
        }
