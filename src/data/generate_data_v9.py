import argparse
import csv
import os
import random
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.utils.system_check import check_scale_feasibility
from src.utils.resource_logging import record_stage_resource

SEED = 42
RAW_DIR = "data/raw"


def get_scale_label(rows):
    """Return clean human-readable scale label, e.g. 100K, 500K, 1M, 5M, 10M."""
    if rows >= 1_000_000:
        val = rows / 1_000_000
        return f"{int(val)}M" if val.is_integer() else f"{val:.1f}M"
    val = rows / 1_000
    return f"{int(val)}K" if val.is_integer() else f"{val:.1f}K"


def ensure_dimensions(num_customers=1000, num_products=60, num_dates=365):
    """
    Ensure dimension tables exist in data/raw/.
    If they exist with correct sizes, reuse them without regeneration.
    """
    os.makedirs(RAW_DIR, exist_ok=True)
    customers_path = os.path.join(RAW_DIR, "customers.csv")
    products_path = os.path.join(RAW_DIR, "products.csv")
    dates_path = os.path.join(RAW_DIR, "dates.csv")

    if (
        os.path.exists(customers_path)
        and os.path.exists(products_path)
        and os.path.exists(dates_path)
    ):
        with open(customers_path, "r") as f:
            customer_rows = sum(1 for _ in f) - 1
        with open(products_path, "r") as f:
            product_rows = sum(1 for _ in f) - 1
        with open(dates_path, "r") as f:
            date_rows = sum(1 for _ in f) - 1

        if customer_rows == num_customers and product_rows == num_products and date_rows == num_dates:
            product_prices = {}
            with open(products_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    product_prices[int(row["product_id"])] = float(row["unit_price"])
            print(f"Dimension tables already exist (C={num_customers}, P={num_products}, D={num_dates}). Reusing.")
            return product_prices

    print(f"Generating deterministic dimension tables (C={num_customers}, P={num_products}, D={num_dates}, seed={SEED})...")
    random.seed(SEED)

    # 1. Customers
    regions = ["North", "South", "East", "West"]
    segments = ["Consumer", "Corporate", "Home Office"]
    with open(customers_path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["customer_id", "customer_name", "region", "segment"])
        for cid in range(1, num_customers + 1):
            writer.writerow([
                cid,
                f"Customer_{cid}",
                random.choice(regions),
                random.choice(segments)
            ])

    # 2. Products
    if num_products <= 60:
        categories = {
            "Electronics": ["Laptop", "Mobile", "Tablet", "Monitor"],
            "Furniture": ["Chair", "Table", "Desk", "Cabinet"],
            "Office": ["Printer", "Paper", "Pen", "File"]
        }
    elif num_products <= 1000:
        categories = {
            "Electronics": [f"Electronics_{i}" for i in range(1, 71)],
            "Furniture": [f"Furniture_{i}" for i in range(1, 51)],
            "Office": [f"Office_{i}" for i in range(1, 36)],
            "Clothing": [f"Clothing_{i}" for i in range(1, 51)],
            "Sports": [f"Sports_{i}" for i in range(1, 36)],
        }
    else:
        categories = {f"Category_{i}": [f"Product_{j}" for j in range(1, 21)] for i in range(1, (num_products // 20) + 2)}

    product_prices = {}
    pid = 1
    with open(products_path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["product_id", "product_name", "category", "unit_price"])
        for cat, names in categories.items():
            for name in names:
                for i in range(1, 6):
                    if pid > num_products:
                        break
                    price = round(random.uniform(100, 5000), 2)
                    writer.writerow([pid, f"{name}_{i}", cat, price])
                    product_prices[pid] = price
                    pid += 1
                if pid > num_products:
                    break
            if pid > num_products:
                break

    # 3. Dates
    start_date = datetime(2025, 1, 1)
    with open(dates_path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow([
            "date_id", "full_date", "year", "quarter", "month", "month_name", "day"
        ])
        for i in range(num_dates):
            current = start_date + timedelta(days=i)
            writer.writerow([
                i + 1,
                current.date().isoformat(),
                current.year,
                (current.month - 1) // 3 + 1,
                current.month,
                current.strftime("%B"),
                current.day
            ])

    print(f"Dimension tables initialized: {num_customers:,} customers, {num_products:,} products, {num_dates:,} dates.")
    return product_prices


def generate_sales_data(rows=100_000, output_path=None, force=False,
                        num_customers=1000, num_products=60):
    """
    Generate sales CSV deterministically with chunked streaming.
    Reuses existing sales file if present and matches row count.
    """
    scale_label = get_scale_label(rows)
    if output_path is None:
        output_path = os.path.join(RAW_DIR, f"sales_{scale_label.lower()}.csv")

    if not force and os.path.exists(output_path):
        with open(output_path, "r") as f:
            existing_rows = sum(1 for _ in f) - 1
        if existing_rows == rows:
            print(f"Sales dataset for {scale_label} already exists ({existing_rows:,} rows). Reusing.")
            return output_path

    product_prices = ensure_dimensions(
        num_customers=num_customers,
        num_products=num_products,
        num_dates=365
    )

    print(f"Generating {rows:,} sales rows for {scale_label} (seed={SEED})...")
    random.seed(SEED)

    t0 = time.time()
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    chunk_size = 50_000
    rows_written = 0

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow([
            "sale_id", "date_id", "customer_id", "product_id",
            "quantity", "discount", "total_amount"
        ])

        while rows_written < rows:
            batch = min(chunk_size, rows - rows_written)
            chunk = []
            for i in range(batch):
                sale_id = rows_written + i + 1
                date_id = random.randint(1, 365)
                customer_id = random.randint(1, num_customers)
                product_id = random.randint(1, num_products)
                quantity = random.randint(1, 10)
                discount = round(random.choice([0.0, 0.05, 0.1, 0.15, 0.2]), 2)
                base = product_prices.get(product_id, 500.0) * quantity
                total_amount = round(base * (1.0 - discount), 2)
                chunk.append([
                    sale_id, date_id, customer_id, product_id,
                    quantity, discount, total_amount
                ])

            writer.writerows(chunk)
            rows_written += batch

    elapsed = time.time() - t0
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    print(f"Generated {rows_written:,} rows in {elapsed:.2f}s ({file_size_mb:.1f} MB) -> {output_path}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description="Deterministic Multi-Representation Data Generator V9")
    parser.add_argument("--rows", type=int, default=100_000, help="Number of sales rows (default: 100,000)")
    parser.add_argument("--num-customers", type=int, default=1000, help="Customer cardinality")
    parser.add_argument("--num-products", type=int, default=60, help="Product cardinality")
    parser.add_argument("--force", action="store_true", help="Force regeneration even if file exists")
    args = parser.parse_args()

    feasible, reason = check_scale_feasibility(args.rows)
    if not feasible:
        print(f"ABORTING: {reason}")
        sys.exit(1)

    t_start = time.time()
    csv_path = generate_sales_data(
        rows=args.rows,
        force=args.force,
        num_customers=args.num_customers,
        num_products=args.num_products
    )
    elapsed = time.time() - t_start
    file_size_mb = os.path.getsize(csv_path) / (1024 * 1024)

    record_stage_resource(
        args.rows,
        generation_time_s=elapsed,
        generation_size_mb=file_size_mb
    )


if __name__ == "__main__":
    main()
