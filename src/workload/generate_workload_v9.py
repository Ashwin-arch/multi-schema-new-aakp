import argparse
import json
import os
import random
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

OUTPUT_FILE = "data/processed/workload_v9.json"
SEED = 2026

REGIONS = ["North", "South", "East", "West"]
SEGMENTS = ["Consumer", "Corporate", "Home Office"]
CATEGORIES = ["Electronics", "Furniture", "Office"]
YEARS = [2025]
QUARTERS = [1, 2, 3, 4]
MONTHS = list(range(1, 13))

AGGREGATES = [
    ("SUM(s.total_amount)", "total_revenue"),
    ("AVG(s.total_amount)", "avg_revenue"),
    ("COUNT(s.sale_id)", "order_count"),
    ("SUM(s.quantity)", "total_units"),
]


def generate_point_lookups(count=40, num_customers=1000, num_products=60):
    """Point and high-selectivity queries targeting star_indexed (ART index / clustering)."""
    queries = []
    for i in range(count):
        qid = f"Q_PL_{i+1:03d}"
        q_type = i % 5

        if q_type == 0:
            cid = random.randint(1, num_customers)
            sql = f"""
SELECT s.sale_id, s.date_id, s.quantity, s.discount, s.total_amount, c.customer_name, c.region
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
WHERE s.customer_id = {cid}
ORDER BY s.date_id
""".strip()
            desc = f"Single-customer transaction history for customer_id={cid}"

        elif q_type == 1:
            pid = random.randint(1, num_products)
            sql = f"""
SELECT s.sale_id, s.date_id, s.quantity, s.total_amount, p.product_name, p.category
FROM fact_sales s
JOIN dim_product p ON s.product_id = p.product_id
WHERE s.product_id = {pid}
ORDER BY s.total_amount DESC
LIMIT 20
""".strip()
            desc = f"Top-20 transactions for product_id={pid}"

        elif q_type == 2:
            cid = random.randint(1, num_customers)
            did = random.randint(1, 365)
            sql = f"""
SELECT s.sale_id, s.quantity, s.discount, s.total_amount, c.customer_name, p.product_name
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
WHERE s.customer_id = {cid} AND s.date_id = {did}
""".strip()
            desc = f"Exact customer ({cid}) and date ({did}) transaction lookup"

        elif q_type == 3:
            cid = random.randint(1, num_customers)
            sql = f"""
SELECT r.return_id, r.date_id, r.returned_quantity, r.refund_amount, c.customer_name, p.product_name
FROM fact_returns r
JOIN dim_customer c ON r.customer_id = c.customer_id
JOIN dim_product p ON r.product_id = p.product_id
WHERE r.customer_id = {cid}
ORDER BY r.date_id
""".strip()
            desc = f"Return audit lookup for customer_id={cid}"

        else:
            pid = random.randint(1, num_products)
            cid = random.randint(1, num_customers)
            sql = f"""
SELECT s.sale_id, s.quantity, s.total_amount, c.region, p.category
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
WHERE s.product_id = {pid} AND s.customer_id = {cid}
""".strip()
            desc = f"Cross-entity pair lookup (cust={cid}, prod={pid})"

        queries.append({
            "query_id": qid,
            "workload": "point_lookup",
            "target_layout": "star_indexed",
            "sql": sql,
            "description": desc
        })
    return queries


def generate_wide_multidim(count=40):
    """Multi-dimensional wide analytical scans targeting One-Big-Table (OBT)."""
    queries = []
    for i in range(count):
        qid = f"Q_WM_{i+1:03d}"
        region = random.choice(REGIONS)
        segment = random.choice(SEGMENTS)
        category = random.choice(CATEGORIES)
        discount_thresh = round(random.uniform(0.05, 0.15), 2)
        price_thresh = random.randint(500, 2500)

        sql = f"""
SELECT
    c.region,
    c.segment,
    p.category,
    d.quarter,
    COUNT(s.sale_id) AS tx_count,
    ROUND(SUM(s.total_amount), 2) AS gross_sales,
    ROUND(AVG(s.discount), 4) AS mean_discount
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE (c.region = '{region}' OR c.segment = '{segment}')
  AND p.category = '{category}'
  AND s.discount >= {discount_thresh}
  AND p.unit_price >= {price_thresh}
GROUP BY c.region, c.segment, p.category, d.quarter
ORDER BY gross_sales DESC
""".strip()

        desc = f"Wide multi-dimensional correlation for {category} in {region}/{segment}"
        queries.append({
            "query_id": qid,
            "workload": "wide_multidim",
            "target_layout": "obt",
            "sql": sql,
            "description": desc
        })
    return queries


