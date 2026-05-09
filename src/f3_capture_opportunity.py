"""
F3 — Capture Opportunity / Competitor Leakage Detection
Inibsa Smart Demand Signals

Two independent branches:
  A. Active customers with low potential utilization → Underutilization
  B. Cold-start (in Potencial, never purchased) → New Account Opportunity

Granularity: client_id × product_family_biz  (3 business families, NOT 4 codes)

Outputs:  ./output/f3/f3_capture_opportunity_alerts.parquet
          ./output/f3/f3_diagnostics.md
"""
import warnings
import random
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED); np.random.seed(SEED)

INPUT_STAGE0 = Path("./output/stage0")
INPUT_F2     = Path("./output/f2")
OUTPUT_DIR   = Path("./output/f3")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# F2 product_family → business name map (severity ordering for de-dup)
LOST_STATUS_SEVERITY = {"Likely Lost": 3, "At Risk": 2, "Early Warning": 1}

# ─────────────────────────────────────────────────────────────
print("=" * 70)
print("F3 — CAPTURE OPPORTUNITY / COMPETITOR LEAKAGE DETECTION")
print("=" * 70)

# ─────────────────────────────────────────────────────────────
# STAGE 0 — DATA PREP
# ─────────────────────────────────────────────────────────────
print("\n[Stage 0] Loading inputs …")
df_master    = pd.read_parquet(INPUT_STAGE0 / "df_master.parquet")
df_potential = pd.read_parquet(INPUT_STAGE0 / "df_potential.parquet")
df_cold      = pd.read_parquet(INPUT_STAGE0 / "df_cold_clients.parquet")
df_master["date"] = pd.to_datetime(df_master["date"])

# F2 alerts (optional)
f2_path = INPUT_F2 / "f2_lost_customer_alerts.parquet"
if f2_path.exists():
    f2_alerts = pd.read_parquet(f2_path)
    print(f"  f2_alerts loaded: {len(f2_alerts):,}")
    f2_available = True
else:
    f2_alerts = None
    f2_available = False
    print("  f2_alerts NOT FOUND — capture_window_flag will all be NORMAL")

print(f"  df_master:    {len(df_master):,}")
print(f"  df_potential: {len(df_potential):,}")
print(f"  df_cold:      {len(df_cold):,}")

# 0.1 scoring_date
scoring_date = pd.to_datetime(df_master["date"].max()) + pd.Timedelta(days=7)
print(f"  scoring_date: {scoring_date.date()}")

# 0.2 positive purchases only, aggregate to (client_id, product_family_biz)
df_pos = df_master[df_master["units"] > 0].copy()
df_pos["month"] = df_pos["date"].dt.to_period("M").dt.to_timestamp()

cutoff_12m = scoring_date - pd.Timedelta(days=365)
cutoff_24m = scoring_date - pd.Timedelta(days=730)

purchase_agg = (
    df_pos.groupby(["client_id", "product_family_biz"], observed=True)
    .agg(last_purchase_date_biz=("date", "max"),
         total_purchase_months=("month", "nunique"))
    .reset_index()
)

obs_12m = (
    df_pos[df_pos["date"] >= cutoff_12m]
    .groupby(["client_id", "product_family_biz"], observed=True)["sales_value"]
    .sum().reset_index().rename(columns={"sales_value": "observed_value_12m"})
)
obs_24m = (
    df_pos[df_pos["date"] >= cutoff_24m]
    .groupby(["client_id", "product_family_biz"], observed=True)["sales_value"]
    .sum().reset_index().rename(columns={"sales_value": "observed_value_24m"})
)

purchase_agg = (
    purchase_agg
    .merge(obs_12m, on=["client_id", "product_family_biz"], how="left")
    .merge(obs_24m, on=["client_id", "product_family_biz"], how="left")
)
purchase_agg[["observed_value_12m", "observed_value_24m"]] = (
    purchase_agg[["observed_value_12m", "observed_value_24m"]].fillna(0)
)
purchase_agg["days_since_last"] = (scoring_date - purchase_agg["last_purchase_date_biz"]).dt.days
print(f"  purchase aggregation rows: {len(purchase_agg):,}")

# 0.3 clean potential
n_pot_invalid = ((df_potential["potential_value"].isna()) | (df_potential["potential_value"] <= 0)).sum()
df_potential_clean = df_potential[df_potential["potential_value"] > 0].copy()
# Some clients may have multiple rows per family_biz (different categoria) — sum
df_potential_clean = (
    df_potential_clean
    .groupby(["client_id", "product_family_biz"])["potential_value"]
    .sum().reset_index()
)
print(f"  potential invalid rows (NaN or ≤0): {n_pot_invalid:,}")
print(f"  potential clean (after sum):        {len(df_potential_clean):,}")

