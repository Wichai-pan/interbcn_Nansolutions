"""
F4 — Commercial Operations Engine
Inibsa Smart Demand Signals

Merges F1, F2, F3 alerts into a unified action queue. Produces:
  * all_alerts.json / .parquet  → full ranked list
  * top_actions.json            → today's Top-5 with soft-penalty diversification
  * f4_diagnostics.md

This module ONLY merges and ranks. It does NOT generate natural-language
explanations or recommended actions — that belongs to the explanation layer.
"""
import json
import math
import random
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED); np.random.seed(SEED)

INPUT_F1 = Path("./output/stage2") / "f1_combined_alerts.parquet"
INPUT_F2 = Path("./output/f2")     / "f2_lost_customer_alerts.parquet"
INPUT_F3 = Path("./output/f3")     / "f3_capture_opportunity_alerts.parquet"
OUTPUT_DIR = Path("./output/f4")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TOP_N                = 5
SAME_MODULE_PENALTY  = 0.7
SAME_CLIENT_PENALTY  = 0.5

FAM2BIZ = {
    "Familia C1": "Anestesia",
    "Familia C2": "Bioseguridad",
    "Familia T1": "Biomateriales",
    "Familia T2": "Biomateriales",
}

print("=" * 70)
print("F4 — COMMERCIAL OPERATIONS ENGINE")
print("=" * 70)

# ─────────────────────────────────────────────────────────────
# UTILITIES
# ─────────────────────────────────────────────────────────────
def safe_load(path):
    if not path.exists():
        print(f"  [WARN] {path} does not exist — treating as empty")
        return None
    df = pd.read_parquet(path)
    if len(df) == 0:
        print(f"  [WARN] {path} is empty")
        return None
    return df

def to_jsonable(v):
    """Convert pandas/numpy NaN/NaT to None for JSON serialization."""
    if v is None: return None
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat() if not pd.isna(v) else None
    if isinstance(v, (np.integer,)):  return int(v)
    if isinstance(v, (np.floating,)):
        return None if (math.isnan(v) or math.isinf(v)) else float(v)
    if isinstance(v, (np.bool_,)):    return bool(v)
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else v
    if pd.isna(v):                    return None
    return v

def evidence_dict(row, fields):
    """Pick a subset of columns into a JSON-clean dict."""
    out = {}
    for f in fields:
        out[f] = to_jsonable(row.get(f))
    return out

# ─────────────────────────────────────────────────────────────
# STAGE 0 — LOAD & UNIFY SCHEMA
# ─────────────────────────────────────────────────────────────
print("\n[Stage 0] Loading inputs …")
f1_raw = safe_load(INPUT_F1)
f2_raw = safe_load(INPUT_F2)
f3_raw = safe_load(INPUT_F3)

n_f1_in = 0 if f1_raw is None else len(f1_raw)
n_f2_in = 0 if f2_raw is None else len(f2_raw)
n_f3_in = 0 if f3_raw is None else len(f3_raw)
print(f"  F1: {n_f1_in:,}  |  F2: {n_f2_in:,}  |  F3: {n_f3_in:,}")

scoring_date = pd.Timestamp.today().normalize()
print(f"  scoring_date (F4 run): {scoring_date.date()}")

# ── F1 unification ──────────────────────────────────────────
f1_dropped_after_biz = 0
if f1_raw is not None:
    f1 = f1_raw.copy()
    # Map product_family → product_family_biz if not already present/coherent
    if "product_family_biz" not in f1.columns:
        f1["product_family_biz"] = f1["product_family"].map(FAM2BIZ)
    # Collapse T1+T2 (not expected in F1 since F1 is commodities-only, but safe)
    n_before = len(f1)
    f1 = f1.sort_values("f1_final_score", ascending=False) \
           .drop_duplicates(subset=["client_id","product_family_biz"], keep="first") \
           .reset_index(drop=True)
    f1_dropped_after_biz = n_before - len(f1)

    f1["alert_id_f4"]    = ["F1-" + str(i+1).zfill(6) for i in range(len(f1))]
    f1["module"]         = "F1"
    f1["alert_type"]     = "Replenishment"
    f1["sub_type"]       = "Replenishment (Active)"   # overwritten to "Reactivation (Dormant)" in Layer 1
    f1["module_score"]   = f1["f1_final_score"]
    f1["module_priority_level"] = f1["combined_priority"] if "combined_priority" in f1.columns else f1["priority_level"]

    # Our method fields (GRU + baseline)
    f1_evidence_fields = [
        "days_since_last_purchase", "expected_interval", "delay",
        "seasonal_time_score", "reorder_probability", "replenishment_score",
    ]
    # Teammate statistical fields (stat_* prefix) — merged in after TM enrichment block
    f1_stat_fields = [
        "stat_avg_interval_days", "stat_grading_eur", "stat_f_in_fixed",
        "stat_n_active_products", "stat_behavioral_status", "stat_cluster",
    ]
    f1_evidence_fields = f1_evidence_fields + f1_stat_fields
    f1["evidence"] = f1.apply(lambda r: evidence_dict(r, f1_evidence_fields), axis=1)

    f1_unified = f1[[
        "alert_id_f4", "client_id", "product_family_biz", "province", "segment_code",
        "module", "alert_type", "sub_type", "module_score", "module_priority_level",
        "confidence_level", "evidence",
    ]].rename(columns={"alert_id_f4": "alert_id"})
