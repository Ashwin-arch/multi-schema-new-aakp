import argparse
import os
import sys
import time
import duckdb

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.data.generate_data_v9 import get_scale_label, RAW_DIR
from src.utils.resource_logging import record_stage_resource

SCHEMAS_V9 = ["obt", "star_indexed", "partitioned_snow", "agg_projections"]


def get_db_paths_v9(scale_label):
    """Return dictionary of database file paths for V9 multi-representation layouts."""
    suffix = f"_{scale_label.lower()}"
    return {
        "obt": f"data/processed/obt_schema{suffix}.duckdb",
        "star_indexed": f"data/processed/star_indexed{suffix}.duckdb",
        "partitioned_snow": f"data/processed/partitioned_snow{suffix}.duckdb",
        "agg_projections": f"data/processed/agg_projections{suffix}.duckdb",
    }


def build_obt_schema(sales_csv_path, db_path):
    """Construct One-Big-Table (OBT) denormalized layout in DuckDB."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    con = duckdb.connect(db_path)

    # 1. Base fact and dimensions loaded temporarily to construct OBT
    con.execute(f"CREATE TEMP TABLE raw_sales AS SELECT * FROM read_csv_auto('{sales_csv_path}')")
    con.execute(f"CREATE TEMP TABLE raw_cust AS SELECT * FROM read_csv_auto('{RAW_DIR}/customers.csv')")
    con.execute(f"CREATE TEMP TABLE raw_prod AS SELECT * FROM read_csv_auto('{RAW_DIR}/products.csv')")
    con.execute(f"CREATE TEMP TABLE raw_date AS SELECT * FROM read_csv_auto('{RAW_DIR}/dates.csv')")

    # 2. Materialize Wide Denormalized OBT Table
    con.execute("""
        CREATE TABLE obt_sales AS
        SELECT
            s.sale_id,
            s.date_id,
            s.customer_id,
            s.product_id,
            s.quantity,
            s.discount,
            s.total_amount,
            c.customer_name,
            c.region,
            c.segment,
            p.product_name,
            p.category,
            p.unit_price,
            d.full_date,
            d.year,
            d.quarter,
            d.month,
            d.month_name,
            d.day
        FROM raw_sales s
        JOIN raw_cust c ON s.customer_id = c.customer_id
        JOIN raw_prod p ON s.product_id = p.product_id
        JOIN raw_date d ON s.date_id = d.date_id
    """)

    # 3. Materialize OBT Returns Table
    con.execute("""
        CREATE TABLE obt_returns AS
        SELECT
            s.sale_id AS return_id,
            s.date_id,
            s.customer_id,
            s.product_id,
            CASE
                WHEN s.sale_id % 10 = 0 THEN 1
                WHEN s.sale_id % 37 = 0 THEN 1
                ELSE 0
            END AS returned_quantity,
            CASE
                WHEN s.sale_id % 10 = 0 THEN ROUND(s.total_amount * 0.80, 2)
                WHEN s.sale_id % 37 = 0 THEN ROUND(s.total_amount * 0.50, 2)
                ELSE 0
            END AS refund_amount,
            c.customer_name,
            c.region,
            c.segment,
            p.product_name,
            p.category,
            d.year,
            d.quarter,
            d.month
        FROM raw_sales s
        JOIN raw_cust c ON s.customer_id = c.customer_id
        JOIN raw_prod p ON s.product_id = p.product_id
        JOIN raw_date d ON s.date_id = d.date_id
        WHERE s.sale_id % 10 = 0 OR s.sale_id % 37 = 0
    """)

    # 4. Canonical Views for Query Interoperability
    con.execute("CREATE VIEW fact_sales AS SELECT * FROM obt_sales")
    con.execute("CREATE VIEW fact_returns AS SELECT * FROM obt_returns")
    con.execute("CREATE VIEW dim_customer AS SELECT DISTINCT customer_id, customer_name, region, segment FROM obt_sales")
    con.execute("CREATE VIEW dim_product AS SELECT DISTINCT product_id, product_name, category, unit_price FROM obt_sales")
    con.execute("CREATE VIEW dim_date AS SELECT DISTINCT date_id, full_date, year, quarter, month, month_name, day FROM obt_sales")

    counts = {
        "obt_sales": con.execute("SELECT COUNT(*) FROM obt_sales").fetchone()[0],
        "obt_returns": con.execute("SELECT COUNT(*) FROM obt_returns").fetchone()[0]
    }
    con.close()
    return counts


def build_star_indexed_schema(sales_csv_path, db_path):
    """Construct Clustered Star Schema with Adaptive Radix Tree (ART) secondary indexes."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    con = duckdb.connect(db_path)

    con.execute(f"""
        CREATE TABLE dim_customer AS
        SELECT customer_id, customer_name, region, segment
        FROM read_csv_auto('{RAW_DIR}/customers.csv')
    """)

    con.execute(f"""
        CREATE TABLE dim_product AS
        SELECT product_id, product_name, category, unit_price
        FROM read_csv_auto('{RAW_DIR}/products.csv')
    """)

    con.execute(f"""
        CREATE TABLE dim_date AS
        SELECT date_id, full_date, year, quarter, month, month_name, day
        FROM read_csv_auto('{RAW_DIR}/dates.csv')
    """)

    # Clustered fact sales (sorted by customer_id, date_id)
    con.execute(f"""
        CREATE TABLE fact_sales AS
        SELECT sale_id, date_id, customer_id, product_id, quantity, discount, total_amount
        FROM read_csv_auto('{sales_csv_path}')
        ORDER BY customer_id, date_id
    """)

    # Returns table
    con.execute(f"""
        CREATE TABLE fact_returns AS
        SELECT
            sale_id AS return_id,
            date_id,
            customer_id,
            product_id,
            CASE
                WHEN sale_id % 10 = 0 THEN 1
                WHEN sale_id % 37 = 0 THEN 1
                ELSE 0
            END AS returned_quantity,
            CASE
                WHEN sale_id % 10 = 0 THEN ROUND(total_amount * 0.80, 2)
                WHEN sale_id % 37 = 0 THEN ROUND(total_amount * 0.50, 2)
                ELSE 0
            END AS refund_amount
        FROM read_csv_auto('{sales_csv_path}')
        WHERE sale_id % 10 = 0 OR sale_id % 37 = 0
        ORDER BY customer_id, date_id
    """)

    # Build ART Secondary Indexes for point / selective lookup acceleration
    con.execute("CREATE INDEX idx_star_sales_cust ON fact_sales(customer_id)")
    con.execute("CREATE INDEX idx_star_sales_prod ON fact_sales(product_id)")
    con.execute("CREATE INDEX idx_star_sales_date ON fact_sales(date_id)")
    con.execute("CREATE INDEX idx_star_cust_id ON dim_customer(customer_id)")
    con.execute("CREATE INDEX idx_star_prod_id ON dim_product(product_id)")
    con.execute("CREATE INDEX idx_star_date_id ON dim_date(date_id)")
    con.execute("CREATE INDEX idx_star_ret_cust ON fact_returns(customer_id)")

    counts = {
        "fact_sales": con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0],
        "fact_returns": con.execute("SELECT COUNT(*) FROM fact_returns").fetchone()[0]
    }
    con.close()
    return counts