# 0.4 cold-start IDs
cold_ids = set(df_cold["client_id"].astype(str).unique())
print(f"  cold-start clients: {len(cold_ids):,}")

# 0.5 Static metadata at client level
client_meta = (
    df_master[["client_id", "province", "segment_code"]]
    .drop_duplicates(subset=["client_id"])
)
client_meta["province"]     = client_meta["province"].fillna("Unknown")
client_meta["segment_code"] = client_meta["segment_code"].fillna(np.nan)

# Cold clients may not be in df_master — fall back to df_cold (which itself was joined with Clientes)
cold_meta = (
    df_cold[["client_id", "province", "segment_code"]].drop_duplicates(subset=["client_id"])
    if "province" in df_cold.columns else
    pd.DataFrame(columns=["client_id", "province", "segment_code"])
)
if "province" in cold_meta.columns:
    cold_meta["province"]     = cold_meta["province"].fillna("Unknown")

# 0.6 F2 lookup: (client_id, product_family_biz) → most-severe lost_status
if f2_available:
    f2_alerts_biz = f2_alerts.copy()
    if "product_family_biz" not in f2_alerts_biz.columns:
        # safety: rebuild from product_family
        FAM2BIZ = {"Familia C1":"Anestesia", "Familia C2":"Bioseguridad",
                   "Familia T1":"Biomateriales", "Familia T2":"Biomateriales"}
        f2_alerts_biz["product_family_biz"] = f2_alerts_biz["product_family"].map(FAM2BIZ)
    f2_alerts_biz["sev"] = f2_alerts_biz["lost_status"].map(LOST_STATUS_SEVERITY).fillna(0)
    f2_lookup = (
        f2_alerts_biz.sort_values("sev", ascending=False)
        .drop_duplicates(subset=["client_id", "product_family_biz"], keep="first")
        [["client_id", "product_family_biz", "lost_status"]]
        .rename(columns={"lost_status": "lost_status_f2"})
    )
else:
    f2_lookup = pd.DataFrame(columns=["client_id", "product_family_biz", "lost_status_f2"])

# 0.7 F3 candidate table
f3_candidates = df_potential_clean.merge(
    purchase_agg, on=["client_id", "product_family_biz"], how="left"
)
f3_candidates["is_cold_start"] = f3_candidates["client_id"].astype(str).isin(cold_ids)
# attach client meta
f3_candidates = f3_candidates.merge(client_meta, on="client_id", how="left")
# fill cold-start province from df_cold (when missing in df_master)
if "province" in cold_meta.columns:
    cold_idx = f3_candidates["province"].isna()
    cold_meta_indexed = cold_meta.set_index("client_id")
    f3_candidates.loc[cold_idx, "province"] = (
        f3_candidates.loc[cold_idx, "client_id"]
        .map(cold_meta_indexed["province"]).fillna("Unknown")
    )
f3_candidates["province"] = f3_candidates["province"].fillna("Unknown")
# attach F2 lookup
f3_candidates = f3_candidates.merge(f2_lookup, on=["client_id", "product_family_biz"], how="left")
print(f"  f3_candidates: {len(f3_candidates):,}")

# ─────────────────────────────────────────────────────────────
# BRANCH A — Active customers with low utilization
# ─────────────────────────────────────────────────────────────
print("\n[Branch A] Underutilization …")

mask_A = (
    (~f3_candidates["is_cold_start"]) &
    (f3_candidates["potential_value"] > 0) &
    ((f3_candidates["observed_value_12m"].fillna(0) > 0) |
     (f3_candidates["observed_value_24m"].fillna(0) > 0))
)
cand_A = f3_candidates[mask_A].copy()
cand_A[["observed_value_12m", "observed_value_24m"]] = (
    cand_A[["observed_value_12m", "observed_value_24m"]].fillna(0)
)
print(f"  Branch A candidates: {len(cand_A):,}")

# A.1 features
cand_A["utilization_ratio"] = (
    (cand_A["observed_value_12m"] / (cand_A["potential_value"] + 1e-9))
    .clip(lower=0, upper=1.0)
)
cand_A["potential_gap"] = np.maximum(
    0, cand_A["potential_value"] - cand_A["observed_value_12m"]
)
cand_A["low_utilization_score"] = np.maximum(0, 1.0 - cand_A["utilization_ratio"])