else:
    f1_unified = pd.DataFrame()

print(f"  F1 unified: {len(f1_unified):,} (collapsed T1+T2 duplicates: {f1_dropped_after_biz})")

# ── F2 unification ──────────────────────────────────────────
if f2_raw is not None:
    f2 = f2_raw.copy()
    if "product_family_biz" not in f2.columns:
        f2["product_family_biz"] = f2["product_family"].map(FAM2BIZ)
    # Same client × biz family may appear via T1+T2 merging — keep highest priority
    sev_map = {"Likely Lost": 3, "At Risk": 2, "Early Warning": 1}
    f2["_sev"] = f2["lost_status"].map(sev_map).fillna(0)
    n_before = len(f2)
    f2 = f2.sort_values(["_sev", "f2_priority_score"], ascending=False) \
           .drop_duplicates(subset=["client_id","product_family_biz"], keep="first") \
           .reset_index(drop=True)
    f2_dropped_after_biz = n_before - len(f2)
    f2.drop(columns=["_sev"], inplace=True)

    # Rename existing F2 alert_id to keep traceability, but also generate stable F4-side id
    f2["module"]                = "F2"
    f2["alert_type"]             = "Lost Customer Risk"
    f2["sub_type"]               = f2["lost_status"]
    f2["module_score"]           = f2["f2_priority_score"]
    f2["module_priority_level"]  = f2["priority_level"]

    f2_evidence_fields = [
        "method", "lost_status", "days_since_last_purchase",
        "silence_score", "threshold_used",
        "volume_drop_ratio", "frequency_drop_ratio",
        "hist_avg_monthly_value", "recent_avg_monthly_value",
    ]
    f2["evidence"] = f2.apply(lambda r: evidence_dict(r, f2_evidence_fields), axis=1)

    f2_unified = f2[[
        "alert_id", "client_id", "product_family_biz", "province", "segment_code",
        "module", "alert_type", "sub_type", "module_score", "module_priority_level",
        "confidence_level", "evidence",
    ]]
else:
    f2_unified = pd.DataFrame()
    f2_dropped_after_biz = 0

print(f"  F2 unified: {len(f2_unified):,}")

# ── F3 unification ──────────────────────────────────────────
if f3_raw is not None:
    f3 = f3_raw.copy()
    # F3 already at product_family_biz granularity — no collapse needed
    f3["module"]                = "F3"
    f3["alert_type"]             = "Capture Opportunity"
    f3["sub_type"]               = f3["opportunity_type"]
    f3["module_score"]           = f3["f3_priority_score"]
    f3["module_priority_level"]  = f3["priority_level"]

    f3_evidence_fields = [
        "opportunity_type", "is_cold_start",
        "potential_value", "observed_value_12m",
        "utilization_ratio", "potential_gap",
        "capture_window_flag", "lost_status_f2",
    ]
    f3["evidence"] = f3.apply(lambda r: evidence_dict(r, f3_evidence_fields), axis=1)

    f3_unified = f3[[
        "alert_id", "client_id", "product_family_biz", "province", "segment_code",
        "module", "alert_type", "sub_type", "module_score", "module_priority_level",
        "confidence_level", "evidence",
    ]]
else:
    f3_unified = pd.DataFrame()

print(f"  F3 unified: {len(f3_unified):,}")

# ═══════════════════════════════════════════════════════════════
# TEAMMATE STATISTICAL ENRICHMENT (互补信号，不影响主评分)
# Source : teamate/Final Gradation Results.csv
# Method : KMeans clustering + dynamic 180-day threshold
#          + Grading = F_in × Potencial_H
# Granularity: client × product  →  aggregated to client × family
# Variables  : tm_df (raw), tm_agg (aggregated), stat_* (evidence fields)
# ═══════════════════════════════════════════════════════════════

TM_CSV_PATH = Path("./teamate/Final Gradation Results.csv")

TM_CATEGORY_MAP = {
    "Categoria C1": "Anestesia",
    "Categoria C2": "Bioseguridad",
    "Categoria T1": "Biomateriales",
}

