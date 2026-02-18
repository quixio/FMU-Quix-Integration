"""
FMU Simulation Benchmark
========================
Standalone benchmark that measures FMU simulation performance in isolation.
Tests both available FMU models with varying workloads and reports detailed
timing statistics.

Usage:
    python benchmark.py [--iterations N] [--warmup N] [--output results.json]
"""

import argparse
import json
import os
import platform
import statistics
import sys
import time
from dataclasses import dataclass, field, asdict

import numpy as np
from fmpy import read_model_description, simulate_fmu


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass
class TimingStats:
    name: str
    iterations: int
    total_s: float
    mean_ms: float
    median_ms: float
    min_ms: float
    max_ms: float
    stdev_ms: float
    p95_ms: float
    p99_ms: float
    throughput_ops: float  # operations per second


def compute_stats(name: str, timings: list[float]) -> TimingStats:
    """Compute statistics from a list of elapsed-time measurements (seconds)."""
    ms = [t * 1000 for t in timings]
    sorted_ms = sorted(ms)
    n = len(ms)
    return TimingStats(
        name=name,
        iterations=n,
        total_s=sum(timings),
        mean_ms=statistics.mean(ms),
        median_ms=statistics.median(ms),
        min_ms=min(ms),
        max_ms=max(ms),
        stdev_ms=statistics.stdev(ms) if n > 1 else 0.0,
        p95_ms=sorted_ms[int(n * 0.95)] if n >= 20 else sorted_ms[-1],
        p99_ms=sorted_ms[int(n * 0.99)] if n >= 100 else sorted_ms[-1],
        throughput_ops=n / sum(timings) if sum(timings) > 0 else 0.0,
    )


def print_stats(stats: TimingStats):
    print(f"\n{'=' * 60}")
    print(f"  {stats.name}")
    print(f"{'=' * 60}")
    print(f"  Iterations : {stats.iterations}")
    print(f"  Total time : {stats.total_s:.3f} s")
    print(f"  Mean       : {stats.mean_ms:.3f} ms")
    print(f"  Median     : {stats.median_ms:.3f} ms")
    print(f"  Min        : {stats.min_ms:.3f} ms")
    print(f"  Max        : {stats.max_ms:.3f} ms")
    print(f"  Stdev      : {stats.stdev_ms:.3f} ms")
    print(f"  P95        : {stats.p95_ms:.3f} ms")
    print(f"  P99        : {stats.p99_ms:.3f} ms")
    print(f"  Throughput : {stats.throughput_ops:.1f} ops/s")


def system_info() -> dict:
    """Gather system information for the report."""
    cpu_count = os.cpu_count() or 0
    # Try to read Docker CPU quota (Linux cgroups v1/v2)
    effective_cpus = cpu_count
    try:
        # cgroups v2
        with open("/sys/fs/cgroup/cpu.max") as f:
            parts = f.read().strip().split()
            if parts[0] != "max":
                quota = int(parts[0])
                period = int(parts[1])
                effective_cpus = quota / period
    except FileNotFoundError:
        try:
            # cgroups v1
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
                quota = int(f.read().strip())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
                period = int(f.read().strip())
            if quota > 0:
                effective_cpus = quota / period
        except FileNotFoundError:
            pass

    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "os_cpu_count": cpu_count,
        "effective_cpus": effective_cpus,
    }


# ---------------------------------------------------------------------------
# Benchmark scenarios
# ---------------------------------------------------------------------------