def generate_partition_pruned(count=40):
    """Partition and cluster-filtered queries targeting partitioned_snow."""
    queries = []
    for i in range(count):
        qid = f"Q_PP_{i+1:03d}"
        region = random.choice(REGIONS)
        month = random.choice(MONTHS)
        year = random.choice(YEARS)

        sql = f"""
SELECT
    c.customer_name,
    p.product_name,
    p.category,
    s.quantity,
    s.total_amount,
    d.full_date
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE d.year = {year}
  AND d.month = {month}
  AND c.region = '{region}'
ORDER BY s.total_amount DESC
LIMIT 50
""".strip()

        desc = f"Partition-pruned slice: Year {year}, Month {month}, Region {region}"
        queries.append({
            "query_id": qid,
            "workload": "partition_pruned",
            "target_layout": "partitioned_snow",
            "sql": sql,
            "description": desc
        })
    return queries


def generate_summary_rollups(count=40):
    """Dashboard summary queries matching conformed materialized aggregate projections."""
    queries = []
    for i in range(count):
        qid = f"Q_SR_{i+1:03d}"
        q_type = i % 3

        if q_type == 0:
            region = random.choice(REGIONS)
            sql = f"""
SELECT
    d.year,
    d.quarter,
    c.region,
    c.segment,
    COUNT(s.sale_id) AS total_transactions,
    SUM(s.quantity) AS total_quantity,
    ROUND(SUM(s.total_amount), 2) AS total_revenue,
    ROUND(AVG(s.discount), 4) AS avg_discount
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE c.region = '{region}'
GROUP BY d.year, d.quarter, c.region, c.segment
ORDER BY d.year, d.quarter, total_revenue DESC
""".strip()
            desc = f"Temporal-regional rollup for Region {region}"

        elif q_type == 1:
            category = random.choice(CATEGORIES)
            sql = f"""
SELECT
    d.year,
    p.category,
    p.product_id,
    p.product_name,
    COUNT(s.sale_id) AS total_transactions,
    SUM(s.quantity) AS total_quantity,
    ROUND(SUM(s.total_amount), 2) AS total_revenue
FROM fact_sales s
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE p.category = '{category}'
GROUP BY d.year, p.category, p.product_id, p.product_name
ORDER BY total_revenue DESC
""".strip()
            desc = f"Product-category rollup for Category {category}"

        else:
            region = random.choice(REGIONS)
            category = random.choice(CATEGORIES)
            sql = f"""
SELECT
    d.year,
    c.region,
    p.category,
    COUNT(DISTINCT s.sale_id) AS total_sales_count,
    ROUND(SUM(s.total_amount), 2) AS total_sales_amount,
    COUNT(DISTINCT r.return_id) AS total_returns_count,
    ROUND(COALESCE(SUM(r.refund_amount), 0), 2) AS total_refund_amount,
    ROUND(SUM(s.total_amount) - COALESCE(SUM(r.refund_amount), 0), 2) AS net_revenue
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_date d ON s.date_id = d.date_id
LEFT JOIN fact_returns r ON s.sale_id = r.return_id
WHERE c.region = '{region}' AND p.category = '{category}'
GROUP BY d.year, c.region, p.category
ORDER BY net_revenue DESC
""".strip()
            desc = f"Conformed multi-fact KPI rollup for {region} / {category}"

        queries.append({
            "query_id": qid,
            "workload": "summary_rollup",
            "target_layout": "agg_projections",
            "sql": sql,
            "description": desc
        })
    return queries