TM_STATUS_SEVERITY = {
    "Lost Customer":                     4,
    "Retention (Seasonal Inactive)":     3,
    "Retention (1st historic purchase)": 2,
    "Out-of-period / Holiday behavior":  1,
    "Habitual":                          0,
}

TM_MIN_RELIABLE_INTERVAL = 7
TM_F_IN_CAP              = 10.0


def _tm_fix_f_in(mean_val, mean_gr_val, avg_delta_val, current_delta):
    indiv = None
    if pd.notna(mean_val) and float(mean_val) >= TM_MIN_RELIABLE_INTERVAL:
        indiv = float(mean_val)
    elif pd.notna(avg_delta_val) and float(avg_delta_val) >= TM_MIN_RELIABLE_INTERVAL:
        indiv = float(avg_delta_val)
    grp = float(mean_gr_val) if (pd.notna(mean_gr_val) and
                                  float(mean_gr_val) >= TM_MIN_RELIABLE_INTERVAL) else None
    if indiv is None and grp is None:
        return None
    t_indiv = float(current_delta) / indiv if indiv else 0.0
    t_group = float(current_delta) / grp   if grp   else 0.0
    return round(min(t_indiv + t_group, TM_F_IN_CAP), 2)


def _tm_most_severe_status(status_series):
    sev = status_series.map(TM_STATUS_SEVERITY).fillna(-1)
    return status_series.iloc[sev.values.argmax()]


if TM_CSV_PATH.exists():
    print("\n[Stat Enrichment] Loading teammate data …")

    tm_df = pd.read_csv(TM_CSV_PATH)
    tm_df = tm_df.rename(columns={"Id. Cliente": "client_id"})
    tm_df["client_id"] = tm_df["client_id"].astype(str).str.strip()

    tm_df["product_family_biz"] = tm_df["Category"].map(TM_CATEGORY_MAP)
    tm_before = len(tm_df)
    tm_df = tm_df.dropna(subset=["product_family_biz"])
    print(f"  rows after category mapping: {len(tm_df):,} / {tm_before:,}")

    tm_df["_stat_f_in_fixed"] = tm_df.apply(
        lambda r: _tm_fix_f_in(
            r.get("mean"), r.get("mean_gr"),
            r.get("avg_delta_t_customer_product"),
            r.get("current_delta_t", 0)
        ),
        axis=1
    )

    # ── Pre-aggregation: identify client×family groups whose most-severe
    #    product status is "Lost Customer" and evict them from F1 before ranking.
    #    Uses the same _tm_most_severe_status logic as tm_agg so the filter is
    #    consistent with what stat_behavioral_status will show in the evidence.
    #    (tm_agg still uses the full tm_df so stat_behavioral_status is accurate)
    group_worst = (
        tm_df.groupby(["client_id", "product_family_biz"])["Status"]
        .apply(_tm_most_severe_status)
    )
    fully_lost_keys = set(group_worst[group_worst == "Lost Customer"].index.tolist())

    if fully_lost_keys and len(f1_unified) > 0:
        f1_unified["client_id"] = f1_unified["client_id"].astype(str).str.strip()
        lost_mi   = pd.MultiIndex.from_tuples(fully_lost_keys)
        f1_mi     = pd.MultiIndex.from_arrays(
            [f1_unified["client_id"], f1_unified["product_family_biz"]]
        )
        lost_mask = f1_mi.isin(lost_mi)
        n_removed = int(lost_mask.sum())
        f1_unified = f1_unified[~lost_mask].reset_index(drop=True)
        print(f"  F1 alerts removed (all products Lost Customer per stat method): {n_removed:,}")

    tm_agg = (
        tm_df
        .groupby(["client_id", "product_family_biz"], as_index=False)
        .agg(
            stat_avg_interval_days=(
                "avg_delta_t_customer_product",
                lambda x: round(x[x >= TM_MIN_RELIABLE_INTERVAL].mean(), 1)
                          if (x >= TM_MIN_RELIABLE_INTERVAL).any() else None
            ),
            stat_grading_eur=("Grading", lambda x: round(x.sum(), 0)),
            stat_f_in_fixed=(
                "_stat_f_in_fixed",
                lambda x: round(x.dropna().max(), 2) if x.notna().any() else None
            ),
            stat_n_active_products=(
                "Status",
                lambda x: int((x != "Lost Customer").sum())
            ),
            stat_behavioral_status=("Status", _tm_most_severe_status),
            stat_cluster=(
                "Cluster",
                lambda x: int(x.mode().iloc[0]) if len(x) > 0 else None
            ),
        )
    )

    n_tm = len(tm_agg)
    print(f"  tm_agg rows (client×family): {n_tm:,}")

    if len(f1_unified) > 0:
        f1_unified["client_id"] = f1_unified["client_id"].astype(str).str.strip()
        f1_unified = f1_unified.merge(
            tm_agg, on=["client_id", "product_family_biz"], how="left"
        )
        n_matched = f1_unified["stat_avg_interval_days"].notna().sum()
        print(f"  F1 alerts matched with stat data: {n_matched:,} / {len(f1_unified):,}")

        # Write stat_* values back into the evidence dict (built before the join)
        _stat_cols = [c for c in f1_unified.columns if c.startswith("stat_")]
        def _enrich_evidence(row):
            ev = dict(row["evidence"]) if isinstance(row["evidence"], dict) else {}
            for col in _stat_cols:
                val = row[col]
                ev[col] = to_jsonable(val)
            return ev
        f1_unified["evidence"] = f1_unified.apply(_enrich_evidence, axis=1)
    else:
        print("  f1_unified is empty — skipping join")

