"""
FMU vs MATLAB Wheel Benchmark — Quix Service
==============================================
Compares BouncingBall simulation performance between:
  - FMU (via fmpy)
  - MATLAB Compiled wheel (via quixmatlab / MATLAB Runtime)

Publishes results to a Kafka topic with a `sim_type` field
("fmu" or "matlab_wheel") so the comparison service can
distinguish them.
"""

from quixstreams import Application
from quixstreams.sources import Source
from fmpy import simulate_fmu

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
# System info
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
        os.path.join(script_dir, "..", "fmu-explorer", "examples", name),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return os.path.abspath(path)
    return None


# ---------------------------------------------------------------------------
# FMU Benchmarks (BouncingBall via fmpy)
# ---------------------------------------------------------------------------

def bench_fmu_bouncing_ball(fmu_path: str, stop_time: float,
                            iterations: int, warmup: int) -> TimingStats:
    for _ in range(warmup):
        simulate_fmu(fmu_path, start_time=0.0, stop_time=stop_time)
    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        simulate_fmu(fmu_path, start_time=0.0, stop_time=stop_time)
        timings.append(time.perf_counter() - t0)
    return compute_stats(f"FMU BouncingBall (stop={stop_time}s)", timings)


# ---------------------------------------------------------------------------
# MATLAB Wheel Benchmarks (sim_bounce via quixmatlab)
# ---------------------------------------------------------------------------

def convert_matlab_to_numpy(matlab_val) -> np.ndarray:
    """Convert matlab.double (or similar) to numpy array."""
    try:
        return np.asarray(matlab_val).flatten()
    except Exception:
        try:
            return np.array(list(matlab_val)).flatten()
        except Exception:
            return np.array([float(matlab_val)])


def probe_function_exists(client, func_name: str) -> bool:
    """Test if a function exists on the MATLAB client."""
    try:
        func = getattr(client, func_name)
        func(nargout=0)
        return True
    except SystemError as e:
        if 'not found' in str(e).lower():
            return False
        return True
    except TypeError:
        return True
    except Exception:
        return True


def discover_function(client) -> str | None:
    """Find the simulation function exposed by the wheel."""
    candidates = ['sim_bounce', 'simulink_wrapper', 'bouncing_ball', 'run_model']
    for name in candidates:
        if probe_function_exists(client, name):
            print(f"  Discovered function: {name}")
            return name

    # Fallback: scan dir()
    excluded = {'initialize', 'terminate', 'set_config', 'get_config',
                'exit', 'quit', 'name', 'wait_for_figures_to_close'}
    for name in dir(client):
        if name.startswith('_') or name in excluded:
            continue
        if probe_function_exists(client, name):
            print(f"  Discovered function via scan: {name}")
            return name
    return None


def call_sim_function(client, func_name: str, stop_time: float,
                      discovered_nargout: list) -> None:
    """
    Call the MATLAB simulation function.
    On first call, probes nargout. Caches the working value in discovered_nargout.
    """
    func = getattr(client, func_name)

    # Default bouncing ball params
    params = {
        'g': -9.81,
        'v0': 15.0,
        'x0': 10.0,
        'k': 0.8,
    }

    if discovered_nargout:
        nargout = discovered_nargout[0]
        func(**params, nargout=nargout)
        return

    # Probe nargout on first call
    for nargout in [3, 2, 1, 4, 5]:
        try:
            result = func(**params, nargout=nargout)
            discovered_nargout.append(nargout)
            print(f"  sim_bounce works with nargout={nargout}")
            return
        except TypeError as e:
            err = str(e).lower()
            if 'nargout' in err or 'argument' in err:
                continue
            if 'missing' in err or 'required' in err:
                break
            raise

    # Fallback: positional args
    param_values = list(params.values())
    for nargout in [3, 2, 1, 4, 5]:
        try:
            func(*param_values, nargout=nargout)
            discovered_nargout.append(nargout)
            print(f"  sim_bounce works with positional args, nargout={nargout}")
            return
        except TypeError:
            continue

    raise RuntimeError(f"Could not call {func_name} with any nargout value")


def init_matlab_package():
    """Initialize the quixmatlab package. Returns (client, func_name) or (None, None)."""
    try:
        import quixmatlab
        print("  Initializing MATLAB Runtime (this may take a moment)...")
        t0 = time.perf_counter()
        pkg = quixmatlab.initialize()
        elapsed = time.perf_counter() - t0
        print(f"  MATLAB Runtime initialized in {elapsed:.1f}s")
        print(f"  Exported: {[n for n in dir(pkg) if not n.startswith('_')]}")

        func_name = discover_function(pkg)
        if not func_name:
            print("  WARNING: No simulation function found in quixmatlab.")
            pkg.terminate()
            return None, None

        return pkg, func_name
    except Exception as e:
        print(f"  WARNING: Could not initialize quixmatlab: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def bench_matlab_bouncing_ball(client, func_name: str, stop_time: float,
                               iterations: int, warmup: int,
                               discovered_nargout: list) -> TimingStats:
    """Benchmark the MATLAB compiled bouncing ball simulation."""
    for _ in range(warmup):
        call_sim_function(client, func_name, stop_time, discovered_nargout)
    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        call_sim_function(client, func_name, stop_time, discovered_nargout)
        timings.append(time.perf_counter() - t0)
    return compute_stats(f"MATLAB BouncingBall (stop={stop_time}s)", timings)