def find_fmu(name: str) -> str | None:
    """Search for an FMU file relative to this script and common locations."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, name),
        os.path.join(script_dir, "..", "fmu-integration", name),
        os.path.join(script_dir, "..", "fmu-explorer", "examples", name),
        os.path.join(script_dir, "fmus", name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


def bench_model_load(fmu_path: str, iterations: int, warmup: int) -> TimingStats:
    """Measure time to read model description (metadata parsing)."""
    for _ in range(warmup):
        read_model_description(fmu_path)

    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        read_model_description(fmu_path)
        timings.append(time.perf_counter() - t0)

    return compute_stats("Model description load", timings)


def bench_simulink_instant(fmu_path: str, iterations: int, warmup: int) -> TimingStats:
    """Benchmark: single-point evaluation (start==stop, like the streaming pipeline)."""
    theta = np.pi / 4
    input_data = np.array(
        [(0.0, 1.0, 2.0, theta)],
        dtype=[('time', np.float64), ('x', np.float64),
               ('y', np.float64), ('theta', np.float64)]
    )

    for _ in range(warmup):
        simulate_fmu(fmu_path, start_time=0.0, stop_time=0.0, input=input_data)

    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        simulate_fmu(fmu_path, start_time=0.0, stop_time=0.0, input=input_data)
        timings.append(time.perf_counter() - t0)

    return compute_stats("Simulink instant eval (start==stop)", timings)


def bench_simulink_timeseries(fmu_path: str, num_points: int,
                               iterations: int, warmup: int) -> TimingStats:
    """Benchmark: time-series simulation with N input points."""
    theta = np.pi / 4
    times = np.linspace(0.0, 1.0, num_points)
    data = [(t, np.sin(t), np.cos(t), theta) for t in times]
    input_data = np.array(
        data,
        dtype=[('time', np.float64), ('x', np.float64),
               ('y', np.float64), ('theta', np.float64)]
    )

    for _ in range(warmup):
        simulate_fmu(fmu_path, start_time=0.0, stop_time=1.0, input=input_data)

    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        simulate_fmu(fmu_path, start_time=0.0, stop_time=1.0, input=input_data)
        timings.append(time.perf_counter() - t0)

    return compute_stats(f"Simulink time-series ({num_points} points)", timings)


def bench_bouncing_ball(fmu_path: str, stop_time: float,
                        iterations: int, warmup: int) -> TimingStats:
    """Benchmark: BouncingBall free-run simulation for a given duration."""
    for _ in range(warmup):
        simulate_fmu(fmu_path, start_time=0.0, stop_time=stop_time)

    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        simulate_fmu(fmu_path, start_time=0.0, stop_time=stop_time)
        timings.append(time.perf_counter() - t0)

    return compute_stats(f"BouncingBall free-run (stop={stop_time}s)", timings)


def bench_rapid_fire(fmu_path: str, iterations: int, warmup: int) -> TimingStats:
    """Benchmark: rapid sequential calls simulating streaming throughput."""
    theta = np.pi / 4

    # Pre-generate random inputs
    rng = np.random.default_rng(42)
    xs = rng.uniform(-10, 10, iterations + warmup)
    ys = rng.uniform(-10, 10, iterations + warmup)

    for i in range(warmup):
        input_data = np.array(
            [(0.0, xs[i], ys[i], theta)],
            dtype=[('time', np.float64), ('x', np.float64),
                   ('y', np.float64), ('theta', np.float64)]
        )
        simulate_fmu(fmu_path, start_time=0.0, stop_time=0.0, input=input_data)

    timings = []
    for i in range(iterations):
        input_data = np.array(
            [(0.0, xs[warmup + i], ys[warmup + i], theta)],
            dtype=[('time', np.float64), ('x', np.float64),
                   ('y', np.float64), ('theta', np.float64)]
        )
        t0 = time.perf_counter()
        simulate_fmu(fmu_path, start_time=0.0, stop_time=0.0, input=input_data)
        timings.append(time.perf_counter() - t0)

    return compute_stats("Rapid-fire streaming simulation", timings)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="FMU Simulation Benchmark")
    parser.add_argument("--iterations", "-n", type=int, default=100,
                        help="Number of timed iterations per benchmark (default: 100)")
    parser.add_argument("--warmup", "-w", type=int, default=5,
                        help="Warmup iterations before timing (default: 5)")
    parser.add_argument("--output", "-o", type=str, default=None,
                        help="Write results to JSON file")
    args = parser.parse_args()

    info = system_info()
    print("=" * 60)
    print("  FMU Simulation Benchmark")
    print("=" * 60)
    print(f"  Platform       : {info['platform']}")
    print(f"  Processor      : {info['processor']}")
    print(f"  Python         : {info['python_version']}")
    print(f"  OS CPU count   : {info['os_cpu_count']}")
    print(f"  Effective CPUs : {info['effective_cpus']}")
    print(f"  Iterations     : {args.iterations}")
    print(f"  Warmup         : {args.warmup}")

    # Locate FMUs
    simulink_fmu = find_fmu("simulink_example_inports.fmu")
    bouncing_fmu = find_fmu("BouncingBall.fmu")

    if not simulink_fmu and not bouncing_fmu:
        print("\nERROR: No FMU files found. Place .fmu files in benchmark/ or fmus/ dir.")
        sys.exit(1)

    all_stats: list[TimingStats] = []

    # -- Simulink benchmarks --
    if simulink_fmu:
        print(f"\n  Simulink FMU   : {simulink_fmu}")

        stats = bench_model_load(simulink_fmu, args.iterations, args.warmup)
        print_stats(stats)
        all_stats.append(stats)

        stats = bench_simulink_instant(simulink_fmu, args.iterations, args.warmup)
        print_stats(stats)
        all_stats.append(stats)

        for pts in [10, 100, 1000]:
            stats = bench_simulink_timeseries(simulink_fmu, pts,
                                               args.iterations, args.warmup)
            print_stats(stats)
            all_stats.append(stats)

        stats = bench_rapid_fire(simulink_fmu, args.iterations, args.warmup)
        print_stats(stats)
        all_stats.append(stats)

    # -- BouncingBall benchmarks --
    if bouncing_fmu:
        print(f"\n  BouncingBall   : {bouncing_fmu}")

        stats = bench_model_load(bouncing_fmu, args.iterations, args.warmup)
        print_stats(stats)
        all_stats.append(stats)

        for duration in [1.0, 5.0, 10.0]:
            stats = bench_bouncing_ball(bouncing_fmu, duration,
                                        args.iterations, args.warmup)
            print_stats(stats)
            all_stats.append(stats)

    # -- Summary table --
    print(f"\n{'=' * 60}")
    print("  Summary")
    print(f"{'=' * 60}")
    print(f"  {'Benchmark':<45} {'Mean':>8} {'P95':>8} {'ops/s':>8}")
    print(f"  {'-' * 45} {'-' * 8} {'-' * 8} {'-' * 8}")
    for s in all_stats:
        print(f"  {s.name:<45} {s.mean_ms:>7.2f}ms {s.p95_ms:>7.2f}ms {s.throughput_ops:>7.1f}")

    # -- Write JSON output --
    if args.output:
        report = {
            "system": info,
            "config": {"iterations": args.iterations, "warmup": args.warmup},
            "benchmarks": [asdict(s) for s in all_stats],
        }
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n  Results written to {args.output}")

    print()


if __name__ == "__main__":
    main()