else:
    print(f"\n[Stat Enrichment] {TM_CSV_PATH} not found — skipping")
    for _col in ["stat_avg_interval_days", "stat_grading_eur", "stat_f_in_fixed",
                 "stat_n_active_products", "stat_behavioral_status", "stat_cluster"]:
        if len(f1_unified) > 0:
            f1_unified[_col] = None

# ═══════════════════════════════════════════════════════════════
# END TEAMMATE STATISTICAL ENRICHMENT
# ═══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────
# STAGE 1 — IN-MODULE NORMALIZATION
# ─────────────────────────────────────────────────────────────
print("\n[Stage 1] In-module rank-percentile …")

def add_rank_pct(df):
    if len(df) == 0:
        df["module_rank_pct"] = []
        return df
    if len(df) == 1:
        df["module_rank_pct"] = 1.0
        return df
    df = df.copy()
    df["module_rank_pct"] = df["module_score"].rank(pct=True, method="average")
    return df

# ── Layer 1: F1 dormancy penalty ─────────────────────────────
LOST_MULTIPLIER     = 3.0
LOST_FLOOR_DAYS     = 90
LOST_HARD_CAP       = 730
DORMANT_SCORE_SCALE = 0.10

if len(f1_unified) > 0 and "evidence" in f1_unified.columns:
    def _get_expected_interval(ev):
        if isinstance(ev, dict):
            v = ev.get("expected_interval")
            try: return float(v) if v is not None else np.nan
            except: return np.nan
        return np.nan

    f1_unified["_expected_interval"] = f1_unified["evidence"].apply(_get_expected_interval)
    f1_unified["_days_since"] = pd.to_numeric(
        f1_unified["evidence"].apply(
            lambda ev: ev.get("days_since_last_purchase") if isinstance(ev, dict) else None
        ), errors="coerce"
    )
    f1_unified["_lost_threshold"] = f1_unified["_expected_interval"].apply(
        lambda ei: min(max(ei * LOST_MULTIPLIER, LOST_FLOOR_DAYS), LOST_HARD_CAP)
        if (not pd.isna(ei) and ei > 0) else LOST_HARD_CAP
    )
    dormant_mask = (
        f1_unified["_days_since"].notna() &
        (f1_unified["_days_since"] > f1_unified["_lost_threshold"])
    )
    n_dormant = int(dormant_mask.sum())
    f1_unified.loc[dormant_mask, "module_score"] *= DORMANT_SCORE_SCALE
    f1_unified.loc[dormant_mask, "sub_type"] = "Reactivation (Dormant)"
    for idx in f1_unified[dormant_mask].index:
        ev = f1_unified.at[idx, "evidence"]
        if isinstance(ev, dict):
            ev["is_dormant"] = True
            ev["lost_threshold_days"] = int(f1_unified.at[idx, "_lost_threshold"])
    f1_unified.drop(columns=["_expected_interval", "_days_since", "_lost_threshold"], inplace=True)
    print(f"  [Layer 1] F1 dormant clients capped: {n_dormant:,} (module_score ×{DORMANT_SCORE_SCALE})")
else:
    n_dormant = 0
    print("  [Layer 1] F1 dormancy check skipped (no data or missing columns)")
# ─────────────────────────────────────────────────────────────

f1_unified = add_rank_pct(f1_unified)
f2_unified = add_rank_pct(f2_unified)

# ── Layer 2: F3 sub_type weighting ───────────────────────────
F3_WEIGHTS = {
    "New Account Opportunity":         0.65,
    "Mild Underutilization":           0.80,
    "Moderate Underutilization":       0.90,
    "High Potential Underutilization": 1.00,
}
DEFAULT_F3_WEIGHT = 0.75