def build_partitioned_snow_schema(sales_csv_path, db_path):
    """Construct Hierarchically Partitioned and Normalized Snowflake schema."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    con = duckdb.connect(db_path)

    # Normalized dimension hierarchies
    con.execute(f"""
        CREATE TABLE dim_region AS
        SELECT ROW_NUMBER() OVER () AS region_id, region
        FROM (SELECT DISTINCT region FROM read_csv_auto('{RAW_DIR}/customers.csv'))
    """)

    con.execute(f"""
        CREATE TABLE dim_segment AS
        SELECT ROW_NUMBER() OVER () AS segment_id, segment
        FROM (SELECT DISTINCT segment FROM read_csv_auto('{RAW_DIR}/customers.csv'))
    """)

    con.execute(f"""
        CREATE TABLE dim_customer AS
        SELECT
            c.customer_id,
            c.customer_name,
            r.region_id,
            s.segment_id
        FROM read_csv_auto('{RAW_DIR}/customers.csv') c
        JOIN dim_region r ON c.region = r.region
        JOIN dim_segment s ON c.segment = s.segment
    """)

    con.execute(f"""
        CREATE TABLE dim_category AS
        SELECT ROW_NUMBER() OVER () AS category_id, category
        FROM (SELECT DISTINCT category FROM read_csv_auto('{RAW_DIR}/products.csv'))
    """)

    con.execute(f"""
        CREATE TABLE dim_product AS
        SELECT
            p.product_id,
            p.product_name,
            cat.category_id,
            p.unit_price
        FROM read_csv_auto('{RAW_DIR}/products.csv') p
        JOIN dim_category cat ON p.category = cat.category
    """)

    con.execute(f"""
        CREATE TABLE dim_date AS
        SELECT date_id, full_date, year, quarter, month, month_name, day
        FROM read_csv_auto('{RAW_DIR}/dates.csv')
    """)

    # Fact sales physically sorted by date_id, customer_id (Z-order/temporal clustering)
    con.execute(f"""
        CREATE TABLE fact_sales AS
        SELECT sale_id, date_id, customer_id, product_id, quantity, discount, total_amount
        FROM read_csv_auto('{sales_csv_path}')
        ORDER BY date_id, customer_id
    """)

    con.execute(f"""
        CREATE TABLE fact_returns AS
        SELECT
            sale_id AS return_id,
            date_id,
            customer_id,
            product_id,
            CASE
                WHEN sale_id % 10 = 0 THEN 1
                WHEN sale_id % 37 = 0 THEN 1
                ELSE 0
            END AS returned_quantity,
            CASE
                WHEN sale_id % 10 = 0 THEN ROUND(total_amount * 0.80, 2)
                WHEN sale_id % 37 = 0 THEN ROUND(total_amount * 0.50, 2)
                ELSE 0
            END AS refund_amount
        FROM read_csv_auto('{sales_csv_path}')
        WHERE sale_id % 10 = 0 OR sale_id % 37 = 0
        ORDER BY date_id, customer_id
    """)

    # Compatibility views
    con.execute("""
        CREATE VIEW vw_customer AS
        SELECT c.customer_id, c.customer_name, r.region, s.segment, r.region_id, s.segment_id
        FROM dim_customer c
        JOIN dim_region r ON c.region_id = r.region_id
        JOIN dim_segment s ON c.segment_id = s.segment_id
    """)

    con.execute("""
        CREATE VIEW vw_product AS
        SELECT p.product_id, p.product_name, cat.category, p.unit_price, cat.category_id
        FROM dim_product p
        JOIN dim_category cat ON p.category_id = cat.category_id
    """)

    counts = {
        "fact_sales": con.execute("SELECT COUNT(*) FROM fact_sales").fetchone()[0],
        "fact_returns": con.execute("SELECT COUNT(*) FROM fact_returns").fetchone()[0]
    }
    con.close()
    return counts


def build_agg_projections_schema(sales_csv_path, db_path):
    """Construct Conformed Materialized Aggregate Projections & Cubes."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)

    con = duckdb.connect(db_path)

    # Base dimensional model
    con.execute(f"CREATE TABLE dim_customer AS SELECT * FROM read_csv_auto('{RAW_DIR}/customers.csv')")
    con.execute(f"CREATE TABLE dim_product AS SELECT * FROM read_csv_auto('{RAW_DIR}/products.csv')")
    con.execute(f"CREATE TABLE dim_date AS SELECT * FROM read_csv_auto('{RAW_DIR}/dates.csv')")
    con.execute(f"CREATE TABLE fact_sales AS SELECT * FROM read_csv_auto('{sales_csv_path}')")
    con.execute(f"""
        CREATE TABLE fact_returns AS
        SELECT
            sale_id AS return_id,
            date_id,
            customer_id,
            product_id,
            CASE
                WHEN sale_id % 10 = 0 THEN 1
                WHEN sale_id % 37 = 0 THEN 1
                ELSE 0
            END AS returned_quantity,
            CASE
                WHEN sale_id % 10 = 0 THEN ROUND(total_amount * 0.80, 2)
                WHEN sale_id % 37 = 0 THEN ROUND(total_amount * 0.50, 2)
                ELSE 0
            END AS refund_amount
        FROM read_csv_auto('{sales_csv_path}')
        WHERE sale_id % 10 = 0 OR sale_id % 37 = 0
    """)

    # 1. Temporal-Regional Materialized Rollup Projection
    con.execute("""
        CREATE TABLE agg_sales_temporal_regional AS
        SELECT
            d.year,
            d.quarter,
            d.month,
            c.region,
            c.segment,
            COUNT(*) AS total_transactions,
            SUM(s.quantity) AS total_quantity,
            ROUND(SUM(s.total_amount), 2) AS total_revenue,
            ROUND(AVG(s.discount), 4) AS avg_discount
        FROM fact_sales s
        JOIN dim_customer c ON s.customer_id = c.customer_id
        JOIN dim_date d ON s.date_id = d.date_id
        GROUP BY d.year, d.quarter, d.month, c.region, c.segment
    """)

    # 2. Product-Category Materialized Rollup Projection
    con.execute("""
        CREATE TABLE agg_sales_product_category AS
        SELECT
            d.year,
            p.category,
            p.product_id,
            p.product_name,
            COUNT(*) AS total_transactions,
            SUM(s.quantity) AS total_quantity,
            ROUND(SUM(s.total_amount), 2) AS total_revenue
        FROM fact_sales s
        JOIN dim_product p ON s.product_id = p.product_id
        JOIN dim_date d ON s.date_id = d.date_id
        GROUP BY d.year, p.category, p.product_id, p.product_name
    """)

    # 3. Conformed Multi-Fact Materialized Projection
    con.execute("""
        CREATE TABLE agg_conformed_multifact AS
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
        GROUP BY d.year, c.region, p.category
    """)

    # Indexes on Projections
    con.execute("CREATE INDEX idx_agg_tr_yr ON agg_sales_temporal_regional(year, region)")
    con.execute("CREATE INDEX idx_agg_pc_cat ON agg_sales_product_category(category)")
    con.execute("CREATE INDEX idx_agg_mf_yr ON agg_conformed_multifact(year, region)")

    counts = {
        "agg_sales_temporal_regional": con.execute("SELECT COUNT(*) FROM agg_sales_temporal_regional").fetchone()[0],
        "agg_sales_product_category": con.execute("SELECT COUNT(*) FROM agg_sales_product_category").fetchone()[0],
        "agg_conformed_multifact": con.execute("SELECT COUNT(*) FROM agg_conformed_multifact").fetchone()[0]
    }
    con.close()
    return counts


