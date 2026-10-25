import argparse
import os
import sys
import time
import duckdb
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.data.generate_data_v9 import get_scale_label
from src.schemas.build_schemas_v9 import get_db_paths_v9, SCHEMAS_V9
from src.workload.feature_extractor_v9 import extract_syntactic_features, parse_plan_features
from src.workload.validate_workload_v9 import adapt_sql_v9

RESULTS_DIR = "results/v9"
QUERY_SUMMARY_FILE = os.path.join(RESULTS_DIR, "scale_query_summary.csv")


class AdaptiveRouterV9:
    """
    Production-grade learned multi-representation query router for DuckDB warehouses.
    Dynamically routes incoming analytical queries to the lowest-latency physical layout
    (One-Big-Table, Clustered Star with ART Indexes, Partitioned Snowflake, or Materialized Projections).
    """

    def __init__(self, scale_rows=100_000, features_csv=None):
        self.scale_rows = scale_rows
        self.scale_label = get_scale_label(scale_rows)
        self.db_paths = get_db_paths_v9(self.scale_label)

        if features_csv is None:
            features_csv = f"data/processed/features_{self.scale_label.lower()}_v9.csv"
        self.features_csv = features_csv

        self._train_models()

    def _train_models(self):
        """Train internal layout cost regressors from benchmark feature matrix."""
        if not os.path.exists(self.features_csv) or not os.path.exists(QUERY_SUMMARY_FILE):
            raise FileNotFoundError("Feature matrix or benchmark query summary missing. Run benchmark first.")

        features_df = pd.read_csv(self.features_csv)
        query_summary = pd.read_csv(QUERY_SUMMARY_FILE)

        qs_scale = query_summary[query_summary["dataset_size"] == self.scale_rows]
        latency_cols = [f"{s}_mean_ms" for s in SCHEMAS_V9]
        df = features_df.merge(qs_scale[["query_id", "workload"] + latency_cols], on=["query_id", "workload"])

        excluded = ["query_id", "workload", "target_layout"] + latency_cols
        self.feature_cols = [c for c in df.columns if c not in excluded and np.issubdtype(df[c].dtype, np.number)]

        X = df[self.feature_cols].values
        self.models = {}
        for s in SCHEMAS_V9:
            y = np.log1p(df[f"{s}_mean_ms"].values)
            rf = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42, n_jobs=-1)
            rf.fit(X, y)
            self.models[s] = rf

    def route(self, raw_sql):
        """
        Analyze incoming query pre-execution and select the optimal physical layout.
        Returns detailed routing decision dict with sub-millisecond overhead.
        """
        t0 = time.perf_counter()

        # 1. Extract syntactic features
        feats = extract_syntactic_features(raw_sql)

        # 2. Extract plan features across layouts
        for schema in SCHEMAS_V9:
            db_path = self.db_paths[schema]
            adapted = adapt_sql_v9(raw_sql, schema)
            try:
                con = duckdb.connect(db_path, read_only=True)
                plan_text = con.execute("EXPLAIN " + adapted).fetchall()[0][1]
                con.close()
                plan_metrics = parse_plan_features(plan_text)
            except Exception:
                plan_metrics = {
                    "est_card_log1p": float(np.log1p(self.scale_rows)),
                    "join_count": 0,
                    "filter_count": 0,
                    "scan_count": 1,
                    "has_index_scan": 0,
                    "has_agg": 0,
                    "has_top_n": 0,
                    "plan_depth": 1,
                }
            for k, v in plan_metrics.items():
                feats[f"{schema}_{k}"] = v

        # Vectorize features
        x_vec = np.array([[feats.get(c, 0.0) for c in self.feature_cols]])

        # 3. Model prediction
        predicted_latencies = {}
        for s in SCHEMAS_V9:
            pred_log = self.models[s].predict(x_vec)[0]
            predicted_latencies[s] = round(float(np.expm1(pred_log)), 3)

        chosen_layout = min(predicted_latencies, key=predicted_latencies.get)
        t_decision = (time.perf_counter() - t0) * 1000.0

        # Estimate speedup vs running on un-optimized Star schema
        star_pred = predicted_latencies.get("star_indexed", 1.0)
        chosen_pred = predicted_latencies[chosen_layout]
        speedup_est = star_pred / chosen_pred if chosen_pred > 0 else 1.0

        return {
            "chosen_layout": chosen_layout,
            "predicted_latencies_ms": predicted_latencies,
            "decision_overhead_ms": round(t_decision, 3),
            "estimated_speedup_vs_star": round(speedup_est, 2),
            "adapted_sql": adapt_sql_v9(raw_sql, chosen_layout),
            "db_path": self.db_paths[chosen_layout],
        }

    def execute(self, raw_sql):
        """Route and execute query on the chosen optimal physical layout."""
        routing = self.route(raw_sql)
        con = duckdb.connect(routing["db_path"], read_only=True)

        t_exec_start = time.perf_counter()
        result = con.execute(routing["adapted_sql"]).fetchall()
        t_exec = (time.perf_counter() - t_exec_start) * 1000.0
        con.close()

        routing["actual_execution_ms"] = round(t_exec, 3)
        routing["row_count"] = len(result)
        return routing, result


def main():
    parser = argparse.ArgumentParser(description="Adaptive Multi-Representation Query Router V9")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--query", type=str, default=None)
    args = parser.parse_args()

    router = AdaptiveRouterV9(scale_rows=args.rows)

    sample_query = args.query or """
SELECT c.region, c.segment, p.category, d.quarter, COUNT(s.sale_id) AS tx_count, ROUND(SUM(s.total_amount), 2) AS gross_sales
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE c.region = 'North' AND p.category = 'Electronics'
GROUP BY c.region, c.segment, p.category, d.quarter
ORDER BY gross_sales DESC
LIMIT 10
""".strip()

    print("\n" + "=" * 75)
    print("ADAPTIVE QUERY ROUTER (V9) DEMONSTRATION")
    print("=" * 75)
    print("Input Query SQL:\n", sample_query)
    print("-" * 75)

    routing, result = router.execute(sample_query)
    print(f"Optimal Chosen Layout      : {routing['chosen_layout'].upper()}")
    print(f"Routing Decision Overhead  : {routing['decision_overhead_ms']} ms")
    print(f"Actual Query Execution Time: {routing['actual_execution_ms']} ms ({routing['row_count']} rows returned)")
    print(f"Estimated Speedup vs Star  : {routing['estimated_speedup_vs_star']}x")
    print("\nPredicted Latencies Across Candidate Layouts:")
    for s, ms in routing["predicted_latencies_ms"].items():
        star_flag = " <-- CHOSEN" if s == routing["chosen_layout"] else ""
        print(f"  - {s:<20}: {ms:>6.3f} ms{star_flag}")
    print("=" * 75)


if __name__ == "__main__":
    main()