if len(f3_unified) > 0 and "sub_type" in f3_unified.columns:
    f3_weight_applied = {}
    for opp_type, weight in F3_WEIGHTS.items():
        mask = f3_unified["sub_type"] == opp_type
        n = int(mask.sum())
        if n > 0:
            f3_unified.loc[mask, "module_score"] *= weight
            f3_weight_applied[opp_type] = (n, weight)
    matched_mask = f3_unified["sub_type"].isin(F3_WEIGHTS.keys())
    n_default = int((~matched_mask).sum())
    if n_default > 0:
        f3_unified.loc[~matched_mask, "module_score"] *= DEFAULT_F3_WEIGHT
    print(f"  [Layer 2] F3 weights applied:")
    for k, (n, w) in f3_weight_applied.items():
        print(f"    {k}: {n:,} rows × {w}")
    if n_default > 0:
        print(f"    (default ×{DEFAULT_F3_WEIGHT}): {n_default:,} rows")
else:
    n_default = 0
    print("  [Layer 2] F3 weighting skipped (no data or missing columns)")
# ─────────────────────────────────────────────────────────────

f3_unified = add_rank_pct(f3_unified)

# ─────────────────────────────────────────────────────────────
# STAGE 2 — CONCAT
# ─────────────────────────────────────────────────────────────
print("\n[Stage 2] Concat all modules …")
parts = [d for d in [f1_unified, f2_unified, f3_unified] if len(d) > 0]
if not parts:
    print("\n[F4-WARN] All three modules are empty. Writing empty outputs.")
    df_unified = pd.DataFrame(columns=[
        "alert_id","client_id","product_family_biz","province","segment_code",
        "module","alert_type","sub_type","module_score","module_priority_level",
        "confidence_level","evidence","module_rank_pct","unified_score",
    ])
else:
    df_unified = pd.concat(parts, ignore_index=True)
df_unified["unified_score"] = df_unified["module_rank_pct"] if len(df_unified) > 0 else []
print(f"  unified rows (before dedup): {len(df_unified):,}")

# ─────────────────────────────────────────────────────────────
# STAGE 3 — CROSS-MODULE LINKED SIGNALS + DEDUP
# ─────────────────────────────────────────────────────────────
print("\n[Stage 3] Cross-module linked_signals + dedup …")

CROSS_MODULE_BONUS = 0.04

dedup_log = []
overlap_pair_counts = {"F1∩F2": 0, "F1∩F3": 0, "F2∩F3": 0, "F1∩F2∩F3": 0}

if len(df_unified) > 0:
    # ── Step A: (client_id, product_family_biz) → alert entries ──
    overlap_map = {}
    for _, row in df_unified.iterrows():
        key = (row["client_id"], row["product_family_biz"])
        overlap_map.setdefault(key, []).append({
            "alert_id": row["alert_id"],
            "module":   row["module"],
            "score":    row["unified_score"],
        })

    # ── Step B: linked_signals + cross-module bonus ──
    linked_signals_map = {}
    bonus_map          = {}

    for key, entries in overlap_map.items():
        if len(entries) < 2:
            continue
        modules = tuple(sorted({e["module"] for e in entries}))
        if set(modules) == {"F1", "F2", "F3"}:
            overlap_pair_counts["F1∩F2∩F3"] += 1
        elif set(modules) == {"F1", "F2"}:
            overlap_pair_counts["F1∩F2"] += 1
        elif set(modules) == {"F1", "F3"}:
            overlap_pair_counts["F1∩F3"] += 1
        elif set(modules) == {"F2", "F3"}:
            overlap_pair_counts["F2∩F3"] += 1

        for e in entries:
            other_ids = [x["alert_id"] for x in entries if x["alert_id"] != e["alert_id"]]
            linked_signals_map[e["alert_id"]] = other_ids
            bonus_map[e["alert_id"]] = len(other_ids) * CROSS_MODULE_BONUS

    # ── Step C: write back ──
    df_unified["linked_signals"] = df_unified["alert_id"].map(
        lambda aid: linked_signals_map.get(aid, [])
    )
    df_unified["unified_score"] = df_unified.apply(
        lambda r: min(r["unified_score"] + bonus_map.get(r["alert_id"], 0.0), 1.05),
        axis=1
    )

    n_with_links = int((df_unified["linked_signals"].apply(len) > 0).sum())
    print(f"  alerts with linked_signals: {n_with_links:,}")
    print(f"  overlap pair counts: {overlap_pair_counts}")

    # ── Step D: dedup, keep highest unified_score per key ──
    n_before = len(df_unified)
    df_unified = df_unified.sort_values("unified_score", ascending=False).reset_index(drop=True)

    seen = set()
    keep_mask = np.zeros(len(df_unified), dtype=bool)
    drops = []
    for i, row in df_unified.iterrows():
        key = (row["client_id"], row["product_family_biz"])
        if key in seen:
            drops.append({
                "client_id":           row["client_id"],
                "product_family_biz":  row["product_family_biz"],
                "module_dropped":      row["module"],
                "sub_type_dropped":    row["sub_type"],
                "linked_preserved_in": linked_signals_map.get(row["alert_id"], []),
            })
            continue
        seen.add(key)
        keep_mask[i] = True

    df_unified = df_unified[keep_mask].reset_index(drop=True)
    n_dedup_dropped = n_before - len(df_unified)
    dedup_log = drops
    print(f"  dropped on dedup: {n_dedup_dropped:,} (alert_ids preserved in linked_signals)")