def bench_matlab_init(iterations: int, warmup: int) -> TimingStats:
    """Benchmark the cost of initializing + terminating the MATLAB package."""
    import quixmatlab
    for _ in range(warmup):
        p = quixmatlab.initialize()
        p.terminate()
    timings = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        p = quixmatlab.initialize()
        p.terminate()
        timings.append(time.perf_counter() - t0)
    return compute_stats("MATLAB package init+terminate", timings)


# ---------------------------------------------------------------------------
# Quix Source
# ---------------------------------------------------------------------------

class BenchmarkMatlabSource(Source):
    """Runs FMU vs MATLAB wheel benchmarks and publishes results."""

    def run(self):
        iterations = int(os.environ.get("iterations", "100"))
        warmup = int(os.environ.get("warmup", "5"))
        run_label = os.environ.get("run_label", "default")

        info = system_info()
        print("=" * 60)
        print("  FMU vs MATLAB Wheel Benchmark (Quix Service)")
        print("=" * 60)
        print(f"  Run label      : {run_label}")
        print(f"  Platform       : {info['platform']}")
        print(f"  Processor      : {info['processor']}")
        print(f"  Python         : {info['python_version']}")
        print(f"  OS CPU count   : {info['os_cpu_count']}")
        print(f"  Effective CPUs : {info['effective_cpus']}")
        print(f"  Iterations     : {iterations}")
        print(f"  Warmup         : {warmup}")

        all_stats: list[TimingStats] = []
        durations = [1.0, 5.0, 10.0, 20.0]

        # ── FMU BouncingBall benchmarks ──
        bouncing_fmu = find_fmu("BouncingBall.fmu")
        if bouncing_fmu:
            print(f"\n  BouncingBall FMU: {bouncing_fmu}")
            for duration in durations:
                stats = bench_fmu_bouncing_ball(bouncing_fmu, duration, iterations, warmup)
                print_stats(stats)
                all_stats.append(stats)
                self._publish(stats, "bouncing_ball", "fmu", run_label, info)
        else:
            print("\n  WARNING: BouncingBall.fmu not found, skipping FMU benchmarks.")

        # ── MATLAB Wheel benchmarks ──
        pkg, func_name = init_matlab_package()
        if pkg:
            # Init/terminate cost (fewer iterations — it's slow)
            init_iters = min(iterations, 10)
            stats = bench_matlab_init(init_iters, min(warmup, 2))
            print_stats(stats)
            all_stats.append(stats)
            self._publish(stats, "bouncing_ball", "matlab_wheel", run_label, info)

            # Re-initialize for the simulation benchmarks
            pkg, func_name = init_matlab_package()
            discovered_nargout = []  # will be filled on first call

            for duration in durations:
                stats = bench_matlab_bouncing_ball(
                    pkg, func_name, duration, iterations, warmup, discovered_nargout)
                print_stats(stats)
                all_stats.append(stats)
                self._publish(stats, "bouncing_ball", "matlab_wheel", run_label, info)

            pkg.terminate()
        else:
            print("\n  WARNING: MATLAB wheel not available, skipping MATLAB benchmarks.")

        # ── Summary ──
        print(f"\n{'=' * 60}")
        print("  Summary")
        print(f"{'=' * 60}")
        print(f"  {'Benchmark':<45} {'Mean':>8} {'P95':>8} {'ops/s':>8}")
        print(f"  {'-' * 45} {'-' * 8} {'-' * 8} {'-' * 8}")
        for s in all_stats:
            print(f"  {s.name:<45} {s.mean_ms:>7.2f}ms {s.p95_ms:>7.2f}ms {s.throughput_ops:>7.1f}")
        print()

    def _publish(self, stats: TimingStats, fmu_model: str,
                 sim_type: str, run_label: str, sys_info: dict):
        """Publish one benchmark result to the topic."""
        value = {
            "run_label": run_label,
            "fmu_model": fmu_model,
            "sim_type": sim_type,
            "effective_cpus": sys_info["effective_cpus"],
            "os_cpu_count": sys_info["os_cpu_count"],
            "platform": sys_info["platform"],
            **asdict(stats),
        }
        msg = self.serialize(
            key=f"benchmark-{run_label}-{sim_type}",
            value=value,
        )
        self.produce(key=msg.key, value=msg.value)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main():
    app = Application(
        consumer_group="fmu-matlab-benchmark",
        auto_create_topics=True,
    )
    output_topic = app.topic(name=os.environ["output"])
    source = BenchmarkMatlabSource(name="fmu-matlab-benchmark")
    app.add_source(source=source, topic=output_topic)
    app.run()


if __name__ == "__main__":
    main()