def build_all_schemas_v9(rows=100_000):
    """Build all four specialized physical layout databases for given scale."""
    scale_label = get_scale_label(rows)
    sales_csv = os.path.join(RAW_DIR, f"sales_{scale_label.lower()}.csv")
    if not os.path.exists(sales_csv):
        raise FileNotFoundError(f"Sales file {sales_csv} not found! Run generate_data_v9.py first.")

    db_paths = get_db_paths_v9(scale_label)
    print("=" * 70)
    print(f"BUILDING MULTI-REPRESENTATION PHYSICAL LAYOUTS (V9) - SCALE {scale_label}")
    print("=" * 70)

    t0 = time.time()
    obt_counts = build_obt_schema(sales_csv, db_paths["obt"])
    print(f" [1/4] OBT Schema: {obt_counts}")

    star_counts = build_star_indexed_schema(sales_csv, db_paths["star_indexed"])
    print(f" [2/4] Star Indexed Schema: {star_counts}")

    snow_counts = build_partitioned_snow_schema(sales_csv, db_paths["partitioned_snow"])
    print(f" [3/4] Partitioned Snowflake Schema: {snow_counts}")

    agg_counts = build_agg_projections_schema(sales_csv, db_paths["agg_projections"])
    print(f" [4/4] Materialized Aggregate Projections: {agg_counts}")

    elapsed = time.time() - t0
    total_size_mb = sum(
        os.path.getsize(p) / (1024 * 1024)
        for p in db_paths.values()
        if os.path.exists(p)
    )
    print(f"\nAll 4 physical layouts successfully materialized in {elapsed:.2f}s ({total_size_mb:.2f} MB).")
    return db_paths, elapsed, total_size_mb


def main():
    parser = argparse.ArgumentParser(description="Multi-Representation Physical Schema Builder V9")
    parser.add_argument("--rows", type=int, default=100_000, help="Row count (default: 100,000)")
    args = parser.parse_args()

    db_paths, elapsed, total_size_mb = build_all_schemas_v9(args.rows)

    record_stage_resource(
        args.rows,
        db_build_time_s=elapsed,
        total_db_size_mb=total_size_mb
    )


if __name__ == "__main__":
    main()