else:
    n_dedup_dropped = 0

# ─────────────────────────────────────────────────────────────
# STAGE 4 — GLOBAL PRIORITY & ALL_ALERTS
# ─────────────────────────────────────────────────────────────
print("\n[Stage 4] Global priority binning …")

if len(df_unified) > 0:
    df_unified = df_unified.sort_values("unified_score", ascending=False).reset_index(drop=True)
    df_unified["rank_global"] = np.arange(1, len(df_unified)+1)

    q95 = df_unified["unified_score"].quantile(0.95)
    q80 = df_unified["unified_score"].quantile(0.80)
    q50 = df_unified["unified_score"].quantile(0.50)
    def prio(s):
        if s >= q95: return "P1 Critical"
        if s >= q80: return "P2 High"
        if s >= q50: return "P3 Medium"
        return "P4 Low"
    df_unified["priority_level"] = df_unified["unified_score"].apply(prio)

    # Tie-break note
    if df_unified["unified_score"].nunique() == 1:
        print("  [WARN] all unified_scores identical — falling back to alert_id sort")
        df_unified = df_unified.sort_values("alert_id").reset_index(drop=True)
        df_unified["rank_global"] = np.arange(1, len(df_unified)+1)

    if "linked_signals" not in df_unified.columns:
        df_unified["linked_signals"] = [[] for _ in range(len(df_unified))]
    df_unified["status"] = "Pending"
else:
    df_unified["rank_global"]    = []
    df_unified["priority_level"] = []
    df_unified["linked_signals"] = []
    df_unified["status"]         = []

# Save parquet (drop linked_signals which is empty list — pandas handles it)
df_unified.to_parquet(OUTPUT_DIR / "all_alerts.parquet", index=False)

# Build JSON
def row_to_json(r):
    return {
        "alert_id":          to_jsonable(r["alert_id"]),
        "rank_global":       int(r["rank_global"]),
        "client_id":         to_jsonable(r["client_id"]),
        "product_family_biz":to_jsonable(r["product_family_biz"]),
        "province":          to_jsonable(r["province"]),
        "segment_code":      to_jsonable(r["segment_code"]),
        "module":            r["module"],
        "alert_type":        r["alert_type"],
        "sub_type":          to_jsonable(r["sub_type"]),
        "unified_score":     to_jsonable(r["unified_score"]),
        "module_score":      to_jsonable(r["module_score"]),
        "module_rank_pct":   to_jsonable(r["module_rank_pct"]),
        "priority_level":    r["priority_level"],
        "confidence_level":  to_jsonable(r["confidence_level"]),
        "evidence":          r["evidence"] if isinstance(r["evidence"], dict) else {},
        "linked_signals":    r["linked_signals"] if isinstance(r.get("linked_signals"), list) else [],
        "status":            "Pending",
    }

all_alerts_json = {
    "scoring_date": str(scoring_date.date()),
    "n_total":      len(df_unified),
    "alerts":       [row_to_json(r) for _, r in df_unified.iterrows()],
}
all_alerts_path = OUTPUT_DIR / "all_alerts.json"
all_alerts_path.write_text(json.dumps(all_alerts_json, ensure_ascii=False, indent=2))

# ─────────────────────────────────────────────────────────────
# STAGE 5 — TOP-N WITH SOFT PENALTY
# ─────────────────────────────────────────────────────────────
print(f"\n[Stage 5] Top-{TOP_N} soft-penalty selection …")

selected_records = []
selection_log = []

