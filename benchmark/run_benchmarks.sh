#!/usr/bin/env bash
#
# Run FMU benchmarks with different CPU allocations.
# Results are saved to benchmark/results/ as JSON files.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

mkdir -p results

echo "============================================="
echo "  FMU Benchmark Suite — CPU Comparison"
echo "============================================="
echo ""

# Build the image once (all services share the same image)
echo ">> Building benchmark image..."
docker compose build benchmark-1cpu
echo ""

# Run each CPU config sequentially so they don't compete for resources
CONFIGS=("benchmark-half-cpu" "benchmark-1cpu" "benchmark-2cpu" "benchmark-4cpu")

for svc in "${CONFIGS[@]}"; do
    echo "---------------------------------------------"
    echo ">> Running: $svc"
    echo "---------------------------------------------"
    docker compose run --rm "$svc"
    echo ""
done

echo "============================================="
echo "  All benchmarks complete!"
echo "============================================="
echo ""
echo "Results saved in: $SCRIPT_DIR/results/"
ls -la results/*.json 2>/dev/null || echo "  (no JSON files found)"
echo ""

# Print comparison if python3 is available
if command -v python3 &>/dev/null; then
    python3 - <<'PYEOF'
import json, glob, os

results_dir = os.path.join(os.path.dirname(os.path.abspath("__file__")), "results")
files = sorted(glob.glob("results/results_*.json"))

if not files:
    print("No result files found.")
    exit()

print("=" * 80)
print("  CPU Comparison Summary")
print("=" * 80)

# Collect data
configs = []
for f in files:
    with open(f) as fh:
        data = json.load(fh)
    label = f.replace("results/results_", "").replace(".json", "")
    cpus = data["system"]["effective_cpus"]
    configs.append((label, cpus, data["benchmarks"]))

# Print header
bench_names = [b["name"] for b in configs[0][2]]
print(f"\n  {'Benchmark':<45}", end="")
for label, cpus, _ in configs:
    print(f" | {label:>10}", end="")
print()
print(f"  {'-' * 45}", end="")
for _ in configs:
    print(f" | {'-' * 10}", end="")
print()

# Print mean_ms for each benchmark
for i, name in enumerate(bench_names):
    print(f"  {name:<45}", end="")
    for _, _, benchmarks in configs:
        if i < len(benchmarks):
            print(f" | {benchmarks[i]['mean_ms']:>8.2f}ms", end="")
        else:
            print(f" | {'N/A':>10}", end="")
    print()

print()
PYEOF
fi
