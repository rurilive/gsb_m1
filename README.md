# rankly

A tiny, dependency-free ranking toolkit written in pure standard-library
Python.

## 现状

Today rankly ships exactly one helper: `SortTopK` in `rankly/topk.py`. It sorts
the entire input in descending order and slices off the first k items. There is
no heap, no streaming mode and no incremental state, so both memory and time
grow with the full input size.

## 目标（见任务描述）

Grow the toolkit beyond full-sort Top-K into streaming and heap-based Top-K,
weighted and de-duplicated ranking, quantiles and medians, and merging of
partial results. The full requirements live in the task description.

## 运行

Run the demo:

    python3 demo.py

Run the test suite:

    python3 -m unittest discover -s tests -v

## 实现说明

（实现后补，10 行以内）
