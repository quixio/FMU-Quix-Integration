"""
Benchmark Comparison Service
=============================
Consumes benchmark results from Kafka and prints a live comparison
table grouped by CPU config. Every time a new result arrives, the
full comparison is reprinted so the logs always show the latest view.
"""

from quixstreams import Application
from collections import defaultdict
import os


# ── In-memory store: results[benchmark_name][run_label] = stats dict ──
results = defaultdict(dict)
# Track which run_labels we've seen (ordered by first appearance)
seen_labels = []


def print_comparison():
    """Print the full comparison table to stdout."""
    if not results:
        return

    labels = list(seen_labels)
    benchmarks = sorted(results.keys())

    # Header
    col_w = 12
    header_label = f"  {'Benchmark':<45}"
    for label in labels:
        header_label += f" | {label:>{col_w}}"
    separator = f"  {'-' * 45}"
    for _ in labels:
        separator += f" | {'-' * col_w}"

    print(f"\n{'=' * (50 + (col_w + 3) * len(labels))}")
    print("  CPU Comparison — Mean (ms)")
    print(f"{'=' * (50 + (col_w + 3) * len(labels))}")
    print(header_label)
    print(separator)

    for bench in benchmarks:
        row = f"  {bench:<45}"
        for label in labels:
            if label in results[bench]:
                val = results[bench][label]["mean_ms"]
                row += f" | {val:>{col_w}.3f}"
            else:
                row += f" | {'—':>{col_w}}"
        print(row)

    # Throughput table
    print(f"\n  {'Benchmark':<45}", end="")
    for label in labels:
        print(f" | {label + ' ops/s':>{col_w}}", end="")
    print()
    print(separator)

    for bench in benchmarks:
        row = f"  {bench:<45}"
        for label in labels:
            if label in results[bench]:
                val = results[bench][label]["throughput_ops"]
                row += f" | {val:>{col_w}.1f}"
            else:
                row += f" | {'—':>{col_w}}"
        print(row)

    # P95 table
    print(f"\n  {'Benchmark':<45}", end="")
    for label in labels:
        print(f" | {label + ' P95':>{col_w}}", end="")
    print()
    print(separator)

    for bench in benchmarks:
        row = f"  {bench:<45}"
        for label in labels:
            if label in results[bench]:
                val = results[bench][label]["p95_ms"]
                row += f" | {val:>{col_w}.3f}"
            else:
                row += f" | {'—':>{col_w}}"
        print(row)

    total = sum(len(v) for v in results.values())
    print(f"\n  Total results collected: {total}  "
          f"({len(benchmarks)} scenarios × {len(labels)} configs)")
    print()


def process_result(row: dict):
    """Called for every benchmark result message."""
    run_label = row.get("run_label", "unknown")
    bench_name = row.get("name", "unknown")

    if run_label not in seen_labels:
        seen_labels.append(run_label)

    results[bench_name][run_label] = {
        "mean_ms": row.get("mean_ms", 0),
        "median_ms": row.get("median_ms", 0),
        "min_ms": row.get("min_ms", 0),
        "max_ms": row.get("max_ms", 0),
        "p95_ms": row.get("p95_ms", 0),
        "p99_ms": row.get("p99_ms", 0),
        "stdev_ms": row.get("stdev_ms", 0),
        "throughput_ops": row.get("throughput_ops", 0),
        "effective_cpus": row.get("effective_cpus", 0),
        "iterations": row.get("iterations", 0),
    }

    print_comparison()


def main():
    app = Application(
        consumer_group="benchmark-compare",
        auto_create_topics=True,
        auto_offset_reset="earliest",
    )
    input_topic = app.topic(name=os.environ["input"])
    sdf = app.dataframe(topic=input_topic)

    sdf = sdf.update(process_result)

    print("Benchmark Comparison Service started.")
    print("Waiting for results on topic:", os.environ["input"])
    app.run()


if __name__ == "__main__":
    main()
