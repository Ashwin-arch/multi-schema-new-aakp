import argparse
import json
import os
import re
import sys
import duckdb
import numpy as np
import pandas as pd

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.data.generate_data_v9 import get_scale_label
from src.schemas.build_schemas_v9 import get_db_paths_v9, SCHEMAS_V9
from src.workload.validate_workload_v9 import adapt_sql_v9

WORKLOAD_FILE_V9 = "data/processed/workload_v9.json"


def count_pattern(text, pattern):
    return len(re.findall(pattern, text, flags=re.IGNORECASE))


def extract_syntactic_features(sql):
    """Extract strictly pre-execution syntactic and semantic query features."""
    sql_clean = " ".join(sql.strip().split())
    sql_lower = sql_clean.lower()

    num_joins = count_pattern(sql_clean, r"\bJOIN\b")
    num_aggs = count_pattern(sql_clean, r"\b(SUM|AVG|COUNT|MIN|MAX)\s*\(")
    num_predicates = count_pattern(sql_clean, r"\b(WHERE|AND|OR)\b")
    has_group_by = int(bool(re.search(r"\bGROUP\s+BY\b", sql_clean, re.I)))

    # Count group-by columns
    num_group_by_cols = 0
    if has_group_by:
        m_gb = re.search(r"\bGROUP\s+BY\s+(.*?)(?:\bORDER\b|\bHAVING\b|\bLIMIT\b|$)", sql_clean, re.I)
        if m_gb:
            num_group_by_cols = len(m_gb.group(1).split(","))

    has_order_by = int(bool(re.search(r"\bORDER\s+BY\b", sql_clean, re.I)))
    has_limit = int(bool(re.search(r"\bLIMIT\s+\d+", sql_clean, re.I)))

    limit_val = 10000
    m_lim = re.search(r"\bLIMIT\s+(\d+)", sql_clean, re.I)
    if m_lim:
        limit_val = int(m_lim.group(1))

    # Entity filter detection
    has_customer_filter = int(bool(re.search(r"\b(customer_id|customer_name|segment)\s*(=|in|like)", sql_clean, re.I)))
    has_product_filter = int(bool(re.search(r"\b(product_id|product_name|category|unit_price)\s*(=|in|>|<)", sql_clean, re.I)))
    has_date_filter = int(bool(re.search(r"\b(date_id|year|month|quarter|full_date)\s*(=|in|>|<)", sql_clean, re.I)))

    # Point filter (high selectivity key equality)
    has_point_filter = int(bool(re.search(r"\b(customer_id|product_id|date_id)\s*=\s*\d+", sql_clean, re.I)))

    # Partition filter (temporal or regional key)
    has_partition_filter = int(bool(re.search(r"\b(year|month|region)\s*(=|in)", sql_clean, re.I)))

    # Summary rollup grain candidate
    is_summary_rollup_candidate = int(
        has_group_by
        and num_aggs > 0
        and not has_point_filter
        and bool(re.search(r"\b(year|quarter|month|region|segment|category)\b", sql_clean, re.I))
    )

    has_returns = int("fact_returns" in sql_lower or "return_id" in sql_lower or "refund_amount" in sql_lower)

    # Number of projected columns in SELECT
    m_proj = re.search(r"SELECT\s+(.*?)\s+FROM\b", sql_clean, re.I)
    num_proj_cols = len(m_proj.group(1).split(",")) if m_proj else 1

    return {
        "num_joins": num_joins,
        "num_aggs": num_aggs,
        "num_predicates": num_predicates,
        "has_group_by": has_group_by,
        "num_group_by_cols": num_group_by_cols,
        "has_order_by": has_order_by,
        "has_limit": has_limit,
        "limit_val": limit_val,
        "has_customer_filter": has_customer_filter,
        "has_product_filter": has_product_filter,
        "has_date_filter": has_date_filter,
        "has_point_filter": has_point_filter,
        "has_partition_filter": has_partition_filter,
        "is_summary_rollup_candidate": is_summary_rollup_candidate,
        "has_returns": has_returns,
        "num_proj_cols": num_proj_cols,
    }


