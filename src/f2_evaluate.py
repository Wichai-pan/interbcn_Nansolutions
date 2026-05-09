"""
F2 — Historical Backtest Evaluation
Inibsa Smart Demand Signals

Evaluation design:
  * Observation date: 2025-06-30
  * Future window:    2025-07-01 → 2025-12-29 (6 months ground truth)
  * Re-run F2 logic using only data ≤ obs_date
  * Construct proxy labels from future window:
       strict_lost  : no purchase in next 6 months
       lenient_lost : future 6m value < 40% × historical 6m mean
  * Metrics: AUROC, AUPRC, Precision/Recall/Lift@TopK,
             hit-rate by lost_status, hit-rate by priority_level

Outputs:
    ./output/f2/f2_backtest_metrics.json
    ./output/f2/f2_evaluation_report.md
"""
import json
import random
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import roc_auc_score, average_precision_score

# ─────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED); np.random.seed(SEED)

INPUT_STAGE0 = Path("./output/stage0")
OUTPUT_DIR   = Path("./output/f2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OBS_DATE     = pd.Timestamp("2025-06-30")
FUTURE_END   = pd.Timestamp("2025-12-29")   # data panel end
HIST_MONTHS  = 6                             # historical window for lenient label
T1_FALLBACK  = 210
T2_FALLBACK  = 251

print("=" * 70)
print("F2 — BACKTEST EVALUATION")
print("=" * 70)
print(f"  Observation date: {OBS_DATE.date()}")
print(f"  Future window:    {(OBS_DATE + pd.Timedelta(days=1)).date()} → {FUTURE_END.date()}")

# ─────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────
print("\n[Load] Reading inputs …")
df_master    = pd.read_parquet(INPUT_STAGE0 / "df_master.parquet")
df_potential = pd.read_parquet(INPUT_STAGE0 / "df_potential.parquet")
df_master["date"] = pd.to_datetime(df_master["date"])

df_pos = df_master[df_master["units"] > 0].copy()

# Past-only data (≤ obs_date) — used for re-running F2
df_past = df_pos[df_pos["date"] <= OBS_DATE].copy()
df_future = df_pos[(df_pos["date"] > OBS_DATE) & (df_pos["date"] <= FUTURE_END)].copy()
print(f"  past rows: {len(df_past):,}  |  future rows: {len(df_future):,}")

# ─────────────────────────────────────────────────────────────
# RE-COMPUTE F2 SCORES AT OBS_DATE (skip f1_scope to evaluate F2 standalone)
# ─────────────────────────────────────────────────────────────
print("\n[F2-recompute] Running F2 logic at obs_date …")

# Monthly panel from past data
df_past["month"] = df_past["date"].dt.to_period("M").dt.to_timestamp()
agg = (
    df_past
    .groupby(["client_id", "product_family", "month"], observed=True)
    .agg(monthly_units=("units", "sum"),
         monthly_value=("sales_value", "sum"),
         order_count=("Num.Fact", pd.Series.nunique))
    .reset_index()
)
agg["had_purchase"] = (agg["order_count"] > 0).astype(int)

scoring_month = OBS_DATE.to_period("M").to_timestamp()
first_month = (
    agg.groupby(["client_id","product_family"], observed=True)["month"]
    .min().reset_index().rename(columns={"month": "first_month"})
)
all_months_global = pd.date_range(agg["month"].min(), scoring_month, freq="MS")
rows = []
for _, r in first_month.iterrows():
    months = all_months_global[all_months_global >= r["first_month"]]
    rows.append(pd.DataFrame({
        "client_id": r["client_id"], "product_family": r["product_family"],
        "month": months,
    }))
grid = pd.concat(rows, ignore_index=True)
monthly = grid.merge(agg, on=["client_id","product_family","month"], how="left")
monthly[["monthly_units","monthly_value","order_count","had_purchase"]] = (
    monthly[["monthly_units","monthly_value","order_count","had_purchase"]].fillna(0)
)

# Customer-family summary
last_purch = df_past.groupby(["client_id","product_family"], observed=True)["date"].max().reset_index()
last_purch.columns = ["client_id","product_family","last_purchase_date"]

total_months = (
    monthly[monthly["had_purchase"]==1]
    .groupby(["client_id","product_family"], observed=True)["month"]
    .nunique().reset_index().rename(columns={"month": "total_purchase_months"})
)

static_cols = (
    df_master[["client_id","product_family","product_family_biz",
               "product_block","province","segment_code"]]
    .drop_duplicates(subset=["client_id","product_family"])
)

summary = (
    last_purch
    .merge(total_months, on=["client_id","product_family"], how="left")
    .merge(static_cols,  on=["client_id","product_family"], how="left")
)
summary["total_purchase_months"] = summary["total_purchase_months"].fillna(0).astype(int)
summary["province"] = summary["province"].fillna("Unknown")
summary["days_since_last"] = (OBS_DATE - summary["last_purchase_date"]).dt.days
print(f"  past pairs: {len(summary):,}")

# Branch A: T-product silence
mask_A = (summary["product_block"]=="Productos Técnicos") & (summary["total_purchase_months"]>=1)
cand_A = summary[mask_A].copy()

t_purch = (
    df_past[df_past["product_block"]=="Productos Técnicos"]
    [["client_id","product_family","date"]]
    .drop_duplicates()
    .sort_values(["client_id","product_family","date"])
)
t_purch["prev"] = t_purch.groupby(["client_id","product_family"], observed=True)["date"].shift(1)
t_purch["interval_days"] = (t_purch["date"] - t_purch["prev"]).dt.days
intervals = (
    t_purch.dropna(subset=["interval_days"])
    .groupby(["client_id","product_family"], observed=True)["interval_days"]
    .agg(intervals=list, n="count").reset_index()
)
cand_A = cand_A.merge(intervals, on=["client_id","product_family"], how="left")
cand_A["n"] = cand_A["n"].fillna(0).astype(int)

def resolve_threshold(row):
    if row["n"] >= 3 and isinstance(row["intervals"], list):
        return max(float(np.percentile(row["intervals"], 90)), 1.0), "high"
    fam = row["product_family"]
    if fam == "Familia T1":  return float(T1_FALLBACK), "low"
    if fam == "Familia T2":  return float(T2_FALLBACK), "low"
    return float(T2_FALLBACK), "low"

resolved = cand_A.apply(resolve_threshold, axis=1, result_type="expand")
resolved.columns = ["threshold_used", "confidence_level"]
cand_A = pd.concat([cand_A, resolved], axis=1)
cand_A["silence_score"] = cand_A["days_since_last"] / cand_A["threshold_used"].clip(lower=1e-9)

def status_A(s):
    if s > 2.0: return "Likely Lost"
    if s > 1.5: return "At Risk"
    if s > 1.0: return "Early Warning"
    return None
cand_A["lost_status"] = cand_A["silence_score"].apply(status_A)
branch_A = cand_A[cand_A["lost_status"].notna()].copy()
branch_A["method"] = "silence_score"
branch_A["raw_score"] = branch_A["silence_score"]
print(f"  Branch A alerts: {len(branch_A):,}")

# Branch B: C-product direct (>730d) — no f1_scope exclusion in eval mode
mask_B = (summary["product_block"]=="Commodities") & (summary["days_since_last"]>730)
branch_B = summary[mask_B].copy()
branch_B["lost_status"] = "Likely Lost"
branch_B["method"] = "direct"
branch_B["confidence_level"] = "high"
branch_B["raw_score"] = branch_B["days_since_last"] / 730.0
print(f"  Branch B alerts: {len(branch_B):,}")

# Branch C: C-product active-degraded
mask_C = (summary["product_block"]=="Commodities") & \
         (summary["days_since_last"]<=730) & (summary["total_purchase_months"]>=3)
cand_C = summary[mask_C].copy()

recent_start = OBS_DATE - pd.DateOffset(months=12)
hist_start   = OBS_DATE - pd.DateOffset(months=24)
hist_end     = recent_start

mc = monthly.merge(cand_C[["client_id","product_family"]], on=["client_id","product_family"], how="inner")
mr = (mc[(mc["month"]>=recent_start)&(mc["month"]<OBS_DATE)]
      .groupby(["client_id","product_family"], observed=True)
      .agg(recent_purchase_months=("had_purchase","sum"),
           recent_total_value=("monthly_value","sum")).reset_index())
mh = (mc[(mc["month"]>=hist_start)&(mc["month"]<hist_end)]
      .groupby(["client_id","product_family"], observed=True)
      .agg(hist_purchase_months=("had_purchase","sum"),
           hist_total_value=("monthly_value","sum")).reset_index())

cf = cand_C.merge(mr, on=["client_id","product_family"], how="left").merge(mh, on=["client_id","product_family"], how="left").fillna(0)
cf = cf[cf["hist_purchase_months"]>=2].copy()
cf["volume_drop_ratio"] = (
    np.maximum(0, cf["hist_total_value"]/12 - cf["recent_total_value"]/12)
    / (cf["hist_total_value"]/12 + 1e-9)
)
cf["frequency_drop_ratio"] = (
    np.maximum(0, cf["hist_purchase_months"]/12 - cf["recent_purchase_months"]/12)
    / (cf["hist_purchase_months"]/12 + 1e-9)
)
cf["pattern_deterioration_score"] = 0.5*cf["volume_drop_ratio"] + 0.5*cf["frequency_drop_ratio"]

def status_C(s):
    if s > 0.6: return "Likely Lost"
    if s > 0.4: return "At Risk"
    if s > 0.2: return "Early Warning"
    return None
cf["lost_status"] = cf["pattern_deterioration_score"].apply(status_C)
branch_C = cf[cf["lost_status"].notna()].copy()
branch_C["method"] = "historical_pattern"
branch_C["confidence_level"] = "medium"
branch_C["raw_score"] = branch_C["pattern_deterioration_score"]
print(f"  Branch C alerts: {len(branch_C):,}")

# Merge branches
keep_cols = ["client_id","product_family","product_family_biz","province",
             "lost_status","method","raw_score","confidence_level"]
def select(df):
    out = pd.DataFrame()
    for c in keep_cols:
        out[c] = df[c] if c in df.columns else np.nan
    return out

merged = pd.concat([select(branch_A), select(branch_B), select(branch_C)], ignore_index=True)
merged = merged.sort_values("raw_score", ascending=False) \
               .drop_duplicates(subset=["client_id","product_family"], keep="first") \
               .reset_index(drop=True)

# Value weighting (replicate production)
hist_12m_start = OBS_DATE - pd.DateOffset(months=12)
h12 = (monthly[(monthly["month"]>=hist_12m_start)&(monthly["month"]<OBS_DATE)]
       .groupby(["client_id","product_family"], observed=True)["monthly_value"]
       .sum().reset_index().rename(columns={"monthly_value":"hist_12m_value"}))
pot = (df_potential.groupby(["client_id","product_family_biz"])["potential_value"].sum().reset_index())
merged = merged.merge(h12, on=["client_id","product_family"], how="left")
merged = merged.merge(pot, on=["client_id","product_family_biz"], how="left")
merged["hist_12m_value"] = merged["hist_12m_value"].fillna(0)

def raw_value(r):
    p, h = r["potential_value"], r["hist_12m_value"]
    pv = pd.notna(p) and p > 0
    hv = pd.notna(h) and h > 0
    if pv and hv: return max(p, h)
    if pv: return p
    if hv: return h
    return 1.0
merged["raw_value"] = merged.apply(raw_value, axis=1)
log_v = np.log1p(merged["raw_value"].clip(lower=0))
denom = log_v.max() - log_v.min()
merged["value_factor"] = (log_v - log_v.min()) / (denom if denom > 1e-12 else 1.0)
merged["f2_priority_score"] = merged["raw_score"] * merged["value_factor"]

# Priority bins
q95 = merged["f2_priority_score"].quantile(0.95)
q80 = merged["f2_priority_score"].quantile(0.80)
q50 = merged["f2_priority_score"].quantile(0.50)
def prio(s):
    if s >= q95: return "P1 Critical"
    if s >= q80: return "P2 High"
    if s >= q50: return "P3 Medium"
    return "P4 Low"
merged["priority_level"] = merged["f2_priority_score"].apply(prio)

print(f"  Total backtest alerts: {len(merged):,}")

# ─────────────────────────────────────────────────────────────
# GROUND TRUTH LABELS (from future window)
# ─────────────────────────────────────────────────────────────
print("\n[GroundTruth] Building proxy labels from future 6 months …")

# Future purchase value per pair
future_value = (df_future.groupby(["client_id","product_family"], observed=True)["sales_value"]
                .sum().reset_index().rename(columns={"sales_value":"future_6m_value"}))
future_purch = (df_future.groupby(["client_id","product_family"], observed=True)["date"]
                .count().reset_index().rename(columns={"date":"future_purch_count"}))

# Historical 6m value (preceding obs_date)
hist_6m_start = OBS_DATE - pd.DateOffset(months=6)
hist_6m = (df_past[df_past["date"] >= hist_6m_start]
           .groupby(["client_id","product_family"], observed=True)["sales_value"]
           .sum().reset_index().rename(columns={"sales_value":"hist_6m_value"}))

eval_df = merged.merge(future_value, on=["client_id","product_family"], how="left")
eval_df = eval_df.merge(future_purch, on=["client_id","product_family"], how="left")
eval_df = eval_df.merge(hist_6m,      on=["client_id","product_family"], how="left")
eval_df["future_6m_value"]    = eval_df["future_6m_value"].fillna(0)
eval_df["future_purch_count"] = eval_df["future_purch_count"].fillna(0).astype(int)
eval_df["hist_6m_value"]      = eval_df["hist_6m_value"].fillna(0)

# Proxy label 1: strict — no purchase in future 6 months
eval_df["y_strict"]  = (eval_df["future_purch_count"] == 0).astype(int)

# Proxy label 2: lenient — future value drop > 60% vs historical 6m
# Only meaningful for pairs with hist_6m_value > 0; otherwise fall back to strict
def lenient_label(row):
    if row["hist_6m_value"] <= 0:
        return int(row["future_purch_count"] == 0)   # no historical → use strict
    return int(row["future_6m_value"] < 0.4 * row["hist_6m_value"])
eval_df["y_lenient"] = eval_df.apply(lenient_label, axis=1)

print(f"  y_strict positive rate:  {eval_df['y_strict'].mean()*100:.1f}%")
print(f"  y_lenient positive rate: {eval_df['y_lenient'].mean()*100:.1f}%")

# ─────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────
print("\n[Metrics] Computing …")

def topk_metrics(y, scores, k):
    if k > len(y): return None, None, None
    top = np.argsort(scores)[-k:]
    prec = float(y[top].mean())
    rec  = float(y[top].sum() / max(y.sum(), 1))
    base = float(y.mean())
    lift = prec / base if base > 0 else float("nan")
    return round(prec,4), round(rec,4), round(lift,4)

def compute_metrics(scores, y, name):
    auroc = roc_auc_score(y, scores)
    auprc = average_precision_score(y, (scores - scores.min())/(scores.max()-scores.min()+1e-10))
    m = {"label": name, "auroc": round(auroc,4), "auprc": round(auprc,4),
         "n_pos": int(y.sum()), "n_total": len(y), "base_rate": round(float(y.mean()),4)}
    for k in [50, 100, 200, 500, 1000]:
        r = topk_metrics(y, scores, k)
        if r[0] is not None:
            m[f"precision@{k}"] = r[0]
            m[f"recall@{k}"]    = r[1]
            m[f"lift@{k}"]      = r[2]
    return m

scores = eval_df["f2_priority_score"].values
y_str  = eval_df["y_strict"].values
y_len  = eval_df["y_lenient"].values

m_overall_strict  = compute_metrics(scores, y_str, "y_strict (no purchase 6m)")
m_overall_lenient = compute_metrics(scores, y_len, "y_lenient (>60% drop)")

# Branch-specific metrics
branch_metrics = {}
for branch_name, mask_fn in [
    ("Branch A (silence)",     lambda d: d["method"]=="silence_score"),
    ("Branch B (direct)",      lambda d: d["method"]=="direct"),
    ("Branch C (historical)",  lambda d: d["method"]=="historical_pattern"),
]:
    sub = eval_df[mask_fn(eval_df)]
    if len(sub) < 2 or sub["y_strict"].nunique() < 2:
        branch_metrics[branch_name] = {"n": len(sub), "note": "insufficient data"}
        continue
    branch_metrics[branch_name] = {
        "n_alerts": len(sub),
        "y_strict_rate": round(float(sub["y_strict"].mean()), 4),
        "auroc_strict":  round(roc_auc_score(sub["y_strict"], sub["f2_priority_score"]), 4),
        "auprc_strict":  round(average_precision_score(sub["y_strict"], sub["f2_priority_score"]), 4),
    }

# Hit rate by lost_status (sanity check)
hit_status = (eval_df.groupby("lost_status")
              .agg(n=("y_strict","size"),
                   strict_rate=("y_strict","mean"),
                   lenient_rate=("y_lenient","mean")).round(4).reset_index())

# Hit rate by priority_level
hit_priority = (eval_df.groupby("priority_level")
                .agg(n=("y_strict","size"),
                     strict_rate=("y_strict","mean"),
                     lenient_rate=("y_lenient","mean")).round(4).reset_index())

# ─────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────
out = {
    "observation_date": str(OBS_DATE.date()),
    "future_window_end": str(FUTURE_END.date()),
    "future_horizon_months": 6,
    "n_alerts_backtest": len(eval_df),
    "overall_strict":  m_overall_strict,
    "overall_lenient": m_overall_lenient,
    "by_branch":       branch_metrics,
    "hit_rate_by_lost_status": hit_status.to_dict("records"),
    "hit_rate_by_priority":    hit_priority.to_dict("records"),
}
(OUTPUT_DIR / "f2_backtest_metrics.json").write_text(json.dumps(out, indent=2))

# Markdown report
report = [
    "# F2 — Backtest Evaluation Report",
    "",
    "## Setup",
    f"- **Observation date:** {OBS_DATE.date()}",
    f"- **Future window:**    {(OBS_DATE+pd.Timedelta(days=1)).date()} → {FUTURE_END.date()} (6 months)",
    f"- **Backtest alerts:**  {len(eval_df):,}",
    f"- **Note:** f1_scope exclusion disabled in eval mode; F2 evaluated standalone",
    "",
    "## Proxy Labels",
    f"- `y_strict`:  no purchase in future 6 months (positive rate: {eval_df['y_strict'].mean()*100:.1f}%)",
    f"- `y_lenient`: future 6m value < 40% of historical 6m (positive rate: {eval_df['y_lenient'].mean()*100:.1f}%)",
    "",
    "## Overall Metrics",
    "",
    "### vs y_strict",
] + [f"- {k}: {v}" for k,v in m_overall_strict.items()] + [
    "",
    "### vs y_lenient",
] + [f"- {k}: {v}" for k,v in m_overall_lenient.items()] + [
    "",
    "## Branch-level (vs y_strict)",
    "",
    pd.DataFrame(branch_metrics).T.to_string(),
    "",
    "## Hit-rate by `lost_status`  (sanity check)",
    "Higher severity → higher actual lost rate is expected.",
    "",
    hit_status.to_string(index=False),
    "",
    "## Hit-rate by `priority_level`",
    "",
    hit_priority.to_string(index=False),
]
(OUTPUT_DIR / "f2_evaluation_report.md").write_text("\n".join(report))

# ─────────────────────────────────────────────────────────────
# CONSOLE SUMMARY
# ─────────────────────────────────────────────────────────────
print("\n" + "=" * 70)
print("F2 BACKTEST RESULTS")
print("=" * 70)
print(f"\nOverall (vs y_strict, no-purchase-6m, base rate {m_overall_strict['base_rate']*100:.1f}%):")
print(f"  AUROC:           {m_overall_strict['auroc']:.4f}")
print(f"  AUPRC:           {m_overall_strict['auprc']:.4f}")
print(f"  Precision@100:   {m_overall_strict.get('precision@100','N/A')}")
print(f"  Lift@100:        {m_overall_strict.get('lift@100','N/A')}")
print(f"  Precision@500:   {m_overall_strict.get('precision@500','N/A')}")
print(f"  Lift@500:        {m_overall_strict.get('lift@500','N/A')}")

print(f"\nOverall (vs y_lenient, >60%-drop, base rate {m_overall_lenient['base_rate']*100:.1f}%):")
print(f"  AUROC:           {m_overall_lenient['auroc']:.4f}")
print(f"  AUPRC:           {m_overall_lenient['auprc']:.4f}")
print(f"  Lift@100:        {m_overall_lenient.get('lift@100','N/A')}")

print("\nHit-rate by lost_status (vs y_strict):")
for _, r in hit_status.iterrows():
    print(f"  {r['lost_status']:<14}  n={int(r['n']):>5}   strict={r['strict_rate']:.3f}   lenient={r['lenient_rate']:.3f}")

print("\nHit-rate by priority_level (vs y_strict):")
for _, r in hit_priority.iterrows():
    print(f"  {r['priority_level']:<14}  n={int(r['n']):>5}   strict={r['strict_rate']:.3f}")

print(f"\n[F2-EVAL] Saved → {OUTPUT_DIR / 'f2_backtest_metrics.json'}")
print(f"[F2-EVAL] Saved → {OUTPUT_DIR / 'f2_evaluation_report.md'}")