if len(df_unified) > 0:
    # Working copy
    work = df_unified.copy()
    work["adjusted_score"] = work["unified_score"].astype(float)
    # Track penalty history per row
    work["_penalty_history"] = [[] for _ in range(len(work))]
    work = work.reset_index(drop=True)

    n_to_pick = min(TOP_N, len(work))
    for round_i in range(1, n_to_pick + 1):
        # Pick highest adjusted_score
        idx = int(work["adjusted_score"].idxmax())
        chosen = work.loc[idx].to_dict()
        chosen_at_pick = float(chosen["adjusted_score"])

        record = {
            "rank_top":         round_i,
            "alert_id":         chosen["alert_id"],
            "client_id":        chosen["client_id"],
            "product_family_biz": chosen["product_family_biz"],
            "module":           chosen["module"],
            "sub_type":         chosen["sub_type"],
            "unified_score":    chosen["unified_score"],
            "adjusted_score_at_selection": chosen_at_pick,
            "penalties_applied_so_far":    chosen.get("_penalty_history", []),
            "row_payload":      chosen,
        }
        selected_records.append(record)
        selection_log.append({
            "round": round_i,
            "picked_alert_id":            chosen["alert_id"],
            "picked_module":              chosen["module"],
            "picked_client_id":           chosen["client_id"],
            "picked_unified_score":       chosen["unified_score"],
            "picked_adjusted_score":      chosen_at_pick,
            "penalties_picked_had":       chosen.get("_penalty_history", []),
        })

        # Drop the chosen row
        work = work.drop(index=idx).reset_index(drop=True)

        # Apply cumulative penalties to remaining
        if len(work) == 0: break
        same_module_mask = (work["module"] == chosen["module"]).values
        same_client_mask = (work["client_id"] == chosen["client_id"]).values

        for j in range(len(work)):
            penalty = 1.0
            tags = list(work.at[j, "_penalty_history"])
            if same_module_mask[j]:
                penalty *= SAME_MODULE_PENALTY
                tags.append({"round": round_i, "reason": "same_module",
                             "vs_alert_id": chosen["alert_id"], "factor": SAME_MODULE_PENALTY})
            if same_client_mask[j]:
                penalty *= SAME_CLIENT_PENALTY
                tags.append({"round": round_i, "reason": "same_client",
                             "vs_alert_id": chosen["alert_id"], "factor": SAME_CLIENT_PENALTY})
            if penalty < 1.0:
                work.at[j, "adjusted_score"] = float(work.at[j, "adjusted_score"]) * penalty
                work.at[j, "_penalty_history"] = tags
print(f"  picked: {len(selected_records)}")

# ─────────────────────────────────────────────────────────────
# STAGE 6 — TOP_ACTIONS JSON
# ─────────────────────────────────────────────────────────────
print("\n[Stage 6] Building top_actions.json …")

top_actions_list = []
for rec in selected_records:
    base = row_to_json(rec["row_payload"])
    base.update({
        "rank_top":         rec["rank_top"],
        "adjusted_score":   to_jsonable(rec["adjusted_score_at_selection"]),
        "selection_reason": {
            "raw_score":        to_jsonable(rec["unified_score"]),
            "adjusted_score":   to_jsonable(rec["adjusted_score_at_selection"]),
            "penalties_applied":[
                {"round": p["round"], "reason": p["reason"],
                 "vs_alert_id": p["vs_alert_id"], "factor": p["factor"]}
                for p in rec["penalties_applied_so_far"]
            ],
        },
    })
    top_actions_list.append(base)

top_actions_json = {
    "scoring_date":     str(scoring_date.date()),
    "top_n":            TOP_N,
    "selection_params": {
        "same_module_penalty": SAME_MODULE_PENALTY,
        "same_client_penalty": SAME_CLIENT_PENALTY,
    },
    "actions": top_actions_list,
}
top_actions_path = OUTPUT_DIR / "top_actions.json"
top_actions_path.write_text(json.dumps(top_actions_json, ensure_ascii=False, indent=2))

# ─────────────────────────────────────────────────────────────
# STAGE 7 — DIAGNOSTICS
# ─────────────────────────────────────────────────────────────
print("\n[Stage 7] Diagnostics …")

n_p1 = (df_unified["priority_level"]=="P1 Critical").sum() if len(df_unified) else 0
n_p2 = (df_unified["priority_level"]=="P2 High").sum()     if len(df_unified) else 0
n_p3 = (df_unified["priority_level"]=="P3 Medium").sum()   if len(df_unified) else 0
n_p4 = (df_unified["priority_level"]=="P4 Low").sum()      if len(df_unified) else 0

top_n_module_counts = pd.Series([r["module"] for r in selected_records]).value_counts().to_dict()
t1 = top_n_module_counts.get("F1", 0)
t2 = top_n_module_counts.get("F2", 0)
t3 = top_n_module_counts.get("F3", 0)
unique_clients_top = len({r["client_id"] for r in selected_records})

# Module composition in global Top-100
if len(df_unified) > 0:
    top100_module = df_unified.head(min(100, len(df_unified)))["module"].value_counts().to_dict()
else:
    top100_module = {}

empty_modules = [m for m, n in [("F1", n_f1_in), ("F2", n_f2_in), ("F3", n_f3_in)] if n == 0]

