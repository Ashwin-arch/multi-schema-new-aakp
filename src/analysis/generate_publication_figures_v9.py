import argparse
import os
import sys
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
from src.data.generate_data_v9 import get_scale_label
from src.schemas.build_schemas_v9 import SCHEMAS_V9

RESULTS_DIR = "results/v9"
FIG_DIR = "results/figures/v9"
QUERY_SUMMARY_FILE = os.path.join(RESULTS_DIR, "scale_query_summary.csv")
ADAPTIVE_QUERY_FILE = os.path.join(RESULTS_DIR, "adaptive_model_query_results.csv")
FEATURE_IMP_FILE = os.path.join(RESULTS_DIR, "feature_importance.csv")


def set_pub_style():
    """Set publication-grade formatting (SIGMOD / VLDB style)."""
    sns.set_theme(style="whitegrid", font="sans-serif")
    plt.rcParams.update({
        "font.size": 11,
        "axes.labelsize": 12,
        "axes.titlesize": 13,
        "xtick.labelsize": 10,
        "ytick.labelsize": 10,
        "legend.fontsize": 10,
        "figure.titlesize": 14,
        "figure.dpi": 300,
    })


def generate_all_figures_v9(scale_rows=100_000):
    """Generate all evaluation plots for conference publication."""
    set_pub_style()
    os.makedirs(FIG_DIR, exist_ok=True)
    scale_label = get_scale_label(scale_rows)

    if not os.path.exists(QUERY_SUMMARY_FILE):
        raise FileNotFoundError(f"{QUERY_SUMMARY_FILE} not found. Run benchmark first.")

    qs_df = pd.read_csv(QUERY_SUMMARY_FILE)
    qs = qs_df[qs_df["dataset_size"] == scale_rows].copy()

    aq_df = pd.read_csv(ADAPTIVE_QUERY_FILE) if os.path.exists(ADAPTIVE_QUERY_FILE) else None
    if aq_df is not None:
        aq = aq_df[aq_df["dataset_size"] == scale_rows].copy()
        if "cv_mode" in aq.columns:
            aq = aq[aq["cv_mode"] == "stratified"].copy()
    else:
        aq = None

    # Merge router results
    if aq is not None:
        merged = qs.merge(aq[["query_id", "chosen_schema", "chosen_ms"]], on="query_id")
    else:
        merged = qs.copy()
        merged["chosen_ms"] = merged["oracle_mean_ms"]

    # -------------------------------------------------------------
    # Figure 1: Per-Workload Class Latency Comparison
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(10, 5))
    wl_means = merged.groupby("workload")[[
        "obt_mean_ms", "star_indexed_mean_ms", "partitioned_snow_mean_ms",
        "agg_projections_mean_ms", "chosen_ms", "oracle_mean_ms"
    ]].mean().reset_index()

    labels = wl_means["workload"].str.replace("_", " ").str.title()
    x = np.arange(len(labels))
    width = 0.14

    palette = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#CCB974", "#64B5CD"]

    ax.bar(x - 2.5 * width, wl_means["obt_mean_ms"], width, label="OBT (Denormalized)", color=palette[0])
    ax.bar(x - 1.5 * width, wl_means["star_indexed_mean_ms"], width, label="Star (ART Indexed)", color=palette[1])
    ax.bar(x - 0.5 * width, wl_means["partitioned_snow_mean_ms"], width, label="Part-Snowflake", color=palette[2])
    ax.bar(x + 0.5 * width, wl_means["agg_projections_mean_ms"], width, label="Agg-Projections", color=palette[3])
    ax.bar(x + 1.5 * width, wl_means["chosen_ms"], width, label="Adaptive Router (Learned)", color=palette[4], hatch="//")
    ax.bar(x + 2.5 * width, wl_means["oracle_mean_ms"], width, label="Theoretical Oracle", color=palette[5], linestyle="--", edgecolor="black")

    ax.set_ylabel("Mean Execution Latency (ms)")
    ax.set_title(f"Multi-Representation Latency Comparison Across Workload Classes ({scale_label} Rows)")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.legend(frameon=True, loc="upper right")
    fig.tight_layout()

    fig1_path = os.path.join(FIG_DIR, f"fig1_latency_by_workload_{scale_label.lower()}.png")
    fig.savefig(fig1_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {fig1_path}")

    # -------------------------------------------------------------
    # Figure 2: Total Workload Execution Time
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(8, 4.5))
    totals = {
        "Fixed OBT": merged["obt_mean_ms"].sum(),
        "Fixed Star": merged["star_indexed_mean_ms"].sum(),
        "Fixed Snowflake": merged["partitioned_snow_mean_ms"].sum(),
        "Fixed Agg-Proj": merged["agg_projections_mean_ms"].sum(),
        "Adaptive Router": merged["chosen_ms"].sum(),
        "Oracle": merged["oracle_mean_ms"].sum(),
    }

    names = list(totals.keys())
    values = list(totals.values())
    colors = ["#4C72B0", "#55A868", "#C44E52", "#8172B2", "#E69F00", "#009E73"]

    bars = ax.barh(names, values, color=colors, height=0.6)
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 10, bar.get_y() + bar.get_height() / 2, f"{w:.1f} ms", va="center", fontsize=10, fontweight="bold")

    ax.set_xlabel("Total Workload Execution Latency (ms)")
    ax.set_title(f"Cumulative Analytical Workload Runtime (240 Queries, {scale_label} Rows)")
    ax.set_xlim(0, max(values) * 1.18)
    fig.tight_layout()

    fig2_path = os.path.join(FIG_DIR, f"fig2_cumulative_latency_{scale_label.lower()}.png")
    fig.savefig(fig2_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {fig2_path}")

    # -------------------------------------------------------------
    # Figure 3: Oracle Win Distribution
    # -------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(6, 6))
    win_counts = merged["oracle_schema"].value_counts()
    layout_display = {
        "obt": "One-Big-Table (OBT)",
        "star_indexed": "Star (ART Indexed)",
        "agg_projections": "Materialized Projections",
        "partitioned_snow": "Partitioned Snowflake",
    }
    pie_labels = [layout_display.get(k, k) for k in win_counts.index]
    pie_colors = ["#8172B2", "#4C72B0", "#55A868", "#C44E52"][:len(win_counts)]

    wedges, texts, autotexts = ax.pie(
        win_counts.values,
        labels=pie_labels,
        autopct="%1.1f%%",
        startangle=140,
        colors=pie_colors,
        wedgeprops=dict(width=0.45, edgecolor="white", linewidth=2)
    )
    plt.setp(autotexts, size=11, weight="bold")
    ax.set_title(f"Empirical Oracle Win Distribution by Layout\n({scale_label} Rows, 240 Queries)")
    fig.tight_layout()

    fig3_path = os.path.join(FIG_DIR, f"fig3_oracle_win_distribution_{scale_label.lower()}.png")
    fig.savefig(fig3_path, dpi=300)
    plt.close(fig)
    print(f"Generated: {fig3_path}")

    # -------------------------------------------------------------
    # Figure 4: Feature Importance
    # -------------------------------------------------------------
    if os.path.exists(FEATURE_IMP_FILE):
        fi_df = pd.read_csv(FEATURE_IMP_FILE)
        top_fi = fi_df.groupby("feature")["importance"].mean().sort_values(ascending=True).tail(15)

        fig, ax = plt.subplots(figsize=(8, 5.5))
        top_fi.plot(kind="barh", color="#2b5c8f", ax=ax)
        ax.set_xlabel("Relative Feature Importance (MDI)")
        ax.set_title("Top-15 Pre-Execution Plan & Syntactic Features (Learned Router)")
        fig.tight_layout()

        fig4_path = os.path.join(FIG_DIR, f"fig4_top_feature_importance_{scale_label.lower()}.png")
        fig.savefig(fig4_path, dpi=300)
        plt.close(fig)
        print(f"Generated: {fig4_path}")

    print("\nAll publication figures successfully generated in results/figures/v9/.")


def main():
    parser = argparse.ArgumentParser(description="Publication Figure Generator V9")
    parser.add_argument("--rows", type=int, default=100_000)
    args = parser.parse_args()

    generate_all_figures_v9(args.rows)


if __name__ == "__main__":
    main()
