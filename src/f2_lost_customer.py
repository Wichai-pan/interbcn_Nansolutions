"""
F2 — Lost Customer Risk Detection
Inibsa Smart Demand Signals

Three independent branches:
  A. Productos Técnicos  (T1/T2)        → Silence Score
  B. Commodities (C1/C2) days_since>730 → Direct flag
  C. Commodities (C1/C2) active-degraded → Historical Pattern compare

Outputs:  ./output/f2/f2_lost_customer_alerts.parquet
          ./output/f2/f2_diagnostics.md
"""
import warnings
import random
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

INPUT_STAGE0 = Path("./output/stage0")
INPUT_STAGE1 = Path("./output/stage1")
OUTPUT_DIR   = Path("./output/f2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Branch A Level B fallback thresholds (days)
T1_FALLBACK_THRESHOLD = 210
T2_FALLBACK_THRESHOLD = 251

# ─────────────────────────────────────────────────────────────
print("=" * 70)
print("F2 — LOST CUSTOMER RISK DETECTION")
print("=" * 70)

# ─────────────────────────────────────────────────────────────
# STAGE 0 — DATA PREP
# ─────────────────────────────────────────────────────────────
print("\n[Stage 0] Loading inputs …")
df_master    = pd.read_parquet(INPUT_STAGE0 / "df_master.parquet")
df_potential = pd.read_parquet(INPUT_STAGE0 / "df_potential.parquet")
f1_alerts    = pd.read_parquet(INPUT_STAGE1 / "f1_baseline_alerts.parquet")
print(f"  df_master:    {len(df_master):,}")
print(f"  df_potential: {len(df_potential):,}")
print(f"  f1_alerts:    {len(f1_alerts):,}")

# 0.1 keep positive purchases only
df_master["date"] = pd.to_datetime(df_master["date"])
df_pos = df_master[df_master["units"] > 0].copy()
print(f"  positive-purchase rows (units>0): {len(df_pos):,}")

# 0.2 scoring_date
scoring_date = pd.to_datetime(df_master["date"].max()) + pd.Timedelta(days=7)
print(f"  scoring_date: {scoring_date.date()}")

# ─────────────────────────────────────────────────────────────
# 0.3 MONTHLY PANEL  (zero-filled per pair, from first month to scoring_month)
# ─────────────────────────────────────────────────────────────
print("\n[Stage 0.3] Building monthly panel …")

df_pos["month"] = df_pos["date"].dt.to_period("M").dt.to_timestamp()
agg = (
    df_pos
    .groupby(["client_id", "product_family", "month"], observed=True)
    .agg(monthly_units=("units", "sum"),
         monthly_value=("sales_value", "sum"),
         order_count=("Num.Fact", pd.Series.nunique))
    .reset_index()
)
agg["had_purchase"] = (agg["order_count"] > 0).astype(int)

# zero-fill grid: per pair from first month to scoring_month
scoring_month = scoring_date.to_period("M").to_timestamp()
first_month   = (
    agg.groupby(["client_id", "product_family"], observed=True)["month"]
    .min().reset_index().rename(columns={"month": "first_month"})
)

all_months_global = pd.date_range(agg["month"].min(), scoring_month, freq="MS")
rows = []
for _, r in first_month.iterrows():
    months = all_months_global[all_months_global >= r["first_month"]]
    rows.append(pd.DataFrame({
        "client_id":      r["client_id"],
        "product_family": r["product_family"],
        "month":          months,
    }))
grid = pd.concat(rows, ignore_index=True)

monthly = grid.merge(agg, on=["client_id", "product_family", "month"], how="left")
monthly[["monthly_units","monthly_value","order_count","had_purchase"]] = (
    monthly[["monthly_units","monthly_value","order_count","had_purchase"]].fillna(0)
)
print(f"  monthly panel rows: {len(monthly):,}")

# ─────────────────────────────────────────────────────────────
# 0.4 CUSTOMER-FAMILY SUMMARY
# ─────────────────────────────────────────────────────────────
print("\n[Stage 0.4] Customer-family summary …")
last_purch = (
    df_pos.groupby(["client_id", "product_family"], observed=True)["date"]
    .max().reset_index().rename(columns={"date": "last_purchase_date"})
)
total_months = (
    monthly[monthly["had_purchase"] == 1]
    .groupby(["client_id", "product_family"], observed=True)["month"]
    .nunique().reset_index().rename(columns={"month": "total_purchase_months"})
)
total_value = (
    df_pos.groupby(["client_id", "product_family"], observed=True)["sales_value"]
    .sum().reset_index().rename(columns={"sales_value": "total_value_all"})
)

# attach static metadata: product_block, product_family_biz, province, segment_code
static_cols = (
    df_master[["client_id", "product_family", "product_family_biz",
               "product_block", "province", "segment_code"]]
    .drop_duplicates(subset=["client_id", "product_family"])
)

summary = (
    last_purch
    .merge(total_months, on=["client_id", "product_family"], how="left")
    .merge(total_value,  on=["client_id", "product_family"], how="left")
    .merge(static_cols,  on=["client_id", "product_family"], how="left")
)
summary["total_purchase_months"] = summary["total_purchase_months"].fillna(0).astype(int)
summary["total_value_all"]       = summary["total_value_all"].fillna(0)
summary["province"]              = summary["province"].fillna("Unknown")
summary["days_since_last"]       = (scoring_date - summary["last_purchase_date"]).dt.days
print(f"  summary rows (unique pairs): {len(summary):,}")

# 0.5 attach potential
pot_lookup = (
    df_potential
    .groupby(["client_id", "product_family_biz"])["potential_value"]
    .sum().reset_index()
)
summary = summary.merge(pot_lookup, on=["client_id", "product_family_biz"], how="left")
n_pot_miss = summary["potential_value"].isna().sum()
print(f"  potential lookup misses: {n_pot_miss:,}")

# 0.6 f1_scope (pairs already flagged by F1 as non-on-track)
f1_scope = set(map(
    tuple,
    f1_alerts[f1_alerts["priority_level"] != "On track"][["client_id", "product_family"]]
    .drop_duplicates().values
))
print(f"  f1_scope (pairs to exclude in B/C): {len(f1_scope):,}")

# ─────────────────────────────────────────────────────────────
# BRANCH A — T-products silence score
# ─────────────────────────────────────────────────────────────
print("\n[Branch A] T-products silence score …")

mask_A = (summary["product_block"] == "Productos Técnicos") & \
         (summary["total_purchase_months"] >= 1)
cand_A = summary[mask_A].copy()
print(f"  Branch A candidates: {len(cand_A):,}")

# compute intervals per pair (T-products only, units>0 dates)
# dedupe same-day purchases (same date counted as one reorder event)
t_purch = (
    df_pos[df_pos["product_block"] == "Productos Técnicos"]
    [["client_id", "product_family", "date"]]
    .drop_duplicates()
    .sort_values(["client_id", "product_family", "date"])
)

t_purch["prev_date"] = t_purch.groupby(
    ["client_id", "product_family"], observed=True
)["date"].shift(1)
t_purch["interval_days"] = (t_purch["date"] - t_purch["prev_date"]).dt.days
intervals_grouped = (
    t_purch.dropna(subset=["interval_days"])
    .groupby(["client_id", "product_family"], observed=True)["interval_days"]
    .agg(intervals=list, n="count")
    .reset_index()
)

cand_A = cand_A.merge(intervals_grouped, on=["client_id", "product_family"], how="left")
cand_A["n"] = cand_A["n"].fillna(0).astype(int)

def resolve_threshold(row):
    # Level A: customer's own p90 if intervals >= 3
    if row["n"] >= 3 and isinstance(row["intervals"], list):
        p90 = float(np.percentile(row["intervals"], 90))
        # safety floor: a reorder cycle cannot be sub-day (handles edge cases)
        return max(p90, 1.0), "high"
    # Level B fallback by family
    fam = row["product_family"]
    if fam == "Familia T1":
        return float(T1_FALLBACK_THRESHOLD), "low"
    elif fam == "Familia T2":
        return float(T2_FALLBACK_THRESHOLD), "low"
    return float(T2_FALLBACK_THRESHOLD), "low"  # safety net

resolved = cand_A.apply(resolve_threshold, axis=1, result_type="expand")
resolved.columns = ["threshold_used", "confidence_level"]
cand_A = pd.concat([cand_A, resolved], axis=1)

cand_A["silence_score"] = cand_A["days_since_last"] / cand_A["threshold_used"].clip(lower=1e-9)

def status_A(s):
    if s > 2.0:  return "Likely Lost"
    if s > 1.5:  return "At Risk"
    if s > 1.0:  return "Early Warning"
    return None

cand_A["lost_status"] = cand_A["silence_score"].apply(status_A)
branch_A = cand_A[cand_A["lost_status"].notna()].copy()
branch_A["method"] = "silence_score"
branch_A["raw_score"] = branch_A["silence_score"]
# explicit NaN columns
for col in ["volume_drop_ratio", "frequency_drop_ratio",
            "hist_avg_monthly_value", "recent_avg_monthly_value",
            "hist_purchase_rate", "recent_purchase_rate",
            "pattern_deterioration_score"]:
    branch_A[col] = np.nan

print(f"  Branch A alerts: {len(branch_A):,}")

# ─────────────────────────────────────────────────────────────
# BRANCH B — C-products direct flag (days_since > 730)
# ─────────────────────────────────────────────────────────────
print("\n[Branch B] C-products direct flag (>730d) …")

mask_B_base = (summary["product_block"] == "Commodities") & \
              (summary["days_since_last"] > 730)
cand_B = summary[mask_B_base].copy()
cand_B["_pair"] = list(zip(cand_B["client_id"], cand_B["product_family"]))
cand_B = cand_B[~cand_B["_pair"].isin(f1_scope)].drop(columns=["_pair"])
print(f"  Branch B alerts: {len(cand_B):,}")

branch_B = cand_B.copy()
branch_B["lost_status"]      = "Likely Lost"
branch_B["method"]           = "direct"
branch_B["confidence_level"] = "high"
branch_B["silence_score"]    = np.nan
branch_B["threshold_used"]   = np.nan
branch_B["raw_score"]        = branch_B["days_since_last"] / 730.0
for col in ["volume_drop_ratio", "frequency_drop_ratio",
            "hist_avg_monthly_value", "recent_avg_monthly_value",
            "hist_purchase_rate", "recent_purchase_rate",
            "pattern_deterioration_score"]:
    branch_B[col] = np.nan

# ─────────────────────────────────────────────────────────────
# BRANCH C — C-products active-degraded (historical pattern)
# ─────────────────────────────────────────────────────────────
print("\n[Branch C] C-products active-degraded …")

mask_C_base = (summary["product_block"] == "Commodities") & \
              (summary["days_since_last"] <= 730) & \
              (summary["total_purchase_months"] >= 3)
cand_C = summary[mask_C_base].copy()
cand_C["_pair"] = list(zip(cand_C["client_id"], cand_C["product_family"]))
cand_C = cand_C[~cand_C["_pair"].isin(f1_scope)].drop(columns=["_pair"])
print(f"  Branch C candidates (after f1_scope exclusion): {len(cand_C):,}")

# windows
recent_start = scoring_date - pd.DateOffset(months=12)
hist_start   = scoring_date - pd.DateOffset(months=24)
hist_end     = recent_start  # exclusive

# slice monthly panel
mc = monthly.merge(
    cand_C[["client_id", "product_family"]],
    on=["client_id", "product_family"], how="inner"
)
mask_recent = (mc["month"] >= recent_start) & (mc["month"] < scoring_date)
mask_hist   = (mc["month"] >= hist_start)   & (mc["month"] < hist_end)

recent = (
    mc[mask_recent].groupby(["client_id", "product_family"], observed=True)
    .agg(recent_purchase_months=("had_purchase", "sum"),
         recent_total_value=("monthly_value", "sum"))
    .reset_index()
)
hist = (
    mc[mask_hist].groupby(["client_id", "product_family"], observed=True)
    .agg(hist_purchase_months=("had_purchase", "sum"),
         hist_total_value=("monthly_value", "sum"))
    .reset_index()
)

c_features = cand_C.merge(recent, on=["client_id", "product_family"], how="left")
c_features = c_features.merge(hist,   on=["client_id", "product_family"], how="left")
c_features[["recent_purchase_months", "recent_total_value",
            "hist_purchase_months",   "hist_total_value"]] = (
    c_features[["recent_purchase_months", "recent_total_value",
                "hist_purchase_months",   "hist_total_value"]].fillna(0)
)

# C.2 skip if hist_purchase_months < 2
n_skipped_hist = (c_features["hist_purchase_months"] < 2).sum()
print(f"  skipped (hist_purchase_months < 2): {n_skipped_hist:,}")
c_features = c_features[c_features["hist_purchase_months"] >= 2].copy()

# C.3 features
c_features["recent_avg_monthly_value"] = c_features["recent_total_value"] / 12.0
c_features["hist_avg_monthly_value"]   = c_features["hist_total_value"]   / 12.0
c_features["recent_purchase_rate"]     = c_features["recent_purchase_months"] / 12.0
c_features["hist_purchase_rate"]       = c_features["hist_purchase_months"]   / 12.0

# C.4 deterioration signals
c_features["volume_drop_ratio"] = (
    np.maximum(0, c_features["hist_avg_monthly_value"] - c_features["recent_avg_monthly_value"])
    / (c_features["hist_avg_monthly_value"] + 1e-9)
)
c_features["frequency_drop_ratio"] = (
    np.maximum(0, c_features["hist_purchase_rate"] - c_features["recent_purchase_rate"])
    / (c_features["hist_purchase_rate"] + 1e-9)
)
c_features["pattern_deterioration_score"] = (
    0.5 * c_features["volume_drop_ratio"] + 0.5 * c_features["frequency_drop_ratio"]
)

def status_C(s):
    if s > 0.6:  return "Likely Lost"
    if s > 0.4:  return "At Risk"
    if s > 0.2:  return "Early Warning"
    return None

c_features["lost_status"] = c_features["pattern_deterioration_score"].apply(status_C)
branch_C = c_features[c_features["lost_status"].notna()].copy()
branch_C["method"]           = "historical_pattern"
branch_C["confidence_level"] = "medium"
branch_C["silence_score"]    = np.nan
branch_C["threshold_used"]   = np.nan
branch_C["raw_score"]        = branch_C["pattern_deterioration_score"]

print(f"  Branch C alerts: {len(branch_C):,}")

# ─────────────────────────────────────────────────────────────
# STAGE 1 — MERGE & DEDUP
# ─────────────────────────────────────────────────────────────
print("\n[Stage 1] Merging branches …")

common_cols = [
    "client_id", "product_family", "product_family_biz", "province", "segment_code",
    "last_purchase_date", "days_since_last",
    "silence_score", "threshold_used",
    "volume_drop_ratio", "frequency_drop_ratio",
    "hist_avg_monthly_value", "recent_avg_monthly_value",
    "hist_purchase_rate", "recent_purchase_rate",
    "pattern_deterioration_score",
    "lost_status", "method", "confidence_level",
    "raw_score", "potential_value",
]

def select_cols(df):
    out = pd.DataFrame()
    for c in common_cols:
        out[c] = df[c] if c in df.columns else np.nan
    return out

A_sel = select_cols(branch_A)
B_sel = select_cols(branch_B)
C_sel = select_cols(branch_C)

merged = pd.concat([A_sel, B_sel, C_sel], ignore_index=True)
print(f"  before dedup: {len(merged):,}")

# duplicate handling
n_dups_before = merged.duplicated(subset=["client_id", "product_family"], keep=False).sum()
merged = (
    merged.sort_values("raw_score", ascending=False)
          .drop_duplicates(subset=["client_id", "product_family"], keep="first")
          .reset_index(drop=True)
)
n_dups_dropped = n_dups_before - merged.duplicated(subset=["client_id", "product_family"]).sum() - len(merged) + (n_dups_before)
# clearer: count how many rows were dropped
n_dropped = (len(A_sel) + len(B_sel) + len(C_sel)) - len(merged)
print(f"  duplicates dropped (kept higher raw_score): {n_dropped:,}")

# ─────────────────────────────────────────────────────────────
# STAGE 2 — VALUE WEIGHTING
# ─────────────────────────────────────────────────────────────
print("\n[Stage 2] Value weighting …")

# historical_12m_value from monthly panel
hist_12m_start = scoring_date - pd.DateOffset(months=12)
hist_12m = (
    monthly[(monthly["month"] >= hist_12m_start) & (monthly["month"] < scoring_date)]
    .groupby(["client_id", "product_family"], observed=True)["monthly_value"]
    .sum().reset_index().rename(columns={"monthly_value": "historical_12m_value"})
)
merged = merged.merge(hist_12m, on=["client_id", "product_family"], how="left")
merged["historical_12m_value"] = merged["historical_12m_value"].fillna(0)

# raw_value
def compute_raw_value(row):
    pot = row["potential_value"]
    h12 = row["historical_12m_value"]
    pot_valid = pd.notna(pot) and pot > 0
    h12_valid = pd.notna(h12) and h12 > 0
    if pot_valid and h12_valid:  return max(pot, h12)
    if pot_valid:                return pot
    if h12_valid:                return h12
    return 1.0

merged["raw_value"] = merged.apply(compute_raw_value, axis=1)

# value_factor: minmax(log1p(raw_value))
log_v = np.log1p(merged["raw_value"].clip(lower=0))
v_min, v_max = log_v.min(), log_v.max()
if v_max - v_min < 1e-12:
    merged["value_factor"] = 1.0
else:
    merged["value_factor"] = (log_v - v_min) / (v_max - v_min)

merged["f2_priority_score"] = merged["raw_score"] * merged["value_factor"]

# ─────────────────────────────────────────────────────────────
# STAGE 3 — PRIORITY BINS
# ─────────────────────────────────────────────────────────────
print("\n[Stage 3] Priority binning …")
q95 = merged["f2_priority_score"].quantile(0.95)
q80 = merged["f2_priority_score"].quantile(0.80)
q50 = merged["f2_priority_score"].quantile(0.50)

def assign_priority(s):
    if s >= q95:  return "P1 Critical"
    if s >= q80:  return "P2 High"
    if s >= q50:  return "P3 Medium"
    return "P4 Low"

merged["priority_level"] = merged["f2_priority_score"].apply(assign_priority)

# ─────────────────────────────────────────────────────────────
# FINAL OUTPUT TABLE
# ─────────────────────────────────────────────────────────────
print("\n[Final] Building output table …")

# sort by priority score desc, then assign alert_id
merged = merged.sort_values("f2_priority_score", ascending=False).reset_index(drop=True)
merged["alert_id"] = ["F2-" + str(i + 1).zfill(6) for i in range(len(merged))]
merged["alert_type"] = "Lost Customer Risk"
merged["status"] = "Pending"
merged = merged.rename(columns={"days_since_last": "days_since_last_purchase"})

output_cols = [
    "alert_id", "client_id", "product_family", "product_family_biz",
    "province", "segment_code",
    "alert_type", "method", "lost_status",
    "last_purchase_date", "days_since_last_purchase",
    "silence_score", "threshold_used",
    "volume_drop_ratio", "frequency_drop_ratio",
    "hist_avg_monthly_value", "recent_avg_monthly_value",
    "hist_purchase_rate", "recent_purchase_rate",
    "raw_score", "value_factor", "f2_priority_score",
    "priority_level", "confidence_level", "status",
]

final = merged[output_cols].copy()
final.to_parquet(OUTPUT_DIR / "f2_lost_customer_alerts.parquet", index=False)

# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
n_A = len(branch_A)
n_B = len(branch_B)
n_C = len(branch_C)
n_total = len(final)
n_p1   = (final["priority_level"] == "P1 Critical").sum()
n_p2   = (final["priority_level"] == "P2 High").sum()
n_p1p2 = n_p1 + n_p2
n_ll = (final["lost_status"] == "Likely Lost").sum()
n_ar = (final["lost_status"] == "At Risk").sum()
n_ew = (final["lost_status"] == "Early Warning").sum()

n_excluded_BC = sum(
    1 for _, row in summary.iterrows()
    if row["product_block"] == "Commodities"
       and (row["client_id"], row["product_family"]) in f1_scope
)

top10 = final.nlargest(10, "f2_priority_score")[
    ["alert_id", "client_id", "product_family_biz", "method",
     "lost_status", "priority_level", "f2_priority_score",
     "days_since_last_purchase"]
]

prov_top10 = final["province"].value_counts().head(10)
fam_dist   = final["product_family"].value_counts()
prio_dist  = final["priority_level"].value_counts()
status_dist = final["lost_status"].value_counts()

report = [
    "# F2 — Lost Customer Risk Diagnostics",
    "",
    f"**Scoring date:** {scoring_date.date()}",
    "",
    "## Branch counts (before dedup)",
    f"- Branch A (T silence):       {n_A:,}",
    f"- Branch B (C direct >730d):  {n_B:,}",
    f"- Branch C (C historical):    {n_C:,}",
    f"- Duplicates dropped on merge: {n_dropped:,}",
    f"- **Total alerts:** {n_total:,}",
    "",
    "## lost_status distribution",
] + [f"- {k}: {v:,}" for k, v in status_dist.items()] + [
    "",
    "## priority_level distribution",
] + [f"- {k}: {v:,}" for k, v in prio_dist.items()] + [
    "",
    "## product_family distribution",
] + [f"- {k}: {v:,}" for k, v in fam_dist.items()] + [
    "",
    "## Top 10 provinces",
] + [f"- {k}: {v:,}" for k, v in prov_top10.items()] + [
    "",
    "## Branch C skipped (hist_purchase_months < 2)",
    f"- {n_skipped_hist:,} pairs",
    "",
    "## f1_scope exclusion (C-products already flagged by F1)",
    f"- excluded from B/C consideration: {n_excluded_BC:,} pairs",
    "",
    "## Merge dedup",
    f"- duplicates dropped (higher raw_score kept): {n_dropped:,}",
    "",
    "## Top 10 alerts",
    "",
    top10.to_string(index=False),
]

(OUTPUT_DIR / "f2_diagnostics.md").write_text("\n".join(report))

# ─────────────────────────────────────────────────────────────
# RUN-END LOG
# ─────────────────────────────────────────────────────────────
print()
print(f"[F2] Branch A (T products silence):     {n_A} alerts")
print(f"[F2] Branch B (C direct >730d):         {n_B} alerts")
print(f"[F2] Branch C (C historical pattern):   {n_C} alerts")
print(f"[F2] Total alerts:                      {n_total}")
print(f"[F2] P1+P2:                             {n_p1p2}")
print(f"[F2] Likely Lost / At Risk / Early Warning: {n_ll} / {n_ar} / {n_ew}")
print(f"[F2] Saved → {OUTPUT_DIR / 'f2_lost_customer_alerts.parquet'}")
print(f"[F2] Saved → {OUTPUT_DIR / 'f2_diagnostics.md'}")