report = [
    "# F4 — Commercial Operations Engine Diagnostics",
    "",
    f"**Scoring date:** {scoring_date.date()}",
    "",
    "## Inputs",
    f"- F1 alerts (input): {n_f1_in:,}",
    f"- F2 alerts (input): {n_f2_in:,}",
    f"- F3 alerts (input): {n_f3_in:,}",
] + ([f"- **Empty modules:** {empty_modules}"] if empty_modules else []) + [
    "",
    "## Schema unification",
    f"- F1 collapsed (T1+T2 → Biomateriales) duplicates dropped: {f1_dropped_after_biz}",
    f"- F2 collapsed (T1+T2) duplicates dropped: {f2_dropped_after_biz}",
    "",
    "## Layer modifications applied",
    f"- Layer 1 (F1 dormancy): LOST_MULTIPLIER={LOST_MULTIPLIER}, HARD_CAP={LOST_HARD_CAP}d, SCORE_SCALE={DORMANT_SCORE_SCALE}",
    f"- Layer 2 (F3 weights): cold_start={F3_WEIGHTS['New Account Opportunity']}, "
    f"mild={F3_WEIGHTS['Mild Underutilization']}, "
    f"moderate={F3_WEIGHTS['Moderate Underutilization']}, "
    f"high={F3_WEIGHTS['High Potential Underutilization']}",
    f"- Layer 3 (linked_signals): CROSS_MODULE_BONUS={CROSS_MODULE_BONUS} per link",
    "",
    "## Cross-module dedup",
    f"- Rows dropped: {n_dedup_dropped:,}",
    "- Module overlap pair counts (within shared client × product_family_biz):",
] + [f"  - {k}: {v:,}" for k, v in overlap_pair_counts.items()] + [
    "",
    "## Global priority distribution",
    f"- P1 Critical: {n_p1:,}",
    f"- P2 High:     {n_p2:,}",
    f"- P3 Medium:   {n_p3:,}",
    f"- P4 Low:      {n_p4:,}",
    f"- **Total:**   {len(df_unified):,}",
    "",
    "## Module share in global Top-100",
] + [f"- {m}: {n:,}" for m, n in top100_module.items()] + [
    "",
    "## Top-5 module distribution",
    f"- F1: {t1}  |  F2: {t2}  |  F3: {t3}",
    f"- Unique clients in Top-5: {unique_clients_top}",
    "",
    "## Top-5 selection log",
    "",
    "| Round | Alert | Module | Client | unified_score | adjusted_score_at_pick | penalties_carried |",
    "|---|---|---|---|---|---|---|",
] + [
    f"| {l['round']} | {l['picked_alert_id']} | {l['picked_module']} | "
    f"{l['picked_client_id']} | {l['picked_unified_score']:.4f} | "
    f"{l['picked_adjusted_score']:.4f} | "
    f"{len(l['penalties_picked_had'])} |"
    for l in selection_log
] + [
    "",
    "## Robustness notes",
    f"- evidence dict NaN → null: handled",
    f"- unified_score all-identical fallback: {'TRIGGERED' if (len(df_unified)>0 and df_unified['unified_score'].nunique()==1) else 'no'}",
    f"- Top-N short of {TOP_N}: {'YES' if len(selected_records) < TOP_N else 'no'} (got {len(selected_records)})",
]

(OUTPUT_DIR / "f4_diagnostics.md").write_text("\n".join(report))

# ─────────────────────────────────────────────────────────────
# RUN-END LOG
# ─────────────────────────────────────────────────────────────
all_alerts_size_kb = round(all_alerts_path.stat().st_size / 1024, 1)

print()
print(f"[F4] Inputs:")
print(f"     F1 alerts: {n_f1_in}")
print(f"     F2 alerts: {n_f2_in}")
print(f"     F3 alerts: {n_f3_in}")
print(f"[F4] Unified after dedup: {len(df_unified)}")
print(f"[F4] Cross-module overlap removed: {n_dedup_dropped}")
print(f"[F4] Global priority distribution:")
print(f"     P1 / P2 / P3 / P4 = {n_p1} / {n_p2} / {n_p3} / {n_p4}")
print(f"[F4] Top {TOP_N} module distribution: F1={t1}, F2={t2}, F3={t3}")
print(f"[F4] Top {TOP_N} unique clients: {unique_clients_top}")
print(f"[F4] Saved → {OUTPUT_DIR / 'all_alerts.parquet'}")
print(f"[F4] Saved → {OUTPUT_DIR / 'all_alerts.json'} ({all_alerts_size_kb} KB)")
print(f"[F4] Saved → {OUTPUT_DIR / 'top_actions.json'}")
print(f"[F4] Saved → {OUTPUT_DIR / 'f4_diagnostics.md'}")
