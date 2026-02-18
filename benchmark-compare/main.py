"""
Benchmark Comparison Service
=============================
Consumes benchmark results from Kafka and prints live comparison
tables grouped by CPU config and simulation type (FMU vs MATLAB wheel).
Includes per-scenario breakdown and aggregated totals.
"""

from quixstreams import Application
from collections import defaultdict
import os


# ── In-memory store ──
# results[benchmark_name][column_label] = stats dict
results = defaultdict(dict)
# Track column labels in order of first appearance
seen_labels = []


def make_label(row: dict) -> str:
    """Build a column label from run_label + sim_type."""
    run_label = row.get("run_label", "unknown")
    sim_type = row.get("sim_type", "")
    if sim_type and sim_type != "fmu":
        return f"{run_label} ({sim_type})"
    return run_label


def print_table(title: str, benchmarks: list[str], labels: list[str],
                metric_key: str, fmt: str, col_w: int, sep: str,
                show_aggregates: bool = True):
    """Print one metric table with optional aggregate rows."""
    header = f"  {'Benchmark':<45}"
    for label in labels:
        header += f" | {label:>{col_w}}"
    print(f"\n  {title}")
    print(header)
    print(sep)

    col_values = defaultdict(list)  # label -> list of values

    for bench in benchmarks:
        row = f"  {bench:<45}"
        for label in labels:
            if label in results[bench]:
                val = results[bench][label][metric_key]
                row += f" | {val:>{col_w}{fmt}}"
                col_values[label].append(val)
            else:
                row += f" | {'—':>{col_w}}"
        print(row)

    if show_aggregates and any(col_values.values()):
        print(sep)
        # Total (sum)
        row_total = f"  {'TOTAL (sum)':<45}"
        for label in labels:
            vals = col_values.get(label, [])
            if vals:
                row_total += f" | {sum(vals):>{col_w}{fmt}}"
            else:
                row_total += f" | {'—':>{col_w}}"
        print(row_total)

        # Average
        row_avg = f"  {'AVERAGE':<45}"
        for label in labels:
            vals = col_values.get(label, [])
            if vals:
                row_avg += f" | {sum(vals) / len(vals):>{col_w}{fmt}}"
            else:
                row_avg += f" | {'—':>{col_w}}"
        print(row_avg)

        # Min
        row_min = f"  {'BEST (min)':<45}"
        for label in labels:
            vals = col_values.get(label, [])
            if vals:
                row_min += f" | {min(vals):>{col_w}{fmt}}"
            else:
                row_min += f" | {'—':>{col_w}}"
        print(row_min)

        # Max
        row_max = f"  {'WORST (max)':<45}"
        for label in labels:
            vals = col_values.get(label, [])
            if vals:
                row_max += f" | {max(vals):>{col_w}{fmt}}"
            else:
                row_max += f" | {'—':>{col_w}}"
        print(row_max)


def print_comparison():
    """Print the full comparison tables to stdout."""
    if not results:
        return

    labels = list(seen_labels)
    benchmarks = sorted(results.keys())

    col_w = max(14, max((len(l) for l in labels), default=12))
    total_w = 50 + (col_w + 3) * len(labels)

    sep = f"  {'-' * 45}"
    for _ in labels:
        sep += f" | {'-' * col_w}"

    print(f"\n{'=' * total_w}")
    print("  CPU / Sim-Type Comparison")
    print(f"{'=' * total_w}")

    print_table("Mean Latency (ms)", benchmarks, labels,
                "mean_ms", ".3f", col_w, sep)

    print_table("Throughput (ops/s)", benchmarks, labels,
                "throughput_ops", ".1f", col_w, sep)

    print_table("P95 Latency (ms)", benchmarks, labels,
                "p95_ms", ".3f", col_w, sep)

    total = sum(len(v) for v in results.values())
    print(f"\n  Total results collected: {total}  "
          f"({len(benchmarks)} scenarios x {len(labels)} configs)")
    print()


def process_result(row: dict):
    """Called for every benchmark result message."""
    label = make_label(row)
    bench_name = row.get("name", "unknown")

    if label not in seen_labels:
        seen_labels.append(label)

    results[bench_name][label] = {
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
        "sim_type": row.get("sim_type", "fmu"),
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
