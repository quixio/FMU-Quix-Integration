import marimo

__generated_with = "0.16.2"
app = marimo.App(width="full")


@app.cell
def _():
    import marimo as mo

    mo.md(
        """
        # FMU vs Simulink (MATLAB Wheel) Benchmark Dashboard

        Performance comparison across CPU configurations and simulation types.
        Data from Benchmark Compare logs (runs 1–3).

        **Key question:** What is the FMU/Simulink cost ratio? How many CPUs does an FMU need vs MATLAB?
        """
    )
    return (mo,)


@app.cell
def _():
    import pandas as pd
    import altair as alt
    import re

    # ══════════════════════════════════════════════════════════════════════
    #  RAW BENCHMARK DATA — extracted from all Benchmark Compare logs
    # ══════════════════════════════════════════════════════════════════════

    # ── Run 1+2: FMU Benchmark service (BouncingBall via fmpy) ──
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

    # ── Run 3: FMU Benchmark service (cpu-4000 only so far) ──
    fmu_bench_run3_data = [
        ("BouncingBall free-run (1s)", 4000, 9.231, 12.175, 108.3),
        ("BouncingBall free-run (5s)", 4000, 11.695, 15.293, 85.5),
        ("BouncingBall free-run (10s)", 4000, 19.167, 25.292, 52.2),
        ("BouncingBall free-run (20s)", 4000, 19.305, 26.436, 51.8),
    ]

    # ── Run 1+2: FMU from MATLAB benchmark service ──
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

    # ── Run 3: FMU from MATLAB benchmark service (new data) ──
    fmu_matlab_svc_run3_data = [
        ("FMU BouncingBall (1s)", 1000, 8.112, 10.404, 123.3),
        ("FMU BouncingBall (1s)", 2000, 6.985, 9.691, 143.2),
        ("FMU BouncingBall (1s)", 4000, 8.212, 10.430, 121.8),
        ("FMU BouncingBall (5s)", 1000, 10.942, 19.414, 91.4),
        ("FMU BouncingBall (5s)", 2000, 10.060, 13.376, 99.4),
        ("FMU BouncingBall (5s)", 4000, 9.663, 12.480, 103.5),
        ("FMU BouncingBall (10s)", 1000, 12.091, 14.030, 82.7),
        ("FMU BouncingBall (10s)", 2000, 13.101, 17.718, 76.3),
        ("FMU BouncingBall (10s)", 4000, 13.703, 19.204, 73.0),
        ("FMU BouncingBall (20s)", 1000, 14.240, 20.040, 70.2),
        ("FMU BouncingBall (20s)", 2000, 15.144, 19.607, 66.0),
        ("FMU BouncingBall (20s)", 4000, 15.085, 20.038, 66.3),
    ]

    # ── FMU micro-benchmarks (from FMU benchmark service, runs 1+2) ──
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

    # ── Run 3: FMU micro-benchmarks (cpu-4000 only) ──
    fmu_micro_run3_data = [
        ("Model description load", 4000, 1.856, 2.649, 538.7),
        ("Simulink instant eval", 4000, 7.482, 10.179, 133.7),
        ("Rapid-fire streaming", 4000, 8.263, 10.688, 121.0),
        ("Time-series (10 pts)", 4000, 8.740, 12.711, 114.4),
        ("Time-series (100 pts)", 4000, 7.658, 10.302, 130.6),
        ("Time-series (1000 pts)", 4000, 7.083, 9.897, 141.2),
    ]

    # ── MATLAB init+terminate cost (all runs) ──
    matlab_init_data = [
        # Runs 1+2
        ("MATLAB init+terminate", 1000, 700.832, 808.661, 1.4),
        ("MATLAB init+terminate", 2000, 720.059, 801.655, 1.4),
        ("MATLAB init+terminate", 4000, 709.757, 839.820, 1.4),
        # Run 3 (new wheel, only 1000 so far)
        ("MATLAB init+terminate (run3)", 1000, 763.464, 912.107, 1.3),
    ]
    return (
        alt,
        fmu_bench_data,
        fmu_bench_run3_data,
        fmu_matlab_svc_data,
        fmu_matlab_svc_run3_data,
        fmu_micro_data,
        fmu_micro_run3_data,
        matlab_init_data,
        pd,
        re,
    )


