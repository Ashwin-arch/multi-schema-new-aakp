import os
import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# Paths
FIG_DIR = "results/figures/v9"
OUTPUT_PPTX = "Adaptive_Multi_Schema_Data_Warehouse.pptx"

# Colors
COLOR_PRIMARY = RGBColor(30, 58, 138)     # Navy #1E3A8A
COLOR_SECONDARY = RGBColor(13, 148, 136)  # Teal #0D9488
COLOR_DARK = RGBColor(15, 23, 42)         # Slate 900 #0F172A
COLOR_MUTED = RGBColor(71, 85, 105)       # Slate 600 #475569
COLOR_LIGHT_BG = RGBColor(248, 250, 252)  # Slate 50 #F8FAFC
COLOR_CARD_BG = RGBColor(255, 255, 255)   # White
COLOR_CARD_BORDER = RGBColor(226, 232, 240) # Border #E2E8F0
COLOR_ACCENT = RGBColor(234, 88, 12)      # Amber/Orange #EA580C
COLOR_SUCCESS = RGBColor(16, 185, 129)    # Emerald #10B981


def set_shape_flat(shape, fill_color, border_color=None):
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if border_color:
        shape.line.color.rgb = border_color
        shape.line.width = Pt(1.5)
    else:
        shape.line.fill.background()


def add_header(slide, title_text, category="RESEARCH & ARCHITECTURE PRESENTATION"):
    """Add modern standard header banner to a slide."""
    # Top thin accent line
    top_bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.1))
    set_shape_flat(top_bar, COLOR_SECONDARY)

    # Category tracker
    cat_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.35), Inches(11.5), Inches(0.3))
    tf_c = cat_box.text_frame
    tf_c.word_wrap = True
    p_c = tf_c.paragraphs[0]
    p_c.text = category.upper()
    p_c.font.size = Pt(10)
    p_c.font.bold = True
    p_c.font.color.rgb = COLOR_SECONDARY

    # Title text
    title_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.65), Inches(11.5), Inches(0.7))
    tf_t = title_box.text_frame
    tf_t.word_wrap = True
    p_t = tf_t.paragraphs[0]
    p_t.text = title_text
    p_t.font.size = Pt(24)
    p_t.font.bold = True
    p_t.font.color.rgb = COLOR_PRIMARY