# A.2 skip if utilization >= 0.8
n_skipped_high_util = (cand_A["utilization_ratio"] >= 0.8).sum()
cand_A = cand_A[cand_A["utilization_ratio"] < 0.8].copy()
print(f"  skipped (utilization ≥ 0.8): {n_skipped_high_util:,}")
print(f"  Branch A after skip:         {len(cand_A):,}")

# A.3 normalized_potential_gap (within Branch A only)
log_gap = np.log1p(cand_A["potential_gap"].clip(lower=0))
g_min, g_max = log_gap.min(), log_gap.max()
denom = g_max - g_min
cand_A["normalized_potential_gap"] = (
    (log_gap - g_min) / (denom if denom > 1e-12 else 1.0)
) if denom > 1e-12 else 1.0

cand_A["opportunity_score"] = (
    0.6 * cand_A["low_utilization_score"]
    + 0.4 * cand_A["normalized_potential_gap"]
)

# A.4 opportunity_type
def opp_type_A(u):
    if u < 0.2:  return "High Potential Underutilization"
    if u < 0.5:  return "Moderate Underutilization"
    return "Mild Underutilization"
cand_A["opportunity_type"] = cand_A["utilization_ratio"].apply(opp_type_A)

# A.5 confidence_level
def conf_A(n):
    if n >= 6: return "high"
    if n >= 3: return "medium"
    return "low"
cand_A["total_purchase_months"] = cand_A["total_purchase_months"].fillna(0).astype(int)
cand_A["confidence_level"] = cand_A["total_purchase_months"].apply(conf_A)
cand_A["method"] = "underutilization"
cand_A["raw_score"] = cand_A["opportunity_score"]

# ─────────────────────────────────────────────────────────────
# BRANCH B — Cold-start customers
# ─────────────────────────────────────────────────────────────
print("\n[Branch B] Cold-start …")

mask_B = (f3_candidates["is_cold_start"]) & (f3_candidates["potential_value"] > 0)
cand_B = f3_candidates[mask_B].copy()
print(f"  Branch B candidates: {len(cand_B):,}")

cand_B["utilization_ratio"]      = 0.0
cand_B["potential_gap"]          = cand_B["potential_value"]
cand_B["low_utilization_score"]  = 1.0
cand_B["observed_value_12m"]     = np.nan
cand_B["observed_value_24m"]     = np.nan
cand_B["last_purchase_date_biz"] = pd.NaT
cand_B["days_since_last"]        = np.nan
cand_B["total_purchase_months"]  = 0

log_pot = np.log1p(cand_B["potential_value"].clip(lower=0))
p_min, p_max = log_pot.min(), log_pot.max()
denom = p_max - p_min
cand_B["normalized_potential_gap"] = (
    (log_pot - p_min) / (denom if denom > 1e-12 else 1.0)
) if denom > 1e-12 else 1.0

cand_B["opportunity_score"] = 1.0 * cand_B["normalized_potential_gap"]
cand_B["opportunity_type"]  = "New Account Opportunity"
cand_B["confidence_level"]  = "low"
cand_B["method"]            = "cold_start"
cand_B["raw_score"]         = cand_B["opportunity_score"]

# ─────────────────────────────────────────────────────────────
# STAGE 1 — MERGE
# ─────────────────────────────────────────────────────────────
print("\n[Stage 1] Merging …")

common_cols = [
    "client_id", "product_family_biz", "province", "segment_code",
    "is_cold_start", "last_purchase_date_biz", "days_since_last",
    "total_purchase_months",
    "potential_value", "observed_value_12m", "observed_value_24m",
    "utilization_ratio", "potential_gap", "low_utilization_score",
    "normalized_potential_gap", "opportunity_score",
    "opportunity_type", "lost_status_f2",
    "method", "confidence_level", "raw_score",
]
def select(df):
    out = pd.DataFrame()
    for c in common_cols:
        out[c] = df[c] if c in df.columns else np.nan
    return out

merged = pd.concat([select(cand_A), select(cand_B)], ignore_index=True)

# de-dup safety
n_before = len(merged)
merged = (merged.sort_values("raw_score", ascending=False)
          .drop_duplicates(subset=["client_id", "product_family_biz"], keep="first")
          .reset_index(drop=True))
n_dropped = n_before - len(merged)
print(f"  duplicates dropped: {n_dropped:,}")
print(f"  merged total:       {len(merged):,}")

# ─────────────────────────────────────────────────────────────
# STAGE 2 — F2 LINKAGE  (separation of concerns: F3=capture, F2=win-back)
# ─────────────────────────────────────────────────────────────
print("\n[Stage 2] F2 linkage (capture/win-back separation) …")