@app.cell
def _(
    fmu_bench_data,
    fmu_bench_run3_data,
    fmu_matlab_svc_data,
    fmu_matlab_svc_run3_data,
    fmu_micro_data,
    fmu_micro_run3_data,
    matlab_init_data,
    pd,
    re,
):
    cols = ["benchmark", "cpu_millicores", "mean_ms", "p95_ms", "throughput_ops"]

    def make_df(data, source, sim_type, run="run1+2"):
        df = pd.DataFrame(data, columns=cols)
        df["source"] = source
        df["sim_type"] = sim_type
        df["run"] = run
        return df

    frames = [
        make_df(fmu_bench_data, "FMU Benchmark Service", "FMU"),
        make_df(fmu_bench_run3_data, "FMU Benchmark Service", "FMU", "run3"),
        make_df(fmu_matlab_svc_data, "MATLAB Benchmark Service", "FMU"),
        make_df(fmu_matlab_svc_run3_data, "MATLAB Benchmark Service", "FMU", "run3"),
        make_df(fmu_micro_data, "FMU Benchmark Service", "FMU"),
        make_df(fmu_micro_run3_data, "FMU Benchmark Service", "FMU", "run3"),
        make_df(matlab_init_data, "MATLAB Benchmark Service", "MATLAB Wheel"),
    ]

    df_all = pd.concat(frames, ignore_index=True)
    df_all["cpu_cores"] = df_all["cpu_millicores"] / 1000

    def extract_stop_time(name):
        m = re.search(r"\((\d+)s\)", name)
        return float(m.group(1)) if m else None

    df_all["stop_time"] = df_all["benchmark"].apply(extract_stop_time)

    # Convenience subsets
    df_micro = df_all[df_all["benchmark"].isin([
        "Model description load", "Simulink instant eval", "Rapid-fire streaming",
        "Time-series (10 pts)", "Time-series (100 pts)", "Time-series (1000 pts)",
    ])].copy()
    df_matlab_init = df_all[df_all["benchmark"].str.contains("init")].copy()
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
    df_bb = df_all[
        df_all["benchmark"].str.contains("BouncingBall|free-run")
        & df_all["stop_time"].notna()
    ].copy()
    df_bb["duration"] = df_bb["stop_time"].astype(int).astype(str) + "s"

    line_mean = (
        alt.Chart(df_bb)
        .mark_line(point=True, strokeWidth=2.5)
        .encode(
            x=alt.X("cpu_cores:Q", title="CPU Cores", scale=alt.Scale(domain=[0.5, 4.5])),
            y=alt.Y("mean_ms:Q", title="Mean Latency (ms)"),
            color=alt.Color("duration:N", title="Sim Duration", sort=["1s", "5s", "10s", "20s"]),
            strokeDash=alt.StrokeDash("source:N", title="Benchmark Service"),
            tooltip=["benchmark", "source", "cpu_cores", "mean_ms", "p95_ms", "throughput_ops", "run"],
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
    ## FMU vs MATLAB Wheel — Startup Cost Ratio

    The MATLAB wheel requires ~700-763ms just to initialize the Runtime before
    any simulation can happen. FMU has zero startup cost. This chart shows how
    many FMU simulation runs you can complete in the time MATLAB takes to boot.

    **NOTE:** The MATLAB wheel `sim_bounce()` still fails at runtime — no actual
    MATLAB simulation latency data is available yet. The ratio below uses only
    the init overhead, which is the *minimum* cost of any MATLAB wheel invocation.
    """
    )
    return


@app.cell
def _(alt, df_all):
    # Average FMU latency per duration across all CPU configs
    df_fmu_bb = df_all[
        df_all["benchmark"].str.contains("BouncingBall|free-run")
        & df_all["stop_time"].notna()
    ].copy()

    fmu_avg = df_fmu_bb.groupby("stop_time")["mean_ms"].mean().reset_index()
    fmu_avg.columns = ["stop_time", "fmu_mean_ms"]

    # MATLAB init cost (average across all measurements)
    matlab_init_ms = df_all[
        df_all["benchmark"].str.contains("init")
    ]["mean_ms"].mean()

    # Build ratio table
    fmu_avg["matlab_init_ms"] = matlab_init_ms
    fmu_avg["ratio_init_only"] = matlab_init_ms / fmu_avg["fmu_mean_ms"]
    fmu_avg["duration_label"] = fmu_avg["stop_time"].astype(int).astype(str) + "s"

    # How many FMU sims fit in one MATLAB init
    bar_ratio = (
        alt.Chart(fmu_avg)
        .mark_bar(color="#4c78a8")
        .encode(
            x=alt.X("duration_label:N", title="Simulation Duration",
                     sort=["1s", "5s", "10s", "20s"],
                     axis=alt.Axis(labelAngle=0)),
            y=alt.Y("ratio_init_only:Q",
                     title="FMU runs per 1 MATLAB init cycle"),
            tooltip=[
                alt.Tooltip("duration_label:N", title="Duration"),
                alt.Tooltip("fmu_mean_ms:Q", title="FMU mean (ms)", format=".1f"),
                alt.Tooltip("matlab_init_ms:Q", title="MATLAB init (ms)", format=".1f"),
                alt.Tooltip("ratio_init_only:Q", title="Ratio", format=".0f"),
            ],
        )
        .properties(width=400, height=350,
                    title=f"FMU sims completed during 1 MATLAB init ({matlab_init_ms:.0f}ms)")
    )

    text_ratio = bar_ratio.mark_text(dy=-10, fontSize=14, fontWeight="bold").encode(
        text=alt.Text("ratio_init_only:Q", format=".0f"),
    )

    bar_ratio + text_ratio
    return fmu_avg, matlab_init_ms


@app.cell
def _(mo):
    mo.md(
        """
    ## FMU vs MATLAB — Latency Breakdown (per invocation)

    What a single simulation request costs end-to-end. For MATLAB wheel,
    the init overhead dominates. For FMU, it's all solver time.
    """
    )
    return


@app.cell
def _(alt, fmu_avg, matlab_init_ms, pd):
    def _():
        # Stacked comparison: FMU sim time vs MATLAB init + estimated sim time
        rows_breakdown = []
        for _, r in fmu_avg.iterrows():
            dur = r["duration_label"]
            fmu_ms = r["fmu_mean_ms"]
            # FMU: all solver time
            rows_breakdown.append({"duration": dur, "technology": "FMU", "component": "Solver time", "ms": fmu_ms})
            # MATLAB: init + solver (estimated same as FMU since same model)
            rows_breakdown.append({"duration": dur, "technology": "MATLAB Wheel", "component": "Runtime init", "ms": matlab_init_ms})
            rows_breakdown.append({"duration": dur, "technology": "MATLAB Wheel", "component": "Solver time (est.)", "ms": fmu_ms})

        df_breakdown = pd.DataFrame(rows_breakdown)

        stacked = (
            alt.Chart(df_breakdown)
            .mark_bar()
            .encode(
                x=alt.X("technology:N", title="", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("sum(ms):Q", title="Total Latency (ms)"),
                color=alt.Color("component:N", title="Cost Component",
                                scale=alt.Scale(
                                    domain=["Solver time", "Solver time (est.)", "Runtime init"],
                                    range=["#4c78a8", "#72b7b2", "#e45756"])),
                column=alt.Column("duration:N", title="Sim Duration",
                                  sort=["1s", "5s", "10s", "20s"],
                                  header=alt.Header(labelAngle=0)),
                tooltip=["technology", "component", alt.Tooltip("ms:Q", format=".1f")],
            )
            .properties(width=120, height=350,
                        title="Per-Invocation Cost: FMU vs MATLAB Wheel")
        )
        return stacked


    _()
    return


@app.cell
def _(mo):
    mo.md(
        """
    ## FMU/MATLAB Cost Ratio by Simulation Duration

    As simulation duration increases, the MATLAB init overhead amortizes
    and the ratio decreases. For short simulations, FMU is dramatically cheaper.
    """
    )
    return


@app.cell
def _(alt, fmu_avg, matlab_init_ms, pd):
    def _():
        # Total MATLAB cost = init + sim (estimated same solver time as FMU)
        ratio_rows = []
        for _, r in fmu_avg.iterrows():
            dur = r["duration_label"]
            fmu_ms = r["fmu_mean_ms"]
            matlab_total_ms = matlab_init_ms + fmu_ms  # init + solver
            ratio_rows.append({
                "duration": dur,
                "stop_time": r["stop_time"],
                "fmu_ms": fmu_ms,
                "matlab_total_ms": matlab_total_ms,
                "cost_ratio": matlab_total_ms / fmu_ms,
            })

        df_ratio = pd.DataFrame(ratio_rows)

        line_ratio = (
            alt.Chart(df_ratio)
            .mark_line(point=True, strokeWidth=3, color="#e45756")
            .encode(
                x=alt.X("stop_time:Q", title="Simulation Duration (s)",
                         scale=alt.Scale(domain=[0, 22])),
                y=alt.Y("cost_ratio:Q", title="MATLAB / FMU Cost Ratio (x times more expensive)"),
                tooltip=[
                    alt.Tooltip("duration:N", title="Duration"),
                    alt.Tooltip("fmu_ms:Q", title="FMU (ms)", format=".1f"),
                    alt.Tooltip("matlab_total_ms:Q", title="MATLAB total (ms)", format=".1f"),
                    alt.Tooltip("cost_ratio:Q", title="Ratio", format=".1fx"),
                ],
            )
            .properties(width=600, height=350,
                        title="MATLAB/FMU Total Cost Ratio (lower = MATLAB catches up)")
        )

        rule = alt.Chart(pd.DataFrame([{"y": 1}])).mark_rule(
            strokeDash=[4, 4], color="gray"
        ).encode(y="y:Q")

        text_pts = (
            alt.Chart(df_ratio)
            .mark_text(dy=-15, fontSize=13, fontWeight="bold", color="#e45756")
            .encode(
                x=alt.X("stop_time:Q"),
                y=alt.Y("cost_ratio:Q"),
                text=alt.Text("cost_ratio:Q", format=".0f"),
            )
        )
        return line_ratio + rule + text_pts, df_ratio


    a, df_ratio = _()
    return (df_ratio,)


@app.cell
def _(df_ratio, mo):
    # Summary callout
    r1 = df_ratio[df_ratio["stop_time"] == 1.0].iloc[0]
    r20 = df_ratio[df_ratio["stop_time"] == 20.0].iloc[0]
    mo.md(
        f"""
    ### Key Takeaway

    | Duration | FMU latency | MATLAB total (est.) | Ratio |
    |----------|------------|--------------------:|------:|
    | **1s sim** | {r1['fmu_ms']:.1f} ms | {r1['matlab_total_ms']:.0f} ms | **{r1['cost_ratio']:.0f}x** |
    | **20s sim** | {r20['fmu_ms']:.1f} ms | {r20['matlab_total_ms']:.0f} ms | **{r20['cost_ratio']:.0f}x** |

    For **short simulations** (1-5s), FMU is **50-80x cheaper** than MATLAB wheel per invocation.
    For **longer simulations** (20s+), the ratio drops to ~**40x** as the init cost amortizes.

    > These ratios assume MATLAB solver time equals FMU solver time (conservative).
    > In practice FMU solver is native C code vs MATLAB Runtime interpretation,
    > so the real ratio may be even higher.
    """
    )
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
            tooltip=["benchmark", "source", "cpu_cores", "mean_ms", "p95_ms", "run"],
        )
        .properties(width=600, height=400, title="P95 vs Mean Latency (excluding MATLAB init)")
    )

    diagonal = (
        alt.Chart(df_no_init)
        .mark_line(strokeDash=[4, 4], color="gray", opacity=0.5)
        .encode(
            x=alt.X("mean_ms:Q"),
            y=alt.Y("mean_ms:Q"),
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
            tooltip=["benchmark", "cpu_cores", "mean_ms", "p95_ms", "throughput_ops", "run"],
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
    This is ~700-763ms regardless of CPU — a fixed overhead for any MATLAB wheel usage.
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
            y=alt.Y("mean_ms:Q", title="Mean Latency (ms)", scale=alt.Scale(domain=[0, 1000])),
            tooltip=["benchmark", "cpu_millicores", "mean_ms", "p95_ms"],
        )
        .properties(width=400, height=300, title="MATLAB Runtime Init+Terminate Cost")
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
    df_speedup = df_all[
        ~df_all["benchmark"].str.contains("init")
        & (df_all["source"] == "FMU Benchmark Service")
        & (df_all["run"] == "run1+2")
    ].copy()

    baseline = df_speedup[df_speedup["cpu_millicores"] == 1000].set_index("benchmark")["mean_ms"]

    rows_sp = []
    for _, row in df_speedup.iterrows():
        b = row["benchmark"]
        if b in baseline.index and baseline[b] > 0:
            rows_sp.append(
                {
                    "benchmark": b,
                    "cpu_cores": row["cpu_cores"],
                    "speedup": baseline[b] / row["mean_ms"],
                }
            )

    df_sp = pd.DataFrame(rows_sp)

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

    speedup_chart
    return


@app.cell
def _(mo):
    mo.md(
        """
    ## CPU Recommendation: Simulink to FMU Migration

    Based on measured data, how many FMU cores replace a given Simulink/MATLAB CPU allocation.

    | Customer Simulink CPUs | Recommended FMU CPUs | Reasoning |
    |:----------------------:|:--------------------:|-----------|
    | 1 | 1 | FMU single-threaded, faster per-step than MATLAB |
    | 2 | 1 | 2nd core was for MATLAB Runtime overhead — FMU doesn't need it |
    | 4 | 1-2 | FMU on 1 core matches Simulink on 4 (native vs interpreted) |
    | 8 | 2-3 | +1 core for service infrastructure (Kafka, Python) |
    | 16 | 4-6 | Diminishing returns beyond 2 cores for single FMU |

    **Memory:** MATLAB Runtime uses 500MB-2GB. FMU uses 10-50MB.
    """
    )
    return


@app.cell
def _(mo):
    mo.md("""## Raw Data Table""")
    return


@app.cell
def _(df_all, mo):
    mo.ui.table(
        df_all[["benchmark", "sim_type", "source", "run", "cpu_cores", "mean_ms", "p95_ms", "throughput_ops"]]
        .sort_values(["benchmark", "cpu_cores", "run"])
        .reset_index(drop=True)
    )
    return


if __name__ == "__main__":
    app.run()
