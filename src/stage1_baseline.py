"""
Stage 1 — Seasonality-Aware Statistical Baseline
F1 Replenishment Intelligence | Inibsa Smart Demand Signals
"""
import warnings
import os
import sys
import random
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# SEED & PATHS
# ─────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

INPUT_DIR  = Path("./output/stage0")
OUTPUT_DIR = Path("./output/stage1")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

STD_EPSILON   = 3.0   # minimum std in days to prevent division blow-up
MIN_PURCHASES_LEVEL_A = 3
MIN_PURCHASES_LEVEL_B = 4

print("=" * 70)
print("STAGE 1 — SEASONALITY-AWARE STATISTICAL BASELINE")
print("=" * 70)
print()

# ─────────────────────────────────────────────────────────────
# LOAD STAGE 0 OUTPUTS
# ─────────────────────────────────────────────────────────────
print("Loading Stage 0 outputs …")
df_weekly    = pd.read_parquet(INPUT_DIR / "df_weekly.parquet")
df_potential = pd.read_parquet(INPUT_DIR / "df_potential.parquet")
df_master    = pd.read_parquet(INPUT_DIR / "df_master.parquet")
print(f"  df_weekly:    {len(df_weekly):,} rows")
print(f"  df_potential: {len(df_potential):,} rows")
print()

# ─────────────────────────────────────────────────────────────
# 1.1 FILTER TO COMMODITIES
# ─────────────────────────────────────────────────────────────
print("Filtering to Commodities (Familia C1, C2) …")
COMMODITY_FAMILIES = ["Familia C1", "Familia C2"]
df_comm = df_weekly[df_weekly["product_family"].isin(COMMODITY_FAMILIES)].copy()
print(f"  Commodity panel rows: {len(df_comm):,}")
print(f"  Unique (client × family): {df_comm.groupby(['client_id','product_family']).ngroups:,}")
print()

# ─────────────────────────────────────────────────────────────
# SCORING DATE
# ─────────────────────────────────────────────────────────────
SCORING_DATE = df_comm["week_start"].max() + pd.Timedelta(weeks=1)
print(f"  Scoring date: {SCORING_DATE.date()}")
print()

# ─────────────────────────────────────────────────────────────
# 1.2 PURCHASE EVENT SERIES & INTERVALS
# ─────────────────────────────────────────────────────────────
print("Building purchase event series and intervals …")

def quarter(dt):
    m = dt.month
    return "Q1" if m <= 3 else "Q2" if m <= 6 else "Q3" if m <= 9 else "Q4"

# Extract purchase events (had_purchase == 1)
df_events = df_comm[df_comm["had_purchase"] == 1][
    ["client_id", "product_family", "week_start"]
].copy().sort_values(["client_id", "product_family", "week_start"])

# Compute consecutive intervals per (client, family)
df_events["prev_week"] = df_events.groupby(
    ["client_id", "product_family"]
)["week_start"].shift(1)

df_events["interval_days"] = (
    df_events["week_start"] - df_events["prev_week"]
).dt.days

df_events["quarter"] = df_events["week_start"].apply(quarter)

# Drop first purchase per pair (no interval)
df_intervals = df_events.dropna(subset=["interval_days"]).copy()
print(f"  Purchase intervals computed: {len(df_intervals):,}")
print()

# ─────────────────────────────────────────────────────────────
# 1.3 HIERARCHICAL INTERVAL STATISTICS
# ─────────────────────────────────────────────────────────────
print("Computing hierarchical interval statistics …")

# Level A: client × family × quarter
level_a = (
    df_intervals
    .groupby(["client_id", "product_family", "quarter"], observed=True)["interval_days"]
    .agg(n_purchases_cfq="count", mean_interval_cfq="mean",
         std_interval_cfq="std",  median_interval_cfq="median")
    .reset_index()
)
level_a["std_interval_cfq"] = level_a["std_interval_cfq"].fillna(0).clip(lower=STD_EPSILON)
level_a_valid = level_a[level_a["n_purchases_cfq"] >= MIN_PURCHASES_LEVEL_A]
print(f"  Level A rows (n≥{MIN_PURCHASES_LEVEL_A}): {len(level_a_valid):,}")