def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # =========================================================================
    # SLIDE 1: Title Slide
    # =========================================================================
    slide1 = prs.slides.add_slide(blank_layout)

    # Background accent rect
    bg = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    set_shape_flat(bg, COLOR_LIGHT_BG)

    top_stripe = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.2))
    set_shape_flat(top_stripe, COLOR_SECONDARY)

    # Left colored accent card
    card = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.0), Inches(11.733), Inches(5.6))
    set_shape_flat(card, COLOR_CARD_BG, COLOR_CARD_BORDER)

    tbox = slide1.shapes.add_textbox(Inches(1.2), Inches(1.4), Inches(11.0), Inches(2.2))
    tf = tbox.text_frame
    tf.word_wrap = True

    p0 = tf.paragraphs[0]
    p0.text = "RESEARCH PROJECT PRESENTATION"
    p0.font.size = Pt(12)
    p0.font.bold = True
    p0.font.color.rgb = COLOR_SECONDARY
    p0.space_after = Pt(10)

    p1 = tf.add_paragraph()
    p1.text = "Adaptive Multi-Schema Data Warehouse"
    p1.font.size = Pt(36)
    p1.font.bold = True
    p1.font.color.rgb = COLOR_PRIMARY
    p1.space_after = Pt(8)

    p2 = tf.add_paragraph()
    p2.text = "An ML-Based Query-Aware Schema Selection & Physical Layout Framework"
    p2.font.size = Pt(18)
    p2.font.color.rgb = COLOR_MUTED

    # Team Box
    team_box = slide1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.2), Inches(3.9), Inches(11.0), Inches(2.3))
    set_shape_flat(team_box, RGBColor(241, 245, 249), COLOR_CARD_BORDER)

    tb_frame = team_box.text_frame
    tb_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    tb_frame.word_wrap = True

    p_th = tb_frame.paragraphs[0]
    p_th.text = "PROJECT TEAM MEMBERS"
    p_th.font.size = Pt(11)
    p_th.font.bold = True
    p_th.font.color.rgb = COLOR_PRIMARY
    p_th.space_after = Pt(8)

    p_tm = tb_frame.add_paragraph()
    p_tm.text = "• Ashwin Kumar G rao          • Aritra das\n• Krishna Teja                         • Priyanshu Goyal"
    p_tm.font.size = Pt(17)
    p_tm.font.bold = True
    p_tm.font.color.rgb = COLOR_DARK
    p_tm.space_after = Pt(10)

    p_tech = tb_frame.add_paragraph()
    p_tech.text = "Backend: DuckDB Vectorized OLAP  |  ML Engine: Plan-Cost Multi-Target Regressors  |  UI: Streamlit Web Dashboard"
    p_tech.font.size = Pt(11)
    p_tech.font.color.rgb = COLOR_MUTED

    # =========================================================================
    # SLIDE 2: Introduction & Motivation
    # =========================================================================
    slide2 = prs.slides.add_slide(blank_layout)
    add_header(slide2, "Introduction & Motivation: The Data Warehouse Dilemma", "Problem Formulation")

    # Left Card: Traditional Approach
    c1 = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    set_shape_flat(c1, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf1 = c1.text_frame
    tf1.word_wrap = True

    p = tf1.paragraphs[0]
    p.text = "The Single-Schema Dogma"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(14)

    points1 = [
        ("Static Commitments: ", "Data engineers historically pick ONE layout—Star Schema, Normalized Snowflake, or One-Big-Table (OBT)."),
        ("The Kimball Trade-off: ", "Star schemas are intuitive but suffer on multi-table joins and lack instant rollups."),
        ("The OBT Trade-off: ", "One-Big-Table avoids joins but wastes massive I/O sequentially scanning wide columns for point queries."),
        ("No Single Winner: ", "No single physical schema is optimal for all query types (point lookups, wide aggregations, KPI rollups).")
    ]
    for b_title, b_desc in points1:
        p = tf1.add_paragraph()
        run1 = p.add_run()
        run1.text = "• " + b_title
        run1.font.bold = True
        run1.font.size = Pt(13)
        run1.font.color.rgb = COLOR_DARK
        run2 = p.add_run()
        run2.text = b_desc
        run2.font.size = Pt(13)
        run2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(10)

    # Right Card: The Core Research Question
    c2 = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    set_shape_flat(c2, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf2 = c2.text_frame
    tf2.word_wrap = True

    p = tf2.paragraphs[0]
    p.text = "Our Core Research Question"
    p.font.size = Pt(18)
    p.font.bold = True
    p.font.color.rgb = COLOR_SECONDARY
    p.space_after = Pt(14)

    p_q = tf2.add_paragraph()
    p_q.text = "“Can pre-execution query structure and query-plan characteristics be used to dynamically route queries across multiple physically specialized schemas with lower latency than any fixed strategy?”"
    p_q.font.size = Pt(15)
    p_q.font.italic = True
    p_q.font.color.rgb = COLOR_PRIMARY
    p_q.space_after = Pt(16)

    points2 = [
        ("Multi-Representation: ", "Materialize multiple specialized layouts simultaneously in DuckDB."),
        ("Leakage-Safe ML: ", "Extract pre-execution AST & query-plan features without executing the query."),
        ("Dynamic Dispatch: ", "Route each query to its optimal physical layout in sub-millisecond time.")
    ]
    for b_title, b_desc in points2:
        p = tf2.add_paragraph()
        run1 = p.add_run()
        run1.text = "✔ " + b_title
        run1.font.bold = True
        run1.font.size = Pt(13)
        run1.font.color.rgb = COLOR_DARK
        run2 = p.add_run()
        run2.text = b_desc
        run2.font.size = Pt(13)
        run2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 3: Evolution & The Honest Negative Finding (V1 - V8)
    # =========================================================================
    slide3 = prs.slides.add_slide(blank_layout)
    add_header(slide3, "Research Evolution: The Honest Negative Finding in V1–V8", "Background & Audit")

    box_top = slide3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.733), Inches(1.8))
    set_shape_flat(box_top, RGBColor(254, 242, 242), RGBColor(254, 202, 202))
    tf_top = box_top.text_frame
    tf_top.word_wrap = True

    p = tf_top.paragraphs[0]
    p.text = "⚠ The V7 & V8 Scientific Finding: Why Pure Relational Schema Selection Stalled"
    p.font.size = Pt(15)
    p.font.bold = True
    p.font.color.rgb = RGBColor(185, 28, 28)
    p.space_after = Pt(6)

    p_desc = tf_top.add_paragraph()
    p_desc.text = "In V1–V8, the system attempted to route queries between Star, Snowflake, and Fact Constellation on DuckDB. Exhaustive benchmarking across 600 queries and 10M rows proved: the adaptive controller NEVER statistically outperformed a fixed Star schema (-0.34% gain, CI crossing zero). The Oracle gap was tiny (2.4%–5.3%) and indistinguishable from measurement noise."
    p_desc.font.size = Pt(12)
    p_desc.font.color.rgb = COLOR_DARK

    # 3 Root Cause Cards
    causes = [
        ("1. Vectorized Columnar Engine", "DuckDB reads only referenced columns automatically. Snowflake's normalization gives zero projection advantage because columnar pruning already does this natively."),
        ("2. In-Memory Dimension Joins", "Dimension tables (1K customers, 60 products) remain cache-resident. Hash joins execute in microseconds, making Snowflake's extra joins pure overhead."),
        ("3. Identical Execution Plans", "Without physical indexing or partitioning, DuckDB produced identical sequential scan + hash join physical plans for Star and Fact Constellation.")
    ]
    for idx, (c_title, c_text) in enumerate(causes):
        cx = Inches(0.8 + idx * 4.0)
        c_box = slide3.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(3.6), Inches(3.7), Inches(3.2))
        set_shape_flat(c_box, COLOR_CARD_BG, COLOR_CARD_BORDER)
        tf_c = c_box.text_frame
        tf_c.word_wrap = True

        p = tf_c.paragraphs[0]
        p.text = c_title
        p.font.size = Pt(14)
        p.font.bold = True
        p.font.color.rgb = COLOR_PRIMARY
        p.space_after = Pt(10)

        p2 = tf_c.add_paragraph()
        p2.text = c_text
        p2.font.size = Pt(12)
        p2.font.color.rgb = COLOR_MUTED

    # =========================================================================
    # SLIDE 4: The V9 Breakthrough (Multi-Representation Architecture)
    # =========================================================================
    slide4 = prs.slides.add_slide(blank_layout)
    add_header(slide4, "The V9 Breakthrough: Multi-Representation Storage Specialization", "Methodology")

    layouts = [
        ("One-Big-Table (OBT)", "Zero-Join Flat Scan", "Pre-joined wide columnar table (obt_sales). Eliminates join hash tables completely. Perfect for wide scans & complex filtering.", "2x – 5x faster vs Joins", "#3B82F6"),
        ("Clustered Star (ART)", "Secondary Index Seeks", "Fact table sorted by customer & date with Adaptive Radix Tree (ART) secondary indexes. Bypasses 99%+ of table scanning.", "10x – 50x for Point Lookups", "#10B981"),
        ("Partitioned Snowflake", "Zonemap Block Skipping", "Normalized dimensions with fact clustered by temporal & spatial keys. DuckDB skips entire blocks of non-matching partitions.", "3x – 10x for Regional Slices", "#F59E0B"),
        ("Aggregate Projections", "Materialized Rollup Cubes", "Pre-aggregated conformed rollup cubes answering summary KPI queries in < 1 ms without touching raw fact records.", "10x – 100x for Rollups", "#8B5CF6")
    ]

    for idx, (title, sub, desc, benefit, col_hex) in enumerate(layouts):
        cx = Inches(0.8 + idx * 3.0)
        box = slide4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, Inches(1.6), Inches(2.8), Inches(5.2))
        set_shape_flat(box, COLOR_CARD_BG, COLOR_CARD_BORDER)
        tf = box.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        p.text = f"Layout {idx+1}"
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = COLOR_SECONDARY
        p.space_after = Pt(4)

        p_t = tf.add_paragraph()
        p_t.text = title
        p_t.font.size = Pt(15)
        p_t.font.bold = True
        p_t.font.color.rgb = COLOR_PRIMARY
        p_t.space_after = Pt(2)

        p_s = tf.add_paragraph()
        p_s.text = sub
        p_s.font.size = Pt(11)
        p_s.font.italic = True
        p_s.font.color.rgb = COLOR_MUTED
        p_s.space_after = Pt(12)

        p_d = tf.add_paragraph()
        p_d.text = desc
        p_d.font.size = Pt(12)
        p_d.font.color.rgb = COLOR_DARK
        p_d.space_after = Pt(14)

        p_b = tf.add_paragraph()
        p_b.text = "⚡ " + benefit
        p_b.font.size = Pt(12)
        p_b.font.bold = True
        p_b.font.color.rgb = COLOR_ACCENT

    # =========================================================================
    # SLIDE 5: End-to-End System Pipeline
    # =========================================================================
    slide5 = prs.slides.add_slide(blank_layout)
    add_header(slide5, "System Architecture: End-to-End Autonomous Pipeline", "System Design")

    steps = [
        ("1. Data Generation", "Deterministic synthetic generator creating sales, customer, product, and dates up to 10M rows."),
        ("2. Multi-Layout Materialization", "Builds 4 distinct DuckDB physical databases (OBT, Star-ART, Part-Snow, Agg-Projections)."),
        ("3. Query AST & Plan Analysis", "Extracts 51 syntactic AST features and DuckDB EXPLAIN plan estimates with zero leakage."),
        ("4. Learned Cost Router", "Trained plan-cost regressor predicts execution latency for each layout and picks the argmin in 0.5 ms."),
        ("5. Dynamic Query Execution", "Adapts SQL to target layout, executes via DuckDB vectorized engine, and returns telemetry.")
    ]

    for idx, (st_title, st_desc) in enumerate(steps):
        sy = Inches(1.5 + idx * 1.1)
        step_box = slide5.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), sy, Inches(11.733), Inches(0.95))
        set_shape_flat(step_box, COLOR_CARD_BG, COLOR_CARD_BORDER)
        tf = step_box.text_frame
        tf.word_wrap = True

        p = tf.paragraphs[0]
        r1 = p.add_run()
        r1.text = st_title + ":  "
        r1.font.bold = True
        r1.font.size = Pt(14)
        r1.font.color.rgb = COLOR_PRIMARY

        r2 = p.add_run()
        r2.text = st_desc
        r2.font.size = Pt(13)
        r2.font.color.rgb = COLOR_MUTED

    # =========================================================================
    # SLIDE 6: The Machine Learning Router
    # =========================================================================
    slide6 = prs.slides.add_slide(blank_layout)
    add_header(slide6, "The Machine Learning Router: Sub-Millisecond Pre-Execution Dispatch", "ML Model")

    # Left: Feature Space
    col1 = slide6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    set_shape_flat(col1, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf1 = col1.text_frame
    tf1.word_wrap = True

    p = tf1.paragraphs[0]
    p.text = "51 Pre-Execution Features"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(12)

    f_points = [
        ("Syntactic AST Features: ", "Number of joins, aggregation functions (SUM/AVG/COUNT), WHERE/AND/OR predicates, GROUP BY column count, LIMIT value, projected column count."),
        ("Entity Filter Flags: ", "Detection of point filters (customer_id = 42), partition filters (year/month/region), and summary rollup compatibility."),
        ("Physical Plan Estimates: ", "Optimizer estimated output cardinality (log1p), scan operator counts, index scan flags, physical join counts, and plan tree depth."),
        ("Zero Target Leakage: ", "Strictly zero runtime execution timing is available to the model during routing.")
    ]
    for b_title, b_desc in f_points:
        p = tf1.add_paragraph()
        r1 = p.add_run()
        r1.text = "• " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(8)

    # Right: Model Formulation
    col2 = slide6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    set_shape_flat(col2, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf2 = col2.text_frame
    tf2.word_wrap = True

    p = tf2.paragraphs[0]
    p.text = "Model Formulation & Training"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_SECONDARY
    p.space_after = Pt(12)

    m_points = [
        ("Multi-Target Plan Cost Regressors: ", "Trained ensemble models predict log execution latency for each layout simultaneously: log(1 + T_obt), log(1 + T_star), etc."),
        ("Cost-Sensitive Routing: ", "Dispatches query to layout with minimal estimated latency: chosen = argmin_L (T_pred_L)."),
        ("Leave-One-Workload-Out (LOWO) CV: ", "Evaluates extreme zero-shot generalization across held-out query families."),
        ("Stratified 5-Fold CV: ", "Evaluates realistic enterprise query traces, achieving 80% Oracle match rate."),
        ("Sub-Millisecond Overhead: ", "Model inference takes only 0.53 ms per query, making routing overhead negligible.")
    ]
    for b_title, b_desc in m_points:
        p = tf2.add_paragraph()
        r1 = p.add_run()
        r1.text = "✔ " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 7: Empirical Benchmark Results (100K & 1M Rows)
    # =========================================================================
    slide7 = prs.slides.add_slide(blank_layout)
    add_header(slide7, "Empirical Results: Statistically Significant Speedup Verified", "Benchmark Evaluation")

    # Table of Results
    rows, cols = 7, 4
    left, top, width, height = Inches(0.8), Inches(1.5), Inches(11.733), Inches(4.2)
    table_shape = slide7.shapes.add_table(rows, cols, left, top, width, height)
    tbl = table_shape.table
    tbl.columns[0].width = Inches(3.6)
    tbl.columns[1].width = Inches(2.6)
    tbl.columns[2].width = Inches(2.6)
    tbl.columns[3].width = Inches(2.933)

    data = [
        ["Benchmark Metric", "100K Rows (100,000)", "1M Rows (1,000,000)", "Conference Significance"],
        ["Theoretical Oracle Headroom", "22.04% reduction", "23.00% reduction", "Massive headroom opened"],
        ["Best Fixed Single Layout Baseline", "agg_projections (4.20 ms)", "star_indexed (13.56 ms)", "Single layout suffers on other queries"],
        ["Adaptive Learned Router Latency", "3.41 ms", "10.75 ms", "Consistently tracks Oracle"],
        ["Latency Reduction vs Best Fixed", "+18.81% (1.23x speedup)", "+20.70% (1.26x speedup)", "Statistically proven"],
        ["95% Bootstrap Confidence Interval", "[+0.626, +0.965] ms", "[+1.868, +3.874] ms", "Zero NOT in CI (p < 0.001)"],
        ["Oracle Match Rate", "78.33%", "80.00%", "Reliable optimal selection"]
    ]

    for r_idx, row in enumerate(data):
        for c_idx, val in enumerate(row):
            cell = tbl.cell(r_idx, c_idx)
            cell.text = val
            p = cell.text_frame.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER if c_idx > 0 else PP_ALIGN.LEFT
            if r_idx == 0:
                p.font.bold = True
                p.font.size = Pt(13)
                p.font.color.rgb = RGBColor(255, 255, 255)
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLOR_PRIMARY
            else:
                p.font.size = Pt(12)
                if r_idx in [4, 5]:
                    p.font.bold = True
                    p.font.color.rgb = COLOR_SUCCESS if c_idx in [1, 2] else COLOR_DARK
                else:
                    p.font.color.rgb = COLOR_DARK
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(248, 250, 252) if r_idx % 2 == 1 else RGBColor(255, 255, 255)

    # Note at bottom
    nb = slide7.shapes.add_textbox(Inches(0.8), Inches(6.0), Inches(11.733), Inches(0.8))
    tf_nb = nb.text_frame
    p_nb = tf_nb.paragraphs[0]
    p_nb.text = "Key Scientific Milestone: In V7 and V8, the adaptive model was -0.34% slower with CIs crossing zero. In V9, AMR-DW delivers +20.70% faster execution with strictly positive confidence bounds [+1.868, +3.874] ms."
    p_nb.font.size = Pt(12)
    p_nb.font.bold = True
    p_nb.font.color.rgb = COLOR_SECONDARY

    # =========================================================================
    # SLIDE 8: Per-Workload Performance Chart
    # =========================================================================
    slide8 = prs.slides.add_slide(blank_layout)
    add_header(slide8, "Per-Workload Class Latency Breakdown", "Empirical Telemetry")

    fig1_path = os.path.join(FIG_DIR, "fig1_latency_by_workload_1m.png")
    if os.path.exists(fig1_path):
        slide8.shapes.add_picture(fig1_path, Inches(0.8), Inches(1.5), width=Inches(7.2))

    # Right side analysis card
    right_card = slide8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3), Inches(1.5), Inches(4.2), Inches(5.3))
    set_shape_flat(right_card, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_r = right_card.text_frame
    tf_r.word_wrap = True

    p = tf_r.paragraphs[0]
    p.text = "Workload Highlights (1M Rows)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(12)

    highlights = [
        ("Summary Rollup: ", "3.90x faster than best fixed baseline (5.11 ms vs 19.96 ms). 100% Oracle match rate!"),
        ("Point Lookups: ", "Star-ART is 1.88x faster than OBT sequential scans (1.61 ms vs 3.02 ms). 85% match rate."),
        ("Wide Multi-Dim: ", "OBT zero-join scan is 1.54x faster than multi-join star schemas (3.50 ms vs 5.40 ms). 92.5% match rate."),
        ("Adaptive Router: ", "Successfully identifies the winning layout across every category, closely tracking the theoretical Oracle.")
    ]
    for h_title, h_desc in highlights:
        p = tf_r.add_paragraph()
        r1 = p.add_run()
        r1.text = "• " + h_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = h_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 9: Cumulative Runtime vs Industry Technologies
    # =========================================================================
    slide9 = prs.slides.add_slide(blank_layout)
    add_header(slide9, "Cumulative Workload Latency vs Industry Baselines", "End-to-End Speedup")

    fig2_path = os.path.join(FIG_DIR, "fig2_cumulative_latency_1m.png")
    if os.path.exists(fig2_path):
        slide9.shapes.add_picture(fig2_path, Inches(0.8), Inches(1.5), width=Inches(7.2))

    # Right side text
    c_right = slide9.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3), Inches(1.5), Inches(4.2), Inches(5.3))
    set_shape_flat(c_right, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_c = c_right.text_frame
    tf_c.word_wrap = True

    p = tf_c.paragraphs[0]
    p.text = "End-to-End Speedup Comparison"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(14)

    bars_info = [
        ("vs. Fixed OBT: ", "2.05x faster overall! (10.75 ms vs 22.04 ms). Eliminates the sequential scan penalty of flat wide tables."),
        ("vs. Fixed Snowflake: ", "1.57x faster overall! (10.75 ms vs 16.90 ms). Eliminates normalized join depth overhead."),
        ("vs. Fixed Star: ", "1.26x faster overall (+20.7% latency reduction). Captures pre-aggregated rollup opportunities."),
        ("Gap to Oracle: ", "The Adaptive Router achieves 10.75 ms vs the theoretical Oracle's 10.44 ms—capturing 80% of total possible headroom.")
    ]
    for b_title, b_desc in bars_info:
        p = tf_c.add_paragraph()
        r1 = p.add_run()
        r1.text = "✔ " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 10: Oracle Win Share Distribution
    # =========================================================================
    slide10 = prs.slides.add_slide(blank_layout)
    add_header(slide10, "Empirical Oracle Win Distribution by Layout", "Multi-Representation Proof")

    fig3_path = os.path.join(FIG_DIR, "fig3_oracle_win_distribution_1m.png")
    if os.path.exists(fig3_path):
        slide10.shapes.add_picture(fig3_path, Inches(1.0), Inches(1.5), width=Inches(5.5))

    c_right2 = slide10.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(7.0), Inches(1.5), Inches(5.5), Inches(5.3))
    set_shape_flat(c_right2, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_w = c_right2.text_frame
    tf_w.word_wrap = True

    p = tf_w.paragraphs[0]
    p.text = "Proof of Multi-Representation Need"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(14)

    wins_info = [
        ("One-Big-Table (42.9% Wins): ", "Dominates wide scans, cross-attribute filters, and mixed queries where zero-join vectorized scans beat all joins."),
        ("Clustered Star-ART (35.8% Wins): ", "Dominates point customer lookups, product searches, and conformed multi-fact returns joins."),
        ("Materialized Projections (15.8% Wins): ", "Dominates high-level temporal/regional/category rollups, answering queries in < 1 ms."),
        ("Partitioned Snowflake (5.4% Wins): ", "Wins on time-windowed regional queries leveraging zonemap block skipping."),
        ("Key Takeaway: ", "In V7/V8, Star won 90%+ of queries because layouts were physically identical. In V9, physical specialization creates true balanced competition!")
    ]
    for b_title, b_desc in wins_info:
        p = tf_w.add_paragraph()
        r1 = p.add_run()
        r1.text = "• " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 11: Feature Importance Analysis
    # =========================================================================
    slide11 = prs.slides.add_slide(blank_layout)
    add_header(slide11, "What Drives the ML Routing Decision?", "Interpretability & Plan Features")

    fig4_path = os.path.join(FIG_DIR, "fig4_top_feature_importance_1m.png")
    if os.path.exists(fig4_path):
        slide11.shapes.add_picture(fig4_path, Inches(0.8), Inches(1.5), width=Inches(7.2))

    c_feat = slide11.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.3), Inches(1.5), Inches(4.2), Inches(5.3))
    set_shape_flat(c_feat, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_f = c_feat.text_frame
    tf_f.word_wrap = True

    p = tf_f.paragraphs[0]
    p.text = "Top Decisive Features"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(14)

    feats_info = [
        ("Plan Tree Depth: ", "Measures structural complexity of the physical operator graph across candidate layouts."),
        ("Estimated Output Cardinality: ", "DuckDB optimizer's estimated output row count (log1p). Drastically separates 36-row rollups from 1M-row scans."),
        ("Scan Operator Count: ", "Reflects whether a query requires scanning 1 wide table vs. 4 separate dimension tables."),
        ("Partition & Point Filters: ", "Direct syntactic AST indicators of whether secondary ART index seeks or zonemap pruning will trigger.")
    ]
    for b_title, b_desc in feats_info:
        p = tf_f.add_paragraph()
        r1 = p.add_run()
        r1.text = "✔ " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 12: Interactive Streamlit Web UI & CLI
    # =========================================================================
    slide12 = prs.slides.add_slide(blank_layout)
    add_header(slide12, "Interactive Exploration: Streamlit Dashboard & CLI", "Software Deliverables")

    s_card1 = slide12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    set_shape_flat(s_card1, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_s1 = s_card1.text_frame
    tf_s1.word_wrap = True

    p = tf_s1.paragraphs[0]
    p.text = "🌐 Streamlit Web Application (app.py)"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(12)

    ui_points = [
        ("Live Query Console: ", "Choose preset analytical templates or type any custom SQL query directly."),
        ("Real-Time Telemetry: ", "Displays chosen layout badge, decision latency (0.5 ms), actual runtime, and speedup vs Star."),
        ("Side-by-Side Cost Chart: ", "Visualizes predicted latency across all 4 candidate layouts."),
        ("Benchmark & Scalability Tab: ", "Toggle between 100K and 1M rows with interactive win-distribution charts."),
        ("One-Command Launch: ", "streamlit run app.py (accessible via browser at localhost:8501).")
    ]
    for b_title, b_desc in ui_points:
        p = tf_s1.add_paragraph()
        r1 = p.add_run()
        r1.text = "• " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(8)

    s_card2 = slide12.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    set_shape_flat(s_card2, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_s2 = s_card2.text_frame
    tf_s2.word_wrap = True

    p = tf_s2.paragraphs[0]
    p.text = "💻 Developer Tooling & Verification"
    p.font.size = Pt(16)
    p.font.bold = True
    p.font.color.rgb = COLOR_SECONDARY
    p.space_after = Pt(12)

    cli_points = [
        ("Interactive CLI Router: ", "python src/optimizer/adaptive_router_v9.py --rows 1000000 --query \"SELECT ...\""),
        ("Automated Unit Test Suite: ", "python -m unittest discover -s tests -p \"test_*.py\" verifying 100% schema consistency & feature parity."),
        ("Reproducible GitHub Repo: ", "Completely committed and pushed to https://github.com/Ashwin-arch/multi-schema-new-aakp."),
        ("Zero-Config Cross-Platform: ", "Standard requirements.txt with simple 3-step setup on Linux, macOS, and Windows WSL2.")
    ]
    for b_title, b_desc in cli_points:
        p = tf_s2.add_paragraph()
        r1 = p.add_run()
        r1.text = "✔ " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 13: Honest Discussion: Strengths vs Trade-Offs
    # =========================================================================
    slide13 = prs.slides.add_slide(blank_layout)
    add_header(slide13, "Honest Discussion: Strengths vs Trade-Offs", "Scientific Transparency")

    card_pro = slide13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    set_shape_flat(card_pro, RGBColor(240, 253, 244), COLOR_SUCCESS)
    tf_p = card_pro.text_frame
    tf_p.word_wrap = True

    p = tf_p.paragraphs[0]
    p.text = "✅ Core Strengths & Advantages"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_SUCCESS
    p.space_after = Pt(14)

    pros = [
        ("Proven Query Speedup: ", "1.26x faster than best fixed layout, 2.05x faster than OBT, up to 3.9x faster on rollups."),
        ("High Oracle Capture: ", "Captures 80% of theoretical Oracle performance with 80% match accuracy."),
        ("Negligible Overhead: ", "Routing takes only 0.53 ms—orders of magnitude faster than analytical query execution."),
        ("Zero Runtime Leakage: ", "Features are strictly pre-execution (AST syntax + EXPLAIN operator estimates)."),
        ("Statistical Significance: ", "95% Bootstrap CI [+1.87, +3.87] ms decisively rejects the null hypothesis.")
    ]
    for b_title, b_desc in pros:
        p = tf_p.add_paragraph()
        r1 = p.add_run()
        r1.text = "✔ " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(8)

    card_con = slide13.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    set_shape_flat(card_con, RGBColor(254, 242, 242), COLOR_ACCENT)
    tf_con = card_con.text_frame
    tf_con.word_wrap = True

    p = tf_con.paragraphs[0]
    p.text = "⚠ System Trade-offs & Limitations"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_ACCENT
    p.space_after = Pt(14)

    cons = [
        ("Storage Amplification: ", "Maintaining 4 physical layouts requires ~2.5x to 3x more disk storage than a single Star schema."),
        ("Write / ETL Synchronization: ", "Best suited for read-heavy OLAP (batch loads). In high-frequency real-time update workloads, multi-table sync costs increase."),
        ("Scale-Out Boundary: ", "Currently evaluated as a single-node in-process vectorized engine (DuckDB up to 10M rows); distributed multi-node scaling remains future work."),
        ("Workload Drift: ", "Requires retraining if query distribution shifts drastically into unobserved analytical domains.")
    ]
    for b_title, b_desc in cons:
        p = tf_con.add_paragraph()
        r1 = p.add_run()
        r1.text = "• " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(8)

    # =========================================================================
    # SLIDE 14: Conclusion & Future Scope
    # =========================================================================
    slide14 = prs.slides.add_slide(blank_layout)
    add_header(slide14, "Conclusion & Future Roadmap", "Summary & Next Steps")

    c_sum = slide14.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), Inches(1.6), Inches(5.6), Inches(5.2))
    set_shape_flat(c_sum, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_s = c_sum.text_frame
    tf_s.word_wrap = True

    p = tf_s.paragraphs[0]
    p.text = "Key Contributions"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(14)

    contribs = [
        ("Overcame Classical Schema Bottleneck: ", "Demonstrated why pure relational normalization fails on modern columnar engines and pivoted to physical layout specialization."),
        ("AMR-DW Framework (V9): ", "First autonomous system combining OBT, Clustered Star-ART, Partitioned Snowflake, and Materialized Projections."),
        ("Empirical Validation: ", "Delivered +20.70% latency reduction over best fixed schema and 2.05x speedup over OBT with statistical significance."),
        ("Turnkey Reproducibility: ", "Complete open-source codebase, automated tests, and interactive Streamlit UI.")
    ]
    for b_title, b_desc in contribs:
        p = tf_s.add_paragraph()
        r1 = p.add_run()
        r1.text = "✔ " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(10)

    c_fut = slide14.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.8), Inches(1.6), Inches(5.7), Inches(5.2))
    set_shape_flat(c_fut, COLOR_CARD_BG, COLOR_CARD_BORDER)
    tf_fut = c_fut.text_frame
    tf_fut.word_wrap = True

    p = tf_fut.paragraphs[0]
    p.text = "Future Research Directions"
    p.font.size = Pt(17)
    p.font.bold = True
    p.font.color.rgb = COLOR_SECONDARY
    p.space_after = Pt(14)

    futures = [
        ("Autonomous Materialized Views: ", "Dynamically synthesize and drop rollup projections on-the-fly based on live query frequency."),
        ("Distributed Engine Routing (Polystore): ", "Expand routing across heterogeneous engines (e.g., DuckDB for analytical vector scans, SQLite for point lookups)."),
        ("Incremental Streaming Maintenance: ", "Implement delta-based change data capture (CDC) to synchronize physical layouts with minimal write cost."),
        ("Deep Tree-Convolutional Models: ", "Integrate Tree-CNN plan encoders (Bao-style) for zero-shot generalized plan routing.")
    ]
    for b_title, b_desc in futures:
        p = tf_fut.add_paragraph()
        r1 = p.add_run()
        r1.text = "🔮 " + b_title
        r1.font.bold = True
        r1.font.size = Pt(12)
        r1.font.color.rgb = COLOR_DARK
        r2 = p.add_run()
        r2.text = b_desc
        r2.font.size = Pt(12)
        r2.font.color.rgb = COLOR_MUTED
        p.space_after = Pt(10)

    # =========================================================================
    # SLIDE 15: Thank You & Q&A
    # =========================================================================
    slide15 = prs.slides.add_slide(blank_layout)

    bg15 = slide15.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    set_shape_flat(bg15, COLOR_LIGHT_BG)

    top_stripe15 = slide15.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.2))
    set_shape_flat(top_stripe15, COLOR_SECONDARY)

    card15 = slide15.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.5), Inches(1.2), Inches(10.333), Inches(5.2))
    set_shape_flat(card15, COLOR_CARD_BG, COLOR_CARD_BORDER)

    tf15 = card15.text_frame
    tf15.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf15.word_wrap = True

    p = tf15.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.text = "Thank You!"
    p.font.size = Pt(40)
    p.font.bold = True
    p.font.color.rgb = COLOR_PRIMARY
    p.space_after = Pt(12)

    p_sub = tf15.add_paragraph()
    p_sub.alignment = PP_ALIGN.CENTER
    p_sub.text = "Adaptive Multi-Schema Data Warehouse (AMR-DW / V9)"
    p_sub.font.size = Pt(20)
    p_sub.font.bold = True
    p_sub.font.color.rgb = COLOR_SECONDARY
    p_sub.space_after = Pt(16)

    p_team = tf15.add_paragraph()
    p_team.alignment = PP_ALIGN.CENTER
    p_team.text = "Ashwin Kumar G rao   |   Aritra das   |   Krishna Teja   |   Priyanshu Goyal"
    p_team.font.size = Pt(15)
    p_team.font.bold = True
    p_team.font.color.rgb = COLOR_DARK
    p_team.space_after = Pt(16)

    p_repo = tf15.add_paragraph()
    p_repo.alignment = PP_ALIGN.CENTER
    p_repo.text = "🔗 GitHub Repository: https://github.com/Ashwin-arch/multi-schema-new-aakp\n🚀 Live Streamlit Web App: http://localhost:8501"
    p_repo.font.size = Pt(13)
    p_repo.font.color.rgb = COLOR_MUTED
    p_repo.space_after = Pt(16)

    p_qa = tf15.add_paragraph()
    p_qa.alignment = PP_ALIGN.CENTER
    p_qa.text = "Questions & Discussion"
    p_qa.font.size = Pt(22)
    p_qa.font.bold = True
    p_qa.font.color.rgb = COLOR_ACCENT

    prs.save(OUTPUT_PPTX)
    print(f"Presentation saved successfully to: {OUTPUT_PPTX}")


if __name__ == "__main__":
    create_presentation()
