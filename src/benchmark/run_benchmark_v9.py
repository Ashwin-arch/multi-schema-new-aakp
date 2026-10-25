import argparse
import json
import os
import random
import resource
import sys
import time
import duckdb
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.data.generate_data_v9 import get_scale_label
from src.schemas.build_schemas_v9 import get_db_paths_v9, SCHEMAS_V9
from src.utils.resource_logging import record_stage_resource
from src.workload.validate_workload_v9 import adapt_sql_v9

WORKLOAD_FILE_V9 = "data/processed/workload_v9.json"
RESULTS_DIR = "results/v9"
RAW_RESULTS_FILE = os.path.join(RESULTS_DIR, "scale_raw_results.csv")
QUERY_SUMMARY_FILE = os.path.join(RESULTS_DIR, "scale_query_summary.csv")
SCALE_SUMMARY_FILE = os.path.join(RESULTS_DIR, "scale_summary.csv")


def execute_timed(con, sql):
    """Execute query with high-resolution timer and forced full materialization."""
    start = time.perf_counter()
    con.execute(sql).fetchall()
    end = time.perf_counter()
    return (end - start) * 1000.0


def bootstrap_ci(values, n_bootstrap=5000, seed=42):
    """Compute 95% bootstrap confidence interval of the mean."""
    values = np.asarray(values, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    if n == 0:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, n, size=(n_bootstrap, n))
    means = values[indices].mean(axis=1)
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def run_benchmark_scale_v9(
    scale_rows=100_000,
    n_repeats=3,
    n_warmup=1,
    random_seed=42,
    workload_file=WORKLOAD_FILE_V9,
    db_paths=None,
    append_results=True
):
    """
    Run multi-representation benchmark across all 4 layouts for V9 workload.
    """
    random.seed(random_seed)
    np.random.seed(random_seed)

    scale_label = get_scale_label(scale_rows)
    if db_paths is None:
        db_paths = get_db_paths_v9(scale_label)

    print("=" * 75)
    print(f"BENCHMARK V9 MULTI-REPRESENTATION EXECUTION - SCALE {scale_label} ({scale_rows:,} rows)")
    print("=" * 75)

    with open(workload_file, "r") as f:
        workload = json.load(f)

    connections = {}
    db_sizes_mb = {}
    for schema, path in db_paths.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"Database not found: {path}")
        connections[schema] = duckdb.connect(path, read_only=True)
        db_sizes_mb[schema] = os.path.getsize(path) / (1024 * 1024)

    # 1. Warm-up
    print(f"Warm-up runs ({n_warmup} per query/schema, untimed)...")
    for item in workload:
        sql = item["sql"]
        wclass = item["workload"]
        for schema in SCHEMAS_V9:
            schema_sql = adapt_sql_v9(sql, schema, wclass)
            for _ in range(n_warmup):
                connections[schema].execute(schema_sql).fetchall()

    print("Warm-up complete. Starting timed benchmark...")

    raw_records = []
    total_expected = len(workload) * len(SCHEMAS_V9) * n_repeats
    completed = 0
    t0_benchmark = time.perf_counter()

    for q_idx, item in enumerate(workload, start=1):
        qid = item["query_id"]
        workload_type = item["workload"]
        sql = item["sql"]

        for rep in range(1, n_repeats + 1):
            rep_schemas = list(SCHEMAS_V9)
            random.shuffle(rep_schemas)

            for schema in rep_schemas:
                schema_sql = adapt_sql_v9(sql, schema, workload_type)
                try:
                    latency = execute_timed(connections[schema], schema_sql)
                    raw_records.append({
                        "query_id": qid,
                        "dataset_size": scale_rows,
                        "scale_label": scale_label,
                        "workload": workload_type,
                        "schema": schema,
                        "repetition": rep,
                        "latency_ms": latency,
                        "success": 1,
                        "error": ""
                    })
                except Exception as e:
                    raw_records.append({
                        "query_id": qid,
                        "dataset_size": scale_rows,
                        "scale_label": scale_label,
                        "workload": workload_type,
                        "schema": schema,
                        "repetition": rep,
                        "latency_ms": np.nan,
                        "success": 0,
                        "error": str(e)
                    })
                completed += 1

        if q_idx % 40 == 0 or q_idx == len(workload):
            elapsed_so_far = time.perf_counter() - t0_benchmark
            rate = completed / elapsed_so_far if elapsed_so_far > 0 else 0
            print(f"\r  Progress: {completed:,}/{total_expected:,} executions ({rate:.1f} exec/s)...", end="", flush=True)

    benchmark_duration_s = time.perf_counter() - t0_benchmark
    print(f"\nBenchmark completed in {benchmark_duration_s:.2f}s ({completed} queries executed).")

    for con in connections.values():
        con.close()

    raw_df = pd.DataFrame(raw_records)

    # Compute query summary
    succ_df = raw_df[raw_df["success"] == 1].copy()
    grouped = succ_df.groupby(["query_id", "workload", "schema"])["latency_ms"].agg(
        mean_ms="mean",
        std_ms="std",
        median_ms="median"
    ).reset_index()

    pivoted_mean = grouped.pivot(index=["query_id", "workload"], columns="schema", values="mean_ms").reset_index()
    pivoted_mean.columns.name = None

    for s in SCHEMAS_V9:
        pivoted_mean.rename(columns={s: f"{s}_mean_ms"}, inplace=True)

    mean_cols = [f"{s}_mean_ms" for s in SCHEMAS_V9]
    pivoted_mean["oracle_schema"] = pivoted_mean[mean_cols].idxmin(axis=1).str.replace("_mean_ms", "")
    pivoted_mean["oracle_mean_ms"] = pivoted_mean[mean_cols].min(axis=1)
    pivoted_mean["dataset_size"] = scale_rows
    pivoted_mean["scale_label"] = scale_label

    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Append or write raw and query summary
    if append_results and os.path.exists(RAW_RESULTS_FILE):
        existing_raw = pd.read_csv(RAW_RESULTS_FILE)
        raw_df = pd.concat([existing_raw[existing_raw["dataset_size"] != scale_rows], raw_df], ignore_index=True)
    raw_df.to_csv(RAW_RESULTS_FILE, index=False)

    if append_results and os.path.exists(QUERY_SUMMARY_FILE):
        existing_qs = pd.read_csv(QUERY_SUMMARY_FILE)
        pivoted_mean = pd.concat([existing_qs[existing_qs["dataset_size"] != scale_rows], pivoted_mean], ignore_index=True)
    pivoted_mean.to_csv(QUERY_SUMMARY_FILE, index=False)

    # Compute scale-level summary
    scale_qs = pivoted_mean[pivoted_mean["dataset_size"] == scale_rows].copy()
    oracle_counts = scale_qs["oracle_schema"].value_counts().to_dict()

    layout_means = {s: float(scale_qs[f"{s}_mean_ms"].mean()) for s in SCHEMAS_V9}
    best_fixed = min(layout_means, key=layout_means.get)
    best_fixed_mean = layout_means[best_fixed]
    oracle_mean = float(scale_qs["oracle_mean_ms"].mean())

    oracle_speedup = (best_fixed_mean - oracle_mean) / best_fixed_mean * 100.0
    relative_speedup = best_fixed_mean / oracle_mean

    scale_summary_record = {
        "dataset_size": scale_rows,
        "scale_label": scale_label,
        "queries_evaluated": len(scale_qs),
        "best_fixed_layout": best_fixed,
        "best_fixed_mean_ms": round(best_fixed_mean, 3),
        "oracle_mean_ms": round(oracle_mean, 3),
        "oracle_latency_reduction_pct": round(oracle_speedup, 2),
        "oracle_speedup_x": round(relative_speedup, 2),
    }

    for s in SCHEMAS_V9:
        scale_summary_record[f"{s}_mean_ms"] = round(layout_means[s], 3)
        scale_summary_record[f"oracle_share_{s}"] = oracle_counts.get(s, 0)

    summary_df = pd.DataFrame([scale_summary_record])
    if append_results and os.path.exists(SCALE_SUMMARY_FILE):
        existing_sum = pd.read_csv(SCALE_SUMMARY_FILE)
        summary_df = pd.concat([existing_sum[existing_sum["dataset_size"] != scale_rows], summary_df], ignore_index=True)
    summary_df.to_csv(SCALE_SUMMARY_FILE, index=False)

    print("\n" + "=" * 75)
    print(f"BENCHMARK SUMMARY RESULTS - SCALE {scale_label}")
    print("=" * 75)
    print(f"Best Fixed Layout       : {best_fixed} ({best_fixed_mean:.2f} ms)")
    print(f"Theoretical Oracle Mean : {oracle_mean:.2f} ms")
    print(f"Oracle Latency Reduction: {oracle_speedup:.2f}%")
    print(f"Oracle Relative Speedup : {relative_speedup:.2f}x faster than best fixed layout!")
    print("\nOracle Win Distribution Across Layouts:")
    for s in SCHEMAS_V9:
        wins = oracle_counts.get(s, 0)
        pct = wins / len(scale_qs) * 100
        print(f"  - {s:<20}: {wins:>3} wins ({pct:>5.1f}%) | Avg Latency: {layout_means[s]:.2f} ms")
    print("=" * 75)

    return summary_df


def main():
    parser = argparse.ArgumentParser(description="Benchmark Runner V9")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--workload", default=WORKLOAD_FILE_V9)
    args = parser.parse_args()

    t_start = time.time()
    run_benchmark_scale_v9(
        scale_rows=args.rows,
        n_repeats=args.repeats,
        n_warmup=args.warmup,
        workload_file=args.workload
    )
    t_end = time.time()

    record_stage_resource(
        args.rows,
        benchmark_execution_time_s=t_end - t_start
    )


if __name__ == "__main__":
    main()