def parse_plan_features(plan_text):
    """Extract structural metrics from DuckDB pre-execution EXPLAIN plan."""
    cardinality_estimates = [
        float(m.replace("~", "").replace("rows", "").strip())
        for m in re.findall(r"~(\d+)\s+rows?", plan_text)
    ]
    est_card = cardinality_estimates[0] if cardinality_estimates else 1.0

    join_count = count_pattern(plan_text, r"\b(HASH_JOIN|INDEX_JOIN|CROSS_PRODUCT|BLOCKWISE_NL_JOIN)\b")
    filter_count = count_pattern(plan_text, r"\b(FILTER|Filters:)\b")
    scan_count = count_pattern(plan_text, r"\b(SEQ_SCAN|INDEX_SCAN)\b")
    has_index_scan = int(bool(re.search(r"\bINDEX_SCAN\b", plan_text, re.I)))
    has_agg = int(bool(re.search(r"\b(AGGREGATE|HASH_GROUP_BY|PERFECT_HASH_GROUP_BY)\b", plan_text, re.I)))
    has_top_n = int(bool(re.search(r"\b(TOP_N|ORDER_BY)\b", plan_text, re.I)))
    plan_depth = plan_text.count("┌")

    return {
        "est_card_log1p": float(np.log1p(est_card)),
        "join_count": join_count,
        "filter_count": filter_count,
        "scan_count": scan_count,
        "has_index_scan": has_index_scan,
        "has_agg": has_agg,
        "has_top_n": has_top_n,
        "plan_depth": plan_depth,
    }


def extract_features_v9(scale_rows=100_000, workload_file=WORKLOAD_FILE_V9, output_csv=None):
    """Extract complete leakage-safe feature matrix for V9 benchmark."""
    scale_label = get_scale_label(scale_rows)
    db_paths = get_db_paths_v9(scale_label)

    if output_csv is None:
        output_csv = f"data/processed/features_{scale_label.lower()}_v9.csv"

    print("=" * 70)
    print(f"EXTRACTING PRE-EXECUTION LEAKAGE-SAFE FEATURES (V9) - SCALE {scale_label}")
    print("=" * 70)

    if not os.path.exists(workload_file):
        raise FileNotFoundError(f"Workload file {workload_file} not found.")

    with open(workload_file, "r") as f:
        workload = json.load(f)

    # Open read-only connections to all 4 layout databases
    connections = {}
    for schema, path in db_paths.items():
        if not os.path.exists(path):
            raise FileNotFoundError(f"DB not found: {path}. Run build_schemas_v9.py first.")
        connections[schema] = duckdb.connect(path, read_only=True)

    rows = []
    for item in workload:
        qid = item["query_id"]
        wclass = item["workload"]
        raw_sql = item["sql"]

        record = {
            "query_id": qid,
            "workload": wclass,
            "target_layout": item.get("target_layout", "unknown"),
        }

        # 1. Syntactic AST features
        record.update(extract_syntactic_features(raw_sql))

        # 2. Plan features across candidate layouts
        for schema in SCHEMAS_V9:
            con = connections[schema]
            adapted = adapt_sql_v9(raw_sql, schema, wclass)
            try:
                plan_text = con.execute("EXPLAIN " + adapted).fetchall()[0][1]
                plan_metrics = parse_plan_features(plan_text)
            except Exception:
                plan_metrics = {
                    "est_card_log1p": float(np.log1p(scale_rows)),
                    "join_count": 0,
                    "filter_count": 0,
                    "scan_count": 1,
                    "has_index_scan": 0,
                    "has_agg": 0,
                    "has_top_n": 0,
                    "plan_depth": 1,
                }

            for k, v in plan_metrics.items():
                record[f"{schema}_{k}"] = v

        rows.append(record)

    for con in connections.values():
        con.close()

    df = pd.DataFrame(rows)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df.to_csv(output_csv, index=False)
    print(f"Extracted {len(df)} query feature rows ({df.shape[1]} features) -> {output_csv}")
    return df


def main():
    parser = argparse.ArgumentParser(description="Feature Extractor V9")
    parser.add_argument("--rows", type=int, default=100_000)
    parser.add_argument("--workload", default=WORKLOAD_FILE_V9)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    extract_features_v9(args.rows, args.workload, args.output)


if __name__ == "__main__":
    main()