# Drop F2 'Likely Lost' clients — they belong to F2's win-back queue, not F3.
n_before_f2_filter = len(merged)
n_dropped_lost = (merged["lost_status_f2"] == "Likely Lost").sum()
merged = merged[merged["lost_status_f2"] != "Likely Lost"].reset_index(drop=True)
print(f"  dropped 'Likely Lost' (handed off to F2): {n_dropped_lost:,}")
print(f"  remaining F3 candidates:                  {len(merged):,}")

# No score boost — let raw_score speak for itself. capture_window_flag is
# now informational only, used by the dashboard to differentiate visuals.
merged["raw_score_pre_boost"] = merged["raw_score"]

def capture_flag(row):
    if row["method"] == "cold_start":
        return "COLD_START"
    status = row["lost_status_f2"]
    if status == "At Risk":
        return "TRANSITIONAL"        # borderline: degrading but not lost
    if status == "Early Warning":
        return "MONITOR"              # mild degradation
    return "FRESH_OPPORTUNITY"        # healthy active client, low utilization

merged["capture_window_flag"] = merged.apply(capture_flag, axis=1)
# raw_score_final == raw_score (no boost); kept for backward-compatible schema
merged["raw_score_final"] = merged["raw_score_pre_boost"]

flag_counts = merged["capture_window_flag"].value_counts()
print(f"  capture_window_flag: {flag_counts.to_dict()}")

# ─────────────────────────────────────────────────────────────
# STAGE 3 — VALUE WEIGHTING
# ─────────────────────────────────────────────────────────────
print("\n[Stage 3] Value weighting …")
log_v = np.log1p(merged["potential_value"].clip(lower=0))
v_min, v_max = log_v.min(), log_v.max()
denom = v_max - v_min
merged["value_factor"] = (
    (log_v - v_min) / (denom if denom > 1e-12 else 1.0)
) if denom > 1e-12 else 1.0

merged["f3_priority_score"] = merged["raw_score_final"] * merged["value_factor"]

# ─────────────────────────────────────────────────────────────
# STAGE 4 — PRIORITY BINS
# ─────────────────────────────────────────────────────────────
print("\n[Stage 4] Priority binning …")
q95 = merged["f3_priority_score"].quantile(0.95)
q80 = merged["f3_priority_score"].quantile(0.80)
q50 = merged["f3_priority_score"].quantile(0.50)
def prio(s):
    if s >= q95: return "P1 Critical"
    if s >= q80: return "P2 High"
    if s >= q50: return "P3 Medium"
    return "P4 Low"
merged["priority_level"] = merged["f3_priority_score"].apply(prio)

# ─────────────────────────────────────────────────────────────
# FINAL OUTPUT TABLE
# ─────────────────────────────────────────────────────────────
print("\n[Final] Building output …")
merged = merged.sort_values("f3_priority_score", ascending=False).reset_index(drop=True)
merged["alert_id"]   = ["F3-" + str(i+1).zfill(6) for i in range(len(merged))]
merged["alert_type"] = "Capture Opportunity"
merged["status"]     = "Pending"
merged = merged.rename(columns={
    "last_purchase_date_biz":  "last_purchase_date",
    "days_since_last":         "days_since_last_purchase",
})

output_cols = [
    "alert_id", "client_id", "product_family_biz", "province", "segment_code",
    "alert_type", "method", "opportunity_type", "is_cold_start",
    "capture_window_flag", "lost_status_f2",
    "last_purchase_date", "days_since_last_purchase", "total_purchase_months",
    "potential_value", "observed_value_12m", "observed_value_24m",
    "utilization_ratio", "potential_gap", "low_utilization_score",
    "normalized_potential_gap", "opportunity_score",
    "raw_score_pre_boost", "raw_score_final", "value_factor",
    "f3_priority_score", "priority_level", "confidence_level", "status",
]
final = merged[output_cols].copy()
final.to_parquet(OUTPUT_DIR / "f3_capture_opportunity_alerts.parquet", index=False)

