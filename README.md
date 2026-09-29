# pathlib2

A tiny, dependency-free shortest-path toolkit written in pure standard-library
Python.

## 现状

Today pathlib2 ships exactly one helper: `NaivePath` in `pathlib2/path.py`. It
stores a directed graph as an adjacency list of `(target, weight)` pairs and
computes distances by sweeping *every* edge round after round until a full pass
changes nothing. It can already answer: single-source single-sink distance
(`shortest`), single-source all-node distances (`dist_all`), whether any
negative edge exists (`has_negative`), and reachability (`path_exists`). There
is no priority queue, no path reconstruction and no shortest-path counting.

## 问题

The relaxation loop rescans all edges on every round, so its round count is
bounded only by the vertex count. On large but sparse graphs the vast majority
of that scanning changes nothing, which is the waste this iteration targets.

## 目标（见任务描述）

Grow the toolkit beyond round-after-round relaxation into a priority-queue
shortest-path core with several variants: lazy-deletion heap relaxation, path
reconstruction, shortest-path counting, must-pass-edge queries, dense/sparse
relaxation accounting, and fail-fast rules for negative weights and unknown
nodes. The full requirements live in the task description.

## 运行

Run the demo:

    python3 demo.py

Run the test suite:

    python3 -m unittest discover -s tests -v

## 实现说明

（实现后补，10 行以内）
