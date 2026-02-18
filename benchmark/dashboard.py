import marimo

__generated_with = "0.16.2"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        # FMU vs MATLAB Benchmark Dashboard

        Performance comparison across CPU configurations and simulation types.
        """
    )
    return (mo,)


@app.cell
def _():
    import pandas as pd
    import altair as alt

    # ── Raw benchmark data from the final comparison (45 results, 15 scenarios x 9 configs) ──
    # Extracted from Benchmark Compare.log

    # FMU Benchmark service results (BouncingBall via fmpy on the FMU-only benchmark)
    # These use the "BouncingBall free-run" naming from the FMU benchmark service
    fmu_bench_data = [
        # benchmark, cpu_millicores, mean_ms, p95_ms, throughput_ops
        ("BouncingBall free-run (1s)", 1000, 11.545, 15.104, 86.6),
        ("BouncingBall free-run (1s)", 2000, 8.990, 11.475, 111.2),
        ("BouncingBall free-run (1s)", 4000, 7.783, 9.090, 128.5),
        ("BouncingBall free-run (5s)", 1000, 16.459, 19.770, 60.8),
        ("BouncingBall free-run (5s)", 2000, 12.413, 17.166, 80.6),
        ("BouncingBall free-run (5s)", 4000, 11.735, 14.753, 85.2),
        ("BouncingBall free-run (10s)", 1000, 24.480, 29.923, 40.9),
        ("BouncingBall free-run (10s)", 2000, 16.286, 22.498, 61.4),
        ("BouncingBall free-run (10s)", 4000, 20.540, 26.668, 48.7),
        ("BouncingBall free-run (20s)", 1000, 24.101, 30.056, 41.5),
        ("BouncingBall free-run (20s)", 2000, 17.060, 24.249, 58.6),
        ("BouncingBall free-run (20s)", 4000, 17.187, 22.963, 58.2),
    ]

    # FMU results from the MATLAB benchmark service (FMU portion)
    # These use "FMU BouncingBall" naming
    fmu_matlab_svc_data = [
        ("FMU BouncingBall (1s)", 1000, 7.159, 9.365, 139.7),
        ("FMU BouncingBall (1s)", 2000, 8.043, 11.406, 124.3),
        ("FMU BouncingBall (1s)", 4000, 7.465, 10.093, 134.0),
        ("FMU BouncingBall (5s)", 1000, 9.983, 13.513, 100.2),
        ("FMU BouncingBall (5s)", 2000, 11.249, 14.795, 88.9),
        ("FMU BouncingBall (5s)", 4000, 9.615, 12.808, 104.0),
        ("FMU BouncingBall (10s)", 1000, 13.435, 18.142, 74.4),
        ("FMU BouncingBall (10s)", 2000, 13.496, 19.448, 74.1),
        ("FMU BouncingBall (10s)", 4000, 14.874, 19.836, 67.2),
        ("FMU BouncingBall (20s)", 1000, 12.497, 16.552, 80.0),
        ("FMU BouncingBall (20s)", 2000, 12.502, 14.093, 80.0),
        ("FMU BouncingBall (20s)", 4000, 15.342, 19.896, 65.2),
    ]

    # Other FMU micro-benchmarks (from FMU benchmark service)
    fmu_micro_data = [
        ("Model description load", 1000, 3.186, 6.932, 313.9),
        ("Model description load", 2000, 1.734, 1.956, 576.8),
        ("Model description load", 4000, 2.109, 3.062, 474.1),
        ("Simulink instant eval", 1000, 10.367, 19.467, 96.5),
        ("Simulink instant eval", 2000, 6.758, 7.676, 148.0),
        ("Simulink instant eval", 4000, 7.829, 12.428, 127.7),
        ("Rapid-fire streaming", 1000, 11.356, 15.517, 88.1),
        ("Rapid-fire streaming", 2000, 6.582, 7.582, 151.9),
        ("Rapid-fire streaming", 4000, 8.675, 11.309, 115.3),
        ("Time-series (10 pts)", 1000, 10.612, 14.205, 94.2),
        ("Time-series (10 pts)", 2000, 7.989, 10.572, 125.2),
        ("Time-series (10 pts)", 4000, 8.262, 10.926, 121.0),
        ("Time-series (100 pts)", 1000, 11.423, 15.716, 87.5),
        ("Time-series (100 pts)", 2000, 6.905, 7.792, 144.8),
        ("Time-series (100 pts)", 4000, 7.816, 10.559, 127.9),
        ("Time-series (1000 pts)", 1000, 13.441, 22.941, 74.4),
        ("Time-series (1000 pts)", 2000, 6.884, 9.652, 145.3),
        ("Time-series (1000 pts)", 4000, 6.688, 7.911, 149.5),
    ]

    # MATLAB init+terminate cost
    matlab_init_data = [
        ("MATLAB init+terminate", 1000, 700.832, 808.661, 1.4),
        ("MATLAB init+terminate", 2000, 720.059, 801.655, 1.4),
        ("MATLAB init+terminate", 4000, 709.757, 839.820, 1.4),
    ]
    return (
        alt,
        fmu_bench_data,
        fmu_matlab_svc_data,
        fmu_micro_data,
        matlab_init_data,
        pd,
    )


@app.cell
def _(
    fmu_bench_data,
    fmu_matlab_svc_data,
    fmu_micro_data,
    matlab_init_data,
    pd,
):
    cols = ["benchmark", "cpu_millicores", "mean_ms", "p95_ms", "throughput_ops"]

    df_fmu_bench = pd.DataFrame(fmu_bench_data, columns=cols)
    df_fmu_bench["source"] = "FMU Benchmark Service"
    df_fmu_bench["sim_type"] = "FMU"

    df_fmu_matlab = pd.DataFrame(fmu_matlab_svc_data, columns=cols)
    df_fmu_matlab["source"] = "MATLAB Benchmark Service"
    df_fmu_matlab["sim_type"] = "FMU"

    df_micro = pd.DataFrame(fmu_micro_data, columns=cols)
    df_micro["source"] = "FMU Benchmark Service"
    df_micro["sim_type"] = "FMU"

    df_matlab_init = pd.DataFrame(matlab_init_data, columns=cols)
    df_matlab_init["source"] = "MATLAB Benchmark Service"
    df_matlab_init["sim_type"] = "MATLAB Wheel"

    df_all = pd.concat([df_fmu_bench, df_fmu_matlab, df_micro, df_matlab_init], ignore_index=True)
    df_all["cpu_cores"] = df_all["cpu_millicores"] / 1000

    # Extract stop_time for BouncingBall benchmarks
    import re

    def extract_stop_time(name):
        m = re.search(r"\((\d+)s\)", name)
        return float(m.group(1)) if m else None

    df_all["stop_time"] = df_all["benchmark"].apply(extract_stop_time)
    return df_all, df_matlab_init, df_micro


@app.cell
def _(mo):
    mo.md(
        """
    ## FMU BouncingBall: Mean Latency vs CPU Cores

    Comparing the same BouncingBall FMU simulation across different CPU allocations
    and simulation durations. Two measurement sources: the dedicated FMU benchmark
    service and the FMU portion of the MATLAB benchmark service.
    """
    )
    return


@app.cell
def _(alt, df_all):
    # BouncingBall benchmarks only (both services)
    df_bb = df_all[
        df_all["benchmark"].str.contains("BouncingBall|free-run")
        & df_all["stop_time"].notna()
    ].copy()

    # Normalize benchmark names for comparison
    df_bb["duration"] = df_bb["stop_time"].astype(int).astype(str) + "s"

    line_mean = (
        alt.Chart(df_bb)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("cpu_cores:Q", title="CPU Cores", scale=alt.Scale(domain=[0.5, 4.5])),
            y=alt.Y("mean_ms:Q", title="Mean Latency (ms)"),
            color=alt.Color("duration:N", title="Sim Duration", sort=["1s", "5s", "10s", "20s"]),
            strokeDash=alt.StrokeDash("source:N", title="Benchmark Service"),
            tooltip=["benchmark", "source", "cpu_cores", "mean_ms", "p95_ms", "throughput_ops"],
        )
        .properties(width=1500, height=400, title="FMU BouncingBall — Mean Latency vs CPU Cores")
    )

    line_mean
    return (df_bb,)


@app.cell
def _(mo):
    mo.md(
        """
    ## FMU BouncingBall: Throughput vs CPU Cores

    Higher is better. Shows how many simulation runs per second each CPU config achieves.
    """
    )
    return


@app.cell
def _(alt, df_bb):
    line_throughput = (
        alt.Chart(df_bb)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("cpu_cores:Q", title="CPU Cores", scale=alt.Scale(domain=[0.5, 4.5])),
            y=alt.Y("throughput_ops:Q", title="Throughput (ops/s)"),
            color=alt.Color("duration:N", title="Sim Duration", sort=["1s", "5s", "10s", "20s"]),
            strokeDash=alt.StrokeDash("source:N", title="Benchmark Service"),
            tooltip=["benchmark", "source", "cpu_cores", "throughput_ops", "mean_ms"],
        )
        .properties(width=700, height=400, title="FMU BouncingBall — Throughput vs CPU Cores")
    )

    line_throughput
    return


@app.cell
def _(mo):
    mo.md(
        """
    ## P95 vs Mean Latency — Tail Latency Analysis

    Comparing P95 to mean latency reveals jitter and outlier behavior.
    Points far from the diagonal have high tail latency relative to mean.
    """
    )
    return


@app.cell
def _(alt, df_all):
    df_no_init = df_all[~df_all["benchmark"].str.contains("init")].copy()

    scatter_p95 = (
        alt.Chart(df_no_init)
        .mark_circle(size=100)
        .encode(
            x=alt.X("mean_ms:Q", title="Mean Latency (ms)"),
            y=alt.Y("p95_ms:Q", title="P95 Latency (ms)"),
            color=alt.Color("cpu_cores:N", title="CPU Cores"),
            shape=alt.Shape("source:N", title="Service"),
            tooltip=["benchmark", "source", "cpu_cores", "mean_ms", "p95_ms"],
        )
        .properties(width=600, height=400, title="P95 vs Mean Latency (excluding MATLAB init)")
    )

    diagonal = (
        alt.Chart(df_no_init)
        .mark_line(strokeDash=[4, 4], color="gray", opacity=0.5)
        .encode(
            x=alt.X("mean_ms:Q"),
            y=alt.Y("mean_ms:Q"),  # y = x diagonal
        )
    )

    scatter_p95 + diagonal
    return


@app.cell
def _(mo):
    mo.md(
        """
    ## FMU Micro-Benchmarks by CPU Config

    Grouped bar chart comparing different FMU operation types across CPU levels.
    """
    )
    return


@app.cell
def _(alt, df_micro):
    bar_micro = (
        alt.Chart(df_micro)
        .mark_bar()
        .encode(
            x=alt.X("cpu_cores:N", title="CPU Cores", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("mean_ms:Q", title="Mean Latency (ms)"),
            color=alt.Color("cpu_cores:N", title="CPU Cores"),
            column=alt.Column("benchmark:N", title="Benchmark", header=alt.Header(labelAngle=-45, labelAlign="right")),
            tooltip=["benchmark", "cpu_cores", "mean_ms", "p95_ms", "throughput_ops"],
        )
        .properties(width=90, height=300, title="FMU Micro-Benchmarks — Mean Latency by CPU")
    )

    bar_micro
    return


@app.cell
def _(mo):
    mo.md(
        """
    ## Latency Heatmap — All FMU Benchmarks

    Color intensity shows mean latency. Darker = slower.
    """
    )
    return


@app.cell
def _(alt, df_all):
    df_heatmap = df_all[~df_all["benchmark"].str.contains("init")].copy()

    heatmap = (
        alt.Chart(df_heatmap)
        .mark_rect()
        .encode(
            x=alt.X("cpu_cores:O", title="CPU Cores"),
            y=alt.Y("benchmark:N", title="Benchmark", sort="-x"),
            color=alt.Color(
                "mean_ms:Q",
                title="Mean (ms)",
                scale=alt.Scale(scheme="orangered"),
            ),
            tooltip=["benchmark", "source", "cpu_cores", "mean_ms", "p95_ms", "throughput_ops"],
        )
        .properties(width=500, height=450, title="Latency Heatmap — All Benchmarks")
    )

    heatmap
    return


@app.cell
def _(mo):
    mo.md(
        """
    ## MATLAB Runtime Init/Terminate Cost

    The cost of initializing and terminating the MATLAB Runtime package.
    This is ~700ms regardless of CPU — a fixed overhead for any MATLAB wheel usage.
    """
    )
    return


@app.cell
def _(alt, df_matlab_init):
    bar_init = (
        alt.Chart(df_matlab_init)
        .mark_bar(color="#e45756")
        .encode(
            x=alt.X(
                "cpu_millicores:N",
                title="CPU (millicores)",
                axis=alt.Axis(labelAngle=0),
            ),
            y=alt.Y("mean_ms:Q", title="Mean Latency (ms)", scale=alt.Scale(domain=[0, 900])),
            tooltip=["cpu_millicores", "mean_ms", "p95_ms"],
        )
        .properties(width=300, height=300, title="MATLAB Runtime Init+Terminate Cost")
    )

    bar_init_p95 = (
        alt.Chart(df_matlab_init)
        .mark_tick(color="black", thickness=2, size=30)
        .encode(
            x=alt.X("cpu_millicores:N"),
            y=alt.Y("p95_ms:Q"),
        )
    )

    bar_init + bar_init_p95
    return


@app.cell
def _(mo):
    mo.md(
        """
    ## Speedup from 1-core Baseline

    How much faster each benchmark gets when going from 1 to 2 or 4 CPU cores.
    """
    )
    return


@app.cell
def _(alt, df_all, pd):
    # Compute speedup relative to 1-core baseline
    df_speedup = df_all[
        ~df_all["benchmark"].str.contains("init")
        & (df_all["source"] == "FMU Benchmark Service")
    ].copy()

    baseline = df_speedup[df_speedup["cpu_millicores"] == 1000].set_index("benchmark")["mean_ms"]

    rows = []
    for _, row in df_speedup.iterrows():
        b = row["benchmark"]
        if b in baseline.index and baseline[b] > 0:
            rows.append(
                {
                    "benchmark": b,
                    "cpu_cores": row["cpu_cores"],
                    "speedup": baseline[b] / row["mean_ms"],
                }
            )

    df_sp = pd.DataFrame(rows)

    speedup_chart = (
        alt.Chart(df_sp)
        .mark_bar()
        .encode(
            x=alt.X("cpu_cores:N", title="CPU Cores", axis=alt.Axis(labelAngle=0)),
            y=alt.Y("speedup:Q", title="Speedup vs 1-core"),
            color=alt.Color("cpu_cores:N", title="CPU Cores"),
            column=alt.Column(
                "benchmark:N",
                title="Benchmark",
                header=alt.Header(labelAngle=-45, labelAlign="right"),
            ),
            tooltip=["benchmark", "cpu_cores", "speedup"],
        )
        .properties(width=60, height=300, title="Speedup vs 1-Core Baseline (FMU Benchmarks)")
    )

    # Add a reference line at speedup=1
    speedup_chart
    return


@app.cell
def _(mo):
    mo.md("""## Raw Data Table""")
    return


@app.cell
def _(df_all, mo):
    mo.ui.table(
        df_all[["benchmark", "sim_type", "source", "cpu_cores", "mean_ms", "p95_ms", "throughput_ops"]]
        .sort_values(["benchmark", "cpu_cores"])
        .reset_index(drop=True)
    )
    return


if __name__ == "__main__":
    app.run()