# Level B: client × family (all quarters)
level_b = (
    df_intervals
    .groupby(["client_id", "product_family"], observed=True)["interval_days"]
    .agg(n_purchases_cf="count", mean_interval_cf="mean",
         std_interval_cf="std",  median_interval_cf="median")
    .reset_index()
)
level_b["std_interval_cf"] = level_b["std_interval_cf"].fillna(0).clip(lower=STD_EPSILON)
level_b_valid = level_b[level_b["n_purchases_cf"] >= MIN_PURCHASES_LEVEL_B]
print(f"  Level B rows (n≥{MIN_PURCHASES_LEVEL_B}): {len(level_b_valid):,}")

# Level C: family × quarter (global fallback)
level_c = (
    df_intervals
    .groupby(["product_family", "quarter"], observed=True)["interval_days"]
    .agg(mean_interval_fq="mean", std_interval_fq="std")
    .reset_index()
)
level_c["std_interval_fq"] = level_c["std_interval_fq"].fillna(0).clip(lower=STD_EPSILON)
print(f"  Level C rows: {len(level_c):,}")
print()

# ─────────────────────────────────────────────────────────────
# 1.4 SCORING
# ─────────────────────────────────────────────────────────────
print("Computing replenishment scores …")

# Last purchase date per (client, family)
last_purchase = (
    df_comm[df_comm["had_purchase"] == 1]
    .groupby(["client_id", "product_family"], observed=True)["week_start"]
    .max()
    .reset_index()
    .rename(columns={"week_start": "last_purchase_date"})
)

# All commodity pairs
all_pairs = df_comm[["client_id", "product_family", "product_family_biz"]].drop_duplicates()

scoring = all_pairs.merge(last_purchase, on=["client_id", "product_family"], how="left")
scoring = scoring.dropna(subset=["last_purchase_date"])  # never bought → skip

scoring["days_since_last"] = (SCORING_DATE - scoring["last_purchase_date"]).dt.days
scoring["current_quarter"]  = scoring["last_purchase_date"].apply(quarter)

# Merge province from master
client_meta = (
    df_master[["client_id", "province", "segment_code"]]
    .drop_duplicates(subset=["client_id"])
)
scoring = scoring.merge(client_meta, on="client_id", how="left")

# Attach Level A stats
scoring = scoring.merge(
    level_a_valid[["client_id", "product_family", "quarter",
                   "n_purchases_cfq", "mean_interval_cfq", "std_interval_cfq"]],
    left_on=["client_id", "product_family", "current_quarter"],
    right_on=["client_id", "product_family", "quarter"],
    how="left"
).drop(columns=["quarter"], errors="ignore")

# Attach Level B stats
scoring = scoring.merge(
    level_b_valid[["client_id", "product_family",
                   "n_purchases_cf", "mean_interval_cf", "std_interval_cf"]],
    on=["client_id", "product_family"],
    how="left"
)

# Attach Level C stats
scoring["current_quarter_for_c"] = scoring["current_quarter"]
scoring = scoring.merge(
    level_c[["product_family", "quarter", "mean_interval_fq", "std_interval_fq"]],
    left_on=["product_family", "current_quarter_for_c"],
    right_on=["product_family", "quarter"],
    how="left"
).drop(columns=["quarter", "current_quarter_for_c"], errors="ignore")

# Resolve fallback hierarchy
def resolve_stats(row):
    # Level A
    if pd.notna(row.get("mean_interval_cfq")):
        return (row["mean_interval_cfq"], max(row["std_interval_cfq"], STD_EPSILON),
                row["n_purchases_cfq"], "high")
    # Level B
    if pd.notna(row.get("mean_interval_cf")):
        return (row["mean_interval_cf"], max(row["std_interval_cf"], STD_EPSILON),
                row["n_purchases_cf"], "medium")
    # Level C
    if pd.notna(row.get("mean_interval_fq")):
        return (row["mean_interval_fq"], max(row["std_interval_fq"], STD_EPSILON),
                1, "low")
    # Ultimate fallback: 30 days
    return (30.0, STD_EPSILON, 0, "low")

resolved = scoring.apply(resolve_stats, axis=1, result_type="expand")
resolved.columns = ["expected_interval", "std_used", "n_purchases_used", "confidence_level"]
scoring = pd.concat([scoring, resolved], axis=1)

scoring["delay"] = scoring["days_since_last"] - scoring["expected_interval"]
scoring["seasonal_time_score"] = (
    scoring["delay"].clip(lower=0) / scoring["std_used"]
)
scoring["expected_reorder_date"] = (
    scoring["last_purchase_date"] +
    pd.to_timedelta(scoring["expected_interval"], unit="D")
)

# Count by confidence level
conf_counts = scoring["confidence_level"].value_counts()
print(f"  Confidence level coverage: {conf_counts.to_dict()}")
print()