# ─────────────────────────────────────────────────────────────
# DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
n_A      = len(cand_A)
n_B      = len(cand_B)
n_total  = len(final)
n_p1     = (final["priority_level"]=="P1 Critical").sum()
n_p2     = (final["priority_level"]=="P2 High").sum()
n_p1p2   = n_p1 + n_p2
n_fresh    = (final["capture_window_flag"]=="FRESH_OPPORTUNITY").sum()
n_trans    = (final["capture_window_flag"]=="TRANSITIONAL").sum()
n_monitor  = (final["capture_window_flag"]=="MONITOR").sum()
n_cold     = (final["capture_window_flag"]=="COLD_START").sum()
n_high_under = (final["opportunity_type"]=="High Potential Underutilization").sum()
n_mod_under  = (final["opportunity_type"]=="Moderate Underutilization").sum()
n_mild_under = (final["opportunity_type"]=="Mild Underutilization").sum()
n_new_acct   = (final["opportunity_type"]=="New Account Opportunity").sum()
cold_pct     = final["is_cold_start"].mean() * 100

opp_dist  = final["opportunity_type"].value_counts()
flag_dist = final["capture_window_flag"].value_counts()
prio_dist = final["priority_level"].value_counts()
fam_dist  = final["product_family_biz"].value_counts()
prov_top  = final["province"].value_counts().head(10)

top10 = final.nlargest(10, "f3_priority_score")[
    ["alert_id", "client_id", "product_family_biz", "method",
     "opportunity_type", "capture_window_flag",
     "utilization_ratio", "potential_value", "f3_priority_score", "priority_level"]
]

report = [
    "# F3 — Capture Opportunity Diagnostics",
    "",
    f"**Scoring date:** {scoring_date.date()}",
    "",
    "## Branch counts",
    f"- Branch A (Underutilization):  {n_A:,}",
    f"- Branch B (Cold-start):        {n_B:,}",
    f"- Duplicates dropped on merge:   {n_dropped:,}",
    f"- **Total alerts:** {n_total:,}",
    "",
    "## opportunity_type distribution",
] + [f"- {k}: {v:,}" for k, v in opp_dist.items()] + [
    "",
    "## capture_window_flag distribution",
] + [f"- {k}: {v:,}" for k, v in flag_dist.items()] + [
    "",
    "## priority_level distribution",
] + [f"- {k}: {v:,}" for k, v in prio_dist.items()] + [
    "",
    "## product_family_biz distribution",
] + [f"- {k}: {v:,}" for k, v in fam_dist.items()] + [
    "",
    "## Top 10 provinces",
] + [f"- {k}: {v:,}" for k, v in prov_top.items()] + [
    "",
    "## Quality control",
    f"- potential_value invalid (NaN or ≤0) dropped: {n_pot_invalid:,} rows from raw potencial table",
    f"- utilization_ratio ≥ 0.8 skipped:             {n_skipped_high_util:,} pairs",
    f"- F2 file present:                              {f2_available}",
    f"- Cold-start in alerts:                         {final['is_cold_start'].sum():,} ({cold_pct:.1f}%)",
    "",
    "## F2 linkage breakdown (capture_window_flag)",
    f"- FRESH_OPPORTUNITY:  {n_fresh:,}",
    f"- TRANSITIONAL:       {n_trans:,}",
    f"- MONITOR:            {n_monitor:,}",
    f"- COLD_START:         {n_cold:,}",
    "",
    f"## F2 hand-off",
    f"- Dropped 'Likely Lost' rows (handed to F2 win-back queue): {n_dropped_lost:,}",
    "",
    "## Top 10 alerts",
    "",
    top10.to_string(index=False),
]
(OUTPUT_DIR / "f3_diagnostics.md").write_text("\n".join(report))

# ─────────────────────────────────────────────────────────────
# RUN-END LOG
# ─────────────────────────────────────────────────────────────
print()
print(f"[F3] Branch A (Underutilization):       {n_A} alerts")
print(f"[F3] Branch B (Cold-start):             {n_B} alerts")
print(f"[F3] Total alerts:                      {n_total}")
print(f"[F3] P1+P2:                             {n_p1p2}")
print(f"[F3] handed off to F2 (Likely Lost):    {n_dropped_lost} rows")
print(f"[F3] capture_window_flag:")
print(f"     FRESH_OPPORTUNITY:  {n_fresh}")
print(f"     TRANSITIONAL:       {n_trans}")
print(f"     MONITOR:            {n_monitor}")
print(f"     COLD_START:         {n_cold}")
print(f"[F3] opportunity_type:")
print(f"     High Potential Underutilization: {n_high_under}")
print(f"     Moderate Underutilization:        {n_mod_under}")
print(f"     Mild Underutilization:            {n_mild_under}")
print(f"     New Account Opportunity:          {n_new_acct}")
print(f"[F3] Saved → {OUTPUT_DIR / 'f3_capture_opportunity_alerts.parquet'}")
print(f"[F3] Saved → {OUTPUT_DIR / 'f3_diagnostics.md'}")
