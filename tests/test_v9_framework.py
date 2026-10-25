import os
import sys
import unittest
import duckdb
import numpy as np

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.data.generate_data_v9 import get_scale_label
from src.schemas.build_schemas_v9 import get_db_paths_v9, SCHEMAS_V9
from src.workload.feature_extractor_v9 import extract_syntactic_features, parse_plan_features
from src.workload.validate_workload_v9 import adapt_sql_v9


class TestV9Framework(unittest.TestCase):
    """Test suite for V9 Multi-Representation Framework."""

    @classmethod
    def setUpClass(cls):
        cls.scale_label = "100k"
        cls.db_paths = get_db_paths_v9(cls.scale_label)

    def test_schema_files_exist(self):
        """Ensure all 4 physical layout databases exist."""
        for schema in SCHEMAS_V9:
            path = self.db_paths[schema]
            self.assertTrue(os.path.exists(path), f"Missing database: {path}")

    def test_syntactic_feature_extractor(self):
        """Verify feature extraction accurately counts joins, aggs, filters, and limit."""
        sql = """
        SELECT c.region, p.category, SUM(s.total_amount), COUNT(s.sale_id)
        FROM fact_sales s
        JOIN dim_customer c ON s.customer_id = c.customer_id
        JOIN dim_product p ON s.product_id = p.product_id
        WHERE c.region = 'North' AND s.discount > 0.1
        GROUP BY c.region, p.category
        ORDER BY SUM(s.total_amount) DESC
        LIMIT 10
        """
        feats = extract_syntactic_features(sql)
        self.assertEqual(feats["num_joins"], 2)
        self.assertEqual(feats["num_aggs"], 3)  # 2 in SELECT, 1 in ORDER BY
        self.assertEqual(feats["has_group_by"], 1)
        self.assertEqual(feats["num_group_by_cols"], 2)
        self.assertEqual(feats["has_order_by"], 1)
        self.assertEqual(feats["has_limit"], 1)
        self.assertEqual(feats["limit_val"], 10)
        self.assertEqual(feats["has_customer_filter"], 1)

    def test_plan_feature_parser(self):
        """Test parsing of DuckDB EXPLAIN text into numeric plan features."""
        sample_plan = """
        ┌───────────────────────────┐
        │         PROJECTION        │
        │          ~36 rows         │
        └─────────────┬─────────────┘
        ┌─────────────┴─────────────┐
        │         HASH_JOIN         │
        │          ~36 rows         │
        └───────────────────────────┘
        """
        plan_feats = parse_plan_features(sample_plan)
        self.assertAlmostEqual(plan_feats["est_card_log1p"], np.log1p(36.0), places=2)
        self.assertEqual(plan_feats["join_count"], 1)

    def test_query_result_consistency_across_layouts(self):
        """Verify that OBT, Star-Indexed, and Agg-Projections return identical aggregate values."""
        con_obt = duckdb.connect(self.db_paths["obt"], read_only=True)
        con_star = duckdb.connect(self.db_paths["star_indexed"], read_only=True)
        con_agg = duckdb.connect(self.db_paths["agg_projections"], read_only=True)

        q_star = "SELECT c.region, ROUND(SUM(s.total_amount), 2) FROM fact_sales s JOIN dim_customer c ON s.customer_id = c.customer_id JOIN dim_date d ON s.date_id = d.date_id WHERE d.year = 2025 GROUP BY c.region ORDER BY c.region"
        q_obt = "SELECT region, ROUND(SUM(total_amount), 2) FROM obt_sales WHERE year = 2025 GROUP BY region ORDER BY region"
        q_agg = "SELECT region, ROUND(SUM(total_revenue), 2) FROM agg_sales_temporal_regional WHERE year = 2025 GROUP BY region ORDER BY region"

        res_star = con_star.execute(q_star).fetchall()
        res_obt = con_obt.execute(q_obt).fetchall()
        res_agg = con_agg.execute(q_agg).fetchall()

        con_obt.close()
        con_star.close()
        con_agg.close()

        self.assertEqual(res_star, res_obt)
        self.assertEqual(res_star, res_agg)


if __name__ == "__main__":
    unittest.main()