# ─────────────────────────────────────────────────────────────
# 1.5 VALUE FACTOR
# ─────────────────────────────────────────────────────────────
print("Computing value factor …")

# Historical 12-month value
cutoff_52w = SCORING_DATE - pd.Timedelta(weeks=52)
df_hist = df_comm[df_comm["week_start"] >= cutoff_52w]
hist_value = (
    df_hist.groupby(["client_id", "product_family"], observed=True)["weekly_value"]
    .sum().reset_index().rename(columns={"weekly_value": "historical_value_12m"})
)
scoring = scoring.merge(hist_value, on=["client_id", "product_family"], how="left")
scoring["historical_value_12m"] = scoring["historical_value_12m"].fillna(0)

# Potential lookup: (client_id, product_family_biz) → potential_value
pot_lookup = (
    df_potential
    .groupby(["client_id", "product_family_biz"])["potential_value"]
    .sum().reset_index()
)
scoring = scoring.merge(pot_lookup, on=["client_id", "product_family_biz"], how="left")

n_pot_miss = scoring["potential_value"].isna().sum()
print(f"  Potential lookup misses (fall back to hist_12m): {n_pot_miss:,}")
scoring["potential_value"] = scoring["potential_value"].fillna(scoring["historical_value_12m"])

scoring["raw_value"] = np.maximum(scoring["potential_value"], scoring["historical_value_12m"])

# Log-normalise to [0, 1]
log_raw = np.log1p(scoring["raw_value"].clip(lower=0))
log_min, log_max = log_raw.min(), log_raw.max()
denom = (log_max - log_min) if (log_max - log_min) > 0 else 1.0
scoring["value_factor"] = (log_raw - log_min) / denom

# ─────────────────────────────────────────────────────────────
# 1.6 FINAL SCORE & PRIORITY
# ─────────────────────────────────────────────────────────────
scoring["replenishment_score"] = scoring["seasonal_time_score"] * scoring["value_factor"]

# Split scored vs on-track
mask_overdue = scoring["seasonal_time_score"] > 0
df_overdue   = scoring[mask_overdue].copy()
df_ontrack   = scoring[~mask_overdue].copy()

print(f"  Overdue (score > 0):   {len(df_overdue):,}")
print(f"  On track (score == 0): {len(df_ontrack):,}")

# Percentile bins on overdue population
q5  = df_overdue["replenishment_score"].quantile(0.95)
q80 = df_overdue["replenishment_score"].quantile(0.80)
q50 = df_overdue["replenishment_score"].quantile(0.50)

def assign_priority(score):
    if score >= q5:
        return "P1 Critical"
    elif score >= q80:
        return "P2 High"
    elif score >= q50:
        return "P3 Medium"
    else:
        return "P4 Low"

df_overdue["priority_level"] = df_overdue["replenishment_score"].apply(assign_priority)
df_ontrack["priority_level"] = "On track"

priority_counts = df_overdue["priority_level"].value_counts().sort_index()
print()
print("  Priority distribution (overdue population):")
for lvl, cnt in priority_counts.items():
    print(f"    {lvl}: {cnt:,}")
print()

# ─────────────────────────────────────────────────────────────
# 1.7 REASON TEXT GENERATOR
# ─────────────────────────────────────────────────────────────
def make_reason(row, campaign_weeks):
    # Check if scoring_date is inside a campaign
    scoring_in_campaign = bool(campaign_weeks.get(SCORING_DATE.normalize(), 0))
    campaign_note = " (Note: current date overlaps an active campaign.)" if scoring_in_campaign else ""

    low_note = ""
    if row["confidence_level"] == "low":
        low_note = " Note: limited purchase history — apply judgment."

    return (
        f"Client {row['client_id']} has not ordered {row['product_family_biz']} "
        f"in {row['days_since_last']:.0f} days. "
        f"Their typical {row['current_quarter']} reorder cycle is "
        f"{row['expected_interval']:.0f} days "
        f"(based on {row['n_purchases_used']:.0f} historical reorders, "
        f"confidence={row['confidence_level']}). "
        f"This delay is {row['seasonal_time_score']:.1f} standard deviations "
        f"beyond the expected pattern. "
        f"With {row['raw_value']:.0f} EUR commercial value at stake, "
        f"priority is {row['priority_level']}."
        f"{campaign_note}{low_note}"
    )

