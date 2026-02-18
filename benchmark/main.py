"""
FMU Simulation Benchmark — Quix Service
========================================
Runs FMU simulation benchmarks and publishes results to a Kafka topic.
Configurable via environment variables: iterations, warmup, run_label.
"""

from quixstreams import Application
from quixstreams.sources import Source
from fmpy import read_model_description, simulate_fmu

import json
import os
import platform
import statistics
import time
from dataclasses import dataclass, asdict

import numpy as np


# ---------------------------------------------------------------------------
# Stats
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
    throughput_ops: float


def compute_stats(name: str, timings: list[float]) -> TimingStats:
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


# ---------------------------------------------------------------------------
# System info (detects Docker CPU limits)
# ---------------------------------------------------------------------------

def system_info() -> dict:
    cpu_count = os.cpu_count() or 0
    effective_cpus = cpu_count
    try:
        with open("/sys/fs/cgroup/cpu.max") as f:
            parts = f.read().strip().split()
            if parts[0] != "max":
                effective_cpus = int(parts[0]) / int(parts[1])
    except FileNotFoundError:
        try:
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
# FMU locator
# ---------------------------------------------------------------------------

def find_fmu(name: str) -> str | None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, name),
        os.path.join(script_dir, "fmus", name),
        os.path.join(script_dir, "..", "fmu-integration", name),
        os.path.join(script_dir, "..", "fmu-explorer", "examples", name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


# ---------------------------------------------------------------------------
# Benchmark scenarios
# ---------------------------------------------------------------------------

def bench_model_load(fmu_path: str, iterations: int, warmup: int) -> TimingStats:
    for _ in range(warmup):
        read_model_description(fmu_path)
    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        read_model_description(fmu_path)
        timings.append(time.perf_counter() - t0)
    return compute_stats("Model description load", timings)


def bench_simulink_instant(fmu_path: str, iterations: int, warmup: int) -> TimingStats:
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
    for _ in range(warmup):
        simulate_fmu(fmu_path, start_time=0.0, stop_time=stop_time)
    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        simulate_fmu(fmu_path, start_time=0.0, stop_time=stop_time)
        timings.append(time.perf_counter() - t0)
    return compute_stats(f"BouncingBall free-run (stop={stop_time}s)", timings)


def bench_rapid_fire(fmu_path: str, iterations: int, warmup: int) -> TimingStats:
    theta = np.pi / 4
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
# Quix Source
# ---------------------------------------------------------------------------

class BenchmarkSource(Source):
    """Runs all FMU benchmarks and publishes each result as a message."""

    def run(self):
        iterations = int(os.environ.get("iterations", "100"))
        warmup = int(os.environ.get("warmup", "5"))
        run_label = os.environ.get("run_label", "default")

        info = system_info()
        print("=" * 60)
        print("  FMU Simulation Benchmark (Quix Service)")
        print("=" * 60)
        print(f"  Run label      : {run_label}")
        print(f"  Platform       : {info['platform']}")
        print(f"  Processor      : {info['processor']}")
        print(f"  Python         : {info['python_version']}")
        print(f"  OS CPU count   : {info['os_cpu_count']}")
        print(f"  Effective CPUs : {info['effective_cpus']}")
        print(f"  Iterations     : {iterations}")
        print(f"  Warmup         : {warmup}")

        simulink_fmu = find_fmu("simulink_example_inports.fmu")
        bouncing_fmu = find_fmu("BouncingBall.fmu")

        if not simulink_fmu and not bouncing_fmu:
            print("ERROR: No FMU files found.")
            return

        all_stats: list[TimingStats] = []

        # -- Simulink benchmarks --
        if simulink_fmu:
            print(f"\n  Simulink FMU: {simulink_fmu}")

            stats = bench_model_load(simulink_fmu, iterations, warmup)
            print_stats(stats)
            all_stats.append(stats)
            self._publish(stats, "simulink", run_label, info)

            stats = bench_simulink_instant(simulink_fmu, iterations, warmup)
            print_stats(stats)
            all_stats.append(stats)
            self._publish(stats, "simulink", run_label, info)

            for pts in [10, 100, 1000]:
                stats = bench_simulink_timeseries(simulink_fmu, pts, iterations, warmup)
                print_stats(stats)
                all_stats.append(stats)
                self._publish(stats, "simulink", run_label, info)

            stats = bench_rapid_fire(simulink_fmu, iterations, warmup)
            print_stats(stats)
            all_stats.append(stats)
            self._publish(stats, "simulink", run_label, info)

        # -- BouncingBall benchmarks --
        if bouncing_fmu:
            print(f"\n  BouncingBall FMU: {bouncing_fmu}")

            stats = bench_model_load(bouncing_fmu, iterations, warmup)
            print_stats(stats)
            all_stats.append(stats)
            self._publish(stats, "bouncing_ball", run_label, info)

            for duration in [1.0, 5.0, 10.0]:
                stats = bench_bouncing_ball(bouncing_fmu, duration, iterations, warmup)
                print_stats(stats)
                all_stats.append(stats)
                self._publish(stats, "bouncing_ball", run_label, info)

        # -- Summary --
        print(f"\n{'=' * 60}")
        print("  Summary")
        print(f"{'=' * 60}")
        print(f"  {'Benchmark':<45} {'Mean':>8} {'P95':>8} {'ops/s':>8}")
        print(f"  {'-' * 45} {'-' * 8} {'-' * 8} {'-' * 8}")
        for s in all_stats:
            print(f"  {s.name:<45} {s.mean_ms:>7.2f}ms {s.p95_ms:>7.2f}ms {s.throughput_ops:>7.1f}")
        print()

    def _publish(self, stats: TimingStats, fmu_model: str,
                 run_label: str, sys_info: dict):
        """Serialize one benchmark result and produce it to the topic."""
        value = {
            "run_label": run_label,
            "fmu_model": fmu_model,
            "effective_cpus": sys_info["effective_cpus"],
            "os_cpu_count": sys_info["os_cpu_count"],
            "platform": sys_info["platform"],
            **asdict(stats),
        }
        msg = self.serialize(
            key=f"benchmark-{run_label}",
            value=value,
        )
        self.produce(key=msg.key, value=msg.value)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    app = Application(
        consumer_group="fmu-benchmark",
        auto_create_topics=True,
    )
    output_topic = app.topic(name=os.environ["output"])
    benchmark_source = BenchmarkSource(name="fmu-benchmark")
    app.add_source(source=benchmark_source, topic=output_topic)
    app.run()


if __name__ == "__main__":
    main()
