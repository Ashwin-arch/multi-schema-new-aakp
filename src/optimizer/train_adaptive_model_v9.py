import argparse
import os
import sys
import time
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.model_selection import StratifiedKFold, LeaveOneGroupOut

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.data.generate_data_v9 import get_scale_label
from src.schemas.build_schemas_v9 import SCHEMAS_V9
from src.benchmark.run_benchmark_v9 import bootstrap_ci

RESULTS_DIR = "results/v9"
QUERY_SUMMARY_FILE = os.path.join(RESULTS_DIR, "scale_query_summary.csv")
ADAPTIVE_QUERY_FILE = os.path.join(RESULTS_DIR, "adaptive_model_query_results.csv")
ADAPTIVE_SUMMARY_FILE = os.path.join(RESULTS_DIR, "adaptive_model_summary.csv")
FEATURE_IMP_FILE = os.path.join(RESULTS_DIR, "feature_importance.csv")


def evaluate_adaptive_model_v9(scale_rows=100_000, features_csv=None, cv_mode="stratified", append_results=True):
    """
    Train and evaluate the adaptive multi-layout selection model for a given scale.
    Supports both:
      - 'stratified': Realistic 5-fold cross-validation with stratified query trace representation.
      - 'lowo': Leave-One-Workload-Out cross-validation evaluating extreme zero-shot generalization.
    """
    scale_label = get_scale_label(scale_rows)
    if features_csv is None:
        features_csv = f"data/processed/features_{scale_label.lower()}_v9.csv"

    print("=" * 80)
    print(f"EVALUATING LEARNED MULTI-LAYOUT ROUTER (V9) - SCALE {scale_label} ({scale_rows:,} rows)")
    print(f"Validation Strategy: {cv_mode.upper()} CV")
    print("=" * 80)

    if not os.path.exists(features_csv):
        raise FileNotFoundError(f"Features file not found: {features_csv}")
    if not os.path.exists(QUERY_SUMMARY_FILE):
        raise FileNotFoundError(f"Query summary file not found: {QUERY_SUMMARY_FILE}. Run benchmark first.")

    features_df = pd.read_csv(features_csv)
    query_summary = pd.read_csv(QUERY_SUMMARY_FILE)

    qs_scale = query_summary[query_summary["dataset_size"] == scale_rows].copy()
    if qs_scale.empty:
        raise ValueError(f"No benchmark data found for dataset_size={scale_rows}")

    latency_cols = [f"{s}_mean_ms" for s in SCHEMAS_V9]
    merge_cols = ["query_id", "workload"] + latency_cols + ["oracle_schema", "oracle_mean_ms"]

    df = features_df.merge(qs_scale[merge_cols], on=["query_id", "workload"], how="inner")
    if len(df) == 0:
        raise ValueError("Merged dataset is empty! Check query IDs.")

    excluded = ["query_id", "workload", "target_layout", "oracle_schema", "oracle_mean_ms"] + latency_cols
    feature_cols = [c for c in df.columns if c not in excluded and np.issubdtype(df[c].dtype, np.number)]
    print(f"Loaded {len(df)} query samples with {len(feature_cols)} pre-execution features.")

    fixed_means = {s: df[f"{s}_mean_ms"].mean() for s in SCHEMAS_V9}
    best_fixed_layout = min(fixed_means, key=fixed_means.get)
    best_fixed_mean_ms = fixed_means[best_fixed_layout]

    query_results = []
    feature_importances = []
    t_inference_list = []

    # Configure CV splits
    if cv_mode == "lowo":
        splitter = LeaveOneGroupOut()
        splits = list(splitter.split(df, groups=df["workload"]))
    else:
        splitter = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        splits = list(splitter.split(df, df["workload"]))

    for fold_idx, (train_idx, test_idx) in enumerate(splits, start=1):
        train_df = df.iloc[train_idx].copy()
        test_df = df.iloc[test_idx].copy()

        X_train = train_df[feature_cols].values
        X_test = test_df[feature_cols].values

        pred_latencies = {}
        for s in SCHEMAS_V9:
            y_train = np.log1p(train_df[f"{s}_mean_ms"].values)

            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                random_state=42,
                n_jobs=-1
            )
            model.fit(X_train, y_train)

            t0_inf = time.perf_counter()
            pred_log = model.predict(X_test)
            t_inf = (time.perf_counter() - t0_inf) / len(test_df) * 1000.0
            t_inference_list.append(t_inf)

            pred_latencies[s] = np.expm1(pred_log)

            if fold_idx == 1:
                for fcol, imp in zip(feature_cols, model.feature_importances_):
                    feature_importances.append({"schema": s, "feature": fcol, "importance": imp})

        pred_matrix = np.column_stack([pred_latencies[s] for s in SCHEMAS_V9])
        chosen_indices = np.argmin(pred_matrix, axis=1)

        test_df = test_df.reset_index(drop=True)
        for i, row in test_df.iterrows():
            chosen_schema = SCHEMAS_V9[chosen_indices[i]]
            actual_chosen_ms = row[f"{chosen_schema}_mean_ms"]
            oracle_ms = row["oracle_mean_ms"]
            regret_ms = actual_chosen_ms - oracle_ms

            query_results.append({
                "dataset_size": scale_rows,
                "scale_label": scale_label,
                "cv_mode": cv_mode,
                "query_id": row["query_id"],
                "workload": row["workload"],
                "oracle_schema": row["oracle_schema"],
                "chosen_schema": chosen_schema,
                "oracle_match": int(chosen_schema == row["oracle_schema"]),
                "chosen_ms": actual_chosen_ms,
                "oracle_ms": oracle_ms,
                "best_fixed_ms": row[f"{best_fixed_layout}_mean_ms"],
                "regret_ms": regret_ms,
                "relative_regret_pct": (regret_ms / oracle_ms) * 100.0 if oracle_ms > 0 else 0.0,
            })

    results_df = pd.DataFrame(query_results)

    total_queries = len(results_df)
    matches = results_df["oracle_match"].sum()
    match_rate = matches / total_queries * 100.0

    adaptive_mean_ms = results_df["chosen_ms"].mean()
    oracle_mean_ms = results_df["oracle_ms"].mean()
    mean_regret_ms = results_df["regret_ms"].mean()

    adaptive_vs_best_fixed_pct = (best_fixed_mean_ms - adaptive_mean_ms) / best_fixed_mean_ms * 100.0
    adaptive_speedup_x = best_fixed_mean_ms / adaptive_mean_ms
    oracle_vs_best_fixed_pct = (best_fixed_mean_ms - oracle_mean_ms) / best_fixed_mean_ms * 100.0
    oracle_speedup_x = best_fixed_mean_ms / oracle_mean_ms

    diff_adaptive_fixed = results_df["best_fixed_ms"].values - results_df["chosen_ms"].values
    ci_low, ci_high = bootstrap_ci(diff_adaptive_fixed)
    avg_inference_ms = float(np.mean(t_inference_list))

    print("\n" + "=" * 80)
    print(f"LEARNED MULTI-LAYOUT ROUTER EVALUATION RESULTS ({cv_mode.upper()} CV) - SCALE {scale_label}")
    print("=" * 80)
    print(f"Oracle Match Rate            : {match_rate:.2f}% ({matches}/{total_queries} queries)")
    print(f"Best Fixed Layout Baseline   : {best_fixed_layout} ({best_fixed_mean_ms:.3f} ms)")
    print(f"Adaptive Router Mean Latency : {adaptive_mean_ms:.3f} ms")
    print(f"Theoretical Oracle Latency   : {oracle_mean_ms:.3f} ms")
    print(f"Mean Regret vs Oracle        : {mean_regret_ms:.3f} ms")
    print("-" * 80)
    print(f"Adaptive Latency Reduction   : {adaptive_vs_best_fixed_pct:+.2f}% over Best Fixed Layout!")
    print(f"Adaptive Speedup Factor      : {adaptive_speedup_x:.2f}x faster than Best Fixed!")
    print(f"Theoretical Oracle Speedup   : {oracle_speedup_x:.2f}x (Max opportunity: {oracle_vs_best_fixed_pct:.2f}%)")
    print(f"95% Bootstrap CI (Gain ms)   : [{ci_low:+.3f}, {ci_high:+.3f}] ms")
    print(f"Router Decision Overhead     : {avg_inference_ms:.3f} ms (sub-millisecond routing)")
    print("=" * 80)

    # Per-workload breakdown
    print("\nPer-Workload Class Performance Breakdown:")
    wl_summary = results_df.groupby("workload").agg(
        queries=("query_id", "count"),
        match_rate=("oracle_match", lambda x: np.mean(x) * 100.0),
        adaptive_ms=("chosen_ms", "mean"),
        best_fixed_ms=("best_fixed_ms", "mean"),
        oracle_ms=("oracle_ms", "mean"),
    ).reset_index()

    wl_summary["speedup_x"] = wl_summary["best_fixed_ms"] / wl_summary["adaptive_ms"]
    for _, r in wl_summary.iterrows():
        print(f"  - {r['workload']:<25}: Match {r['match_rate']:>5.1f}% | Adaptive: {r['adaptive_ms']:>6.2f} ms | Best Fixed: {r['best_fixed_ms']:>6.2f} ms | Speedup: {r['speedup_x']:>5.2f}x")

    # Save outputs
    os.makedirs(RESULTS_DIR, exist_ok=True)
    if append_results and os.path.exists(ADAPTIVE_QUERY_FILE):
        existing_aq = pd.read_csv(ADAPTIVE_QUERY_FILE)
        if "cv_mode" in existing_aq.columns:
            mask = (existing_aq["dataset_size"] == scale_rows) & (existing_aq["cv_mode"] == cv_mode)
            results_df = pd.concat([existing_aq[~mask], results_df], ignore_index=True)
        else:
            results_df = pd.concat([existing_aq[existing_aq["dataset_size"] != scale_rows], results_df], ignore_index=True)
    results_df.to_csv(ADAPTIVE_QUERY_FILE, index=False)

    summary_record = {
        "dataset_size": scale_rows,
        "scale_label": scale_label,
        "cv_mode": cv_mode,
        "queries_evaluated": total_queries,
        "best_fixed_layout": best_fixed_layout,
        "best_fixed_mean_ms": round(best_fixed_mean_ms, 3),
        "adaptive_mean_ms": round(adaptive_mean_ms, 3),
        "oracle_mean_ms": round(oracle_mean_ms, 3),
        "oracle_match_rate_pct": round(match_rate, 2),
        "mean_regret_ms": round(mean_regret_ms, 3),
        "adaptive_latency_reduction_pct": round(adaptive_vs_best_fixed_pct, 2),
        "adaptive_speedup_x": round(adaptive_speedup_x, 2),
        "ci_95_low_ms": round(ci_low, 3),
        "ci_95_high_ms": round(ci_high, 3),
        "avg_decision_overhead_ms": round(avg_inference_ms, 3),
    }

    sum_df = pd.DataFrame([summary_record])
    if append_results and os.path.exists(ADAPTIVE_SUMMARY_FILE):
        existing_sum = pd.read_csv(ADAPTIVE_SUMMARY_FILE)
        if "cv_mode" in existing_sum.columns:
            mask = (existing_sum["dataset_size"] == scale_rows) & (existing_sum["cv_mode"] == cv_mode)
            sum_df = pd.concat([existing_sum[~mask], sum_df], ignore_index=True)
        else:
            sum_df = pd.concat([existing_sum[existing_sum["dataset_size"] != scale_rows], sum_df], ignore_index=True)
    sum_df.to_csv(ADAPTIVE_SUMMARY_FILE, index=False)

    if feature_importances:
        fi_df = pd.DataFrame(feature_importances)
        fi_df.to_csv(FEATURE_IMP_FILE, index=False)

    return summary_record


def main():
    parser = argparse.ArgumentParser(description="Adaptive Model Trainer V9")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--cv", default="stratified", choices=["stratified", "lowo"])
    parser.add_argument("--features", default=None)
    args = parser.parse_args()

    evaluate_adaptive_model_v9(args.rows, args.features, cv_mode=args.cv)


if __name__ == "__main__":
    main()