def generate_mixed_analytical(count=40):
    """Mixed analytical joins and reporting queries."""
    queries = []
    for i in range(count):
        qid = f"Q_MA_{i+1:03d}"
        q, agg_col = random.choice(AGGREGATES)
        segment = random.choice(SEGMENTS)
        limit_val = random.choice([5, 10, 20])

        sql = f"""
SELECT
    p.product_name,
    p.category,
    c.region,
    {q} AS metric_val
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
JOIN dim_date d ON s.date_id = d.date_id
WHERE c.segment = '{segment}'
GROUP BY p.product_name, p.category, c.region
ORDER BY metric_val DESC
LIMIT {limit_val}
""".strip()

        desc = f"Top {limit_val} products in segment '{segment}' by {agg_col}"
        queries.append({
            "query_id": qid,
            "workload": "mixed_analytical",
            "target_layout": "obt",
            "sql": sql,
            "description": desc
        })
    return queries


def generate_multifact_correlation(count=40):
    """Conformed multi-fact analysis comparing sales and returns behavior."""
    queries = []
    for i in range(count):
        qid = f"Q_MC_{i+1:03d}"
        region = random.choice(REGIONS)
        category = random.choice(CATEGORIES)

        sql = f"""
SELECT
    c.customer_name,
    p.category,
    ROUND(SUM(s.total_amount), 2) AS total_spent,
    ROUND(COALESCE(SUM(r.refund_amount), 0), 2) AS total_refunded,
    ROUND(COALESCE(SUM(r.refund_amount), 0) / NULLIF(SUM(s.total_amount), 0) * 100, 2) AS return_rate_pct
FROM fact_sales s
JOIN dim_customer c ON s.customer_id = c.customer_id
JOIN dim_product p ON s.product_id = p.product_id
LEFT JOIN fact_returns r ON s.sale_id = r.return_id
WHERE c.region = '{region}' AND p.category = '{category}'
GROUP BY c.customer_name, p.category
HAVING SUM(s.total_amount) > 1000
ORDER BY return_rate_pct DESC
LIMIT 15
""".strip()

        desc = f"Customer return rate ranking for {category} in {region}"
        queries.append({
            "query_id": qid,
            "workload": "multifact_correlation",
            "target_layout": "obt",
            "sql": sql,
            "description": desc
        })
    return queries


def generate_workload_v9(output_file=OUTPUT_FILE, count_per_class=40):
    """Generate balanced 240-query analytical benchmark workload."""
    random.seed(SEED)
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    workload = []
    workload.extend(generate_point_lookups(count_per_class))
    workload.extend(generate_wide_multidim(count_per_class))
    workload.extend(generate_partition_pruned(count_per_class))
    workload.extend(generate_summary_rollups(count_per_class))
    workload.extend(generate_mixed_analytical(count_per_class))
    workload.extend(generate_multifact_correlation(count_per_class))

    with open(output_file, "w") as f:
        json.dump(workload, f, indent=2)

    counts = {}
    for q in workload:
        w = q["workload"]
        counts[w] = counts.get(w, 0) + 1

    print("=" * 65)
    print(f"MULTI-REPRESENTATION BENCHMARK WORKLOAD GENERATOR (V9)")
    print("=" * 65)
    print(f"Total queries generated : {len(workload)}")
    for k, v in counts.items():
        print(f"  - {k:<25}: {v} queries")
    print(f"Saved to: {output_file}")
    return workload


def main():
    parser = argparse.ArgumentParser(description="Workload Generator V9")
    parser.add_argument("--output", default=OUTPUT_FILE, help="Output path for workload JSON")
    parser.add_argument("--count-per-class", type=int, default=40, help="Number of queries per class (default: 40)")
    args = parser.parse_args()

    generate_workload_v9(args.output, args.count_per_class)


if __name__ == "__main__":
    main()