# Build campaign_weeks lookup
campaign_weeks = {}
for w in df_comm["week_start"].unique():
    week_end = w + pd.Timedelta(days=6)
    if "campaign_active" in df_comm.columns:
        val = df_comm.loc[df_comm["week_start"] == w, "campaign_active"].max()
        campaign_weeks[w.normalize()] = int(val)

df_overdue["reason"] = df_overdue.apply(
    lambda r: make_reason(r, campaign_weeks), axis=1
)
df_ontrack["reason"] = "Client is within expected reorder window."

# ─────────────────────────────────────────────────────────────
# 1.8 COMBINE & SAVE
# ─────────────────────────────────────────────────────────────
output_cols = [
    "client_id", "product_family", "product_family_biz", "province",
    "current_quarter", "last_purchase_date", "days_since_last",
    "expected_interval", "expected_reorder_date", "delay",
    "seasonal_time_score", "value_factor", "replenishment_score",
    "priority_level", "confidence_level", "n_purchases_used", "reason",
    "raw_value", "historical_value_12m", "potential_value",
]

df_overdue = df_overdue.rename(columns={"days_since_last": "days_since_last_purchase"})
df_ontrack = df_ontrack.rename(columns={"days_since_last": "days_since_last_purchase"})

# Ensure all output cols exist
for col in output_cols:
    if col not in df_overdue.columns:
        df_overdue[col] = np.nan
    if col not in df_ontrack.columns:
        df_ontrack[col] = np.nan

output_cols_fixed = [c.replace("days_since_last", "days_since_last_purchase") if c == "days_since_last" else c for c in output_cols]
output_cols = [c for c in output_cols if c in df_overdue.columns]

f1_alerts = pd.concat([df_overdue, df_ontrack], ignore_index=True)
f1_alerts.to_parquet(OUTPUT_DIR / "f1_baseline_alerts.parquet", index=False)
print(f"  ✓ f1_baseline_alerts.parquet ({len(f1_alerts):,} rows)")

# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS REPORT
# ─────────────────────────────────────────────────────────────
top10 = df_overdue.nlargest(10, "replenishment_score")[
    ["client_id", "product_family_biz", "priority_level",
     "days_since_last_purchase", "expected_interval",
     "seasonal_time_score", "replenishment_score", "confidence_level"]
]

# Score distribution summary
score_desc = df_overdue["replenishment_score"].describe()

p1p2_count = priority_counts.get("P1 Critical", 0) + priority_counts.get("P2 High", 0)

report_lines = [
    "# Stage 1 — Baseline Diagnostics",
    "",
    "## Coverage",
    f"- Total scored pairs:   {len(f1_alerts):,}",
    f"- Overdue (score > 0):  {len(df_overdue):,}",
    f"- On track:             {len(df_ontrack):,}",
    "",
    "## Priority Distribution",
] + [f"- {lvl}: {cnt}" for lvl, cnt in priority_counts.items()] + [
    f"- On track: {len(df_ontrack):,}",
    "",
    "## Confidence Level Coverage",
] + [f"- {lvl}: {cnt}" for lvl, cnt in conf_counts.items()] + [
    "",
    "## Score Distribution (overdue population)",
    f"- count: {score_desc['count']:.0f}",
    f"- mean:  {score_desc['mean']:.3f}",
    f"- std:   {score_desc['std']:.3f}",
    f"- min:   {score_desc['min']:.3f}",
    f"- 25%:   {score_desc['25%']:.3f}",
    f"- 50%:   {score_desc['50%']:.3f}",
    f"- 75%:   {score_desc['75%']:.3f}",
    f"- max:   {score_desc['max']:.3f}",
    "",
    f"## P1+P2 Alert Count: {p1p2_count}",
    "",
    "## Top 10 Alerts",
    "",
    top10.to_string(index=False),
    "",
    "## Notes",
    "- Value factor uses log1p normalization (skewed EUR distribution)",
    "- STD epsilon = 3 days to prevent score explosion for very regular clients",
    "- Priority bins: P1=top 5%, P2=next 15%, P3=next 30%, P4=remaining 50%",
]

(OUTPUT_DIR / "f1_baseline_diagnostics.md").write_text("\n".join(report_lines))
print(f"  ✓ f1_baseline_diagnostics.md")

print()
print("=" * 70)
print("STAGE 1 COMPLETE")
print("=" * 70)
print(f"  Total alerts: {len(f1_alerts):,}")
print(f"  P1+P2 alerts: {p1p2_count:,}")
print(f"  Confidence breakdown: {conf_counts.to_dict()}")
