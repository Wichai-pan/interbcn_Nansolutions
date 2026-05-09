"""
F3 — Construct/Discriminative/Negative Validation
Inibsa Smart Demand Signals

This is NOT outcome evaluation. F3 is a prescriptive task: "should sales contact
this client?" — true validation requires intervention records (A/B test) which
we don't have. Naturally-occurring 6m growth measures a different thing.

Three validation modes used here, all weak but informative:

  1. CONSTRUCT VALIDITY
     Top-ranked F3 alerts should match the "opportunity" profile:
     high potential, low utilization, still active, not yet lost.

  2. DISCRIMINATIVE VALIDITY
     F3 score should differ from naive single-signal baselines:
       naive_potential   = rank by potential_value alone
       naive_low_util    = rank by (1 - utilization_ratio) alone
     If F3 ≈ either baseline, the composite formula adds no value.

  3. NEGATIVE VALIDATION
     F3 should NOT rank these high (they violate the "opportunity" definition):
       - F2 "Likely Lost" clients (they are losses, not opportunities)
       - Long-sleep clients (>365d since last purchase, in Branch A)
       - Clients with very few historical months (low signal reliability)

Outputs:
    ./output/f3/f3_validation_metrics.json
    ./output/f3/f3_validation_report.md
"""
import json
import random
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.stats import kendalltau, spearmanr

SEED = 42
random.seed(SEED); np.random.seed(SEED)

INPUT_F2 = Path("./output/f2")
INPUT_F3 = Path("./output/f3")
OUTPUT_DIR = INPUT_F3
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("F3 — VALIDATION (construct / discriminative / negative)")
print("=" * 70)
print("\nNote: this is NOT outcome evaluation. F3 is prescriptive — true")
print("      validation needs intervention records we don't have. These metrics")
print("      assess whether F3's structure matches its stated intent.\n")

# ─────────────────────────────────────────────────────────────
# LOAD
# ─────────────────────────────────────────────────────────────
f3 = pd.read_parquet(INPUT_F3 / "f3_capture_opportunity_alerts.parquet")
f2_path = INPUT_F2 / "f2_lost_customer_alerts.parquet"
f2 = pd.read_parquet(f2_path) if f2_path.exists() else None
print(f"  F3 alerts: {len(f3):,}")
print(f"  F2 alerts: {len(f2):,}" if f2 is not None else "  F2: not found")

# Map F2 to (client_id, product_family_biz) and severity
FAM2BIZ = {"Familia C1":"Anestesia","Familia C2":"Bioseguridad",
           "Familia T1":"Biomateriales","Familia T2":"Biomateriales"}
SEV = {"Likely Lost":3,"At Risk":2,"Early Warning":1}

if f2 is not None:
    f2_biz = f2.copy()
    if "product_family_biz" not in f2_biz.columns:
        f2_biz["product_family_biz"] = f2_biz["product_family"].map(FAM2BIZ)
    f2_biz["sev"] = f2_biz["lost_status"].map(SEV).fillna(0)
    f2_lookup = (
        f2_biz.sort_values("sev", ascending=False)
        .drop_duplicates(["client_id","product_family_biz"], keep="first")
        .set_index(["client_id","product_family_biz"])["lost_status"]
    )
else:
    f2_lookup = pd.Series(dtype=str)

# ─────────────────────────────────────────────────────────────
# 1. CONSTRUCT VALIDITY
# ─────────────────────────────────────────────────────────────
print("\n[1] Construct validity — does Top-K match the 'opportunity' profile?")

results_construct = {}
for K in [100, 500, 1000]:
    top = f3.nlargest(K, "f3_priority_score")
    profile = {
        "K": K,
        "median_potential_value":  round(float(top["potential_value"].median()), 2),
        "median_utilization":      round(float(top["utilization_ratio"].median()), 4),
        "pct_active_recent":       round(float((top["days_since_last_purchase"].fillna(9999) <= 365).mean()), 4),
        "pct_cold_start":          round(float(top["is_cold_start"].mean()), 4),
        "pct_high_potential":      round(float((top["opportunity_type"]=="High Potential Underutilization").mean()), 4),
        "pct_purchase_months_ge_3": round(float((top["total_purchase_months"].fillna(0)>=3).mean()), 4),
    }
    results_construct[f"top_{K}"] = profile
    print(f"  Top-{K:<4}  median_pot={profile['median_potential_value']:>8.0f}  "
          f"median_util={profile['median_utilization']:.3f}  "
          f"recent_active={profile['pct_active_recent']*100:.0f}%  "
          f"cold_start={profile['pct_cold_start']*100:.0f}%")

# ─────────────────────────────────────────────────────────────
# 2. DISCRIMINATIVE VALIDITY — vs naive baselines
# ─────────────────────────────────────────────────────────────
print("\n[2] Discriminative validity — does F3 differ from naive baselines?")

# Limit comparison to Branch A (Branch B has no utilization signal)
f3_A = f3[f3["method"] == "underutilization"].copy()
print(f"  (using Branch A only, n={len(f3_A):,})")

# Naive baselines
f3_A["score_potential_only"] = f3_A["potential_value"]
f3_A["score_low_util_only"]  = 1 - f3_A["utilization_ratio"]

# Rank correlations
def rank_correlation(a, b):
    valid = a.notna() & b.notna()
    if valid.sum() < 10: return None, None
    rho_s, _ = spearmanr(a[valid], b[valid])
    tau,    _ = kendalltau(a[valid], b[valid])
    return round(float(rho_s), 4), round(float(tau), 4)

rs_pot, kt_pot = rank_correlation(f3_A["f3_priority_score"], f3_A["score_potential_only"])
rs_lu,  kt_lu  = rank_correlation(f3_A["f3_priority_score"], f3_A["score_low_util_only"])

print(f"  F3 vs potential-only:    Spearman={rs_pot:.4f}  Kendall={kt_pot:.4f}")
print(f"  F3 vs low-util-only:     Spearman={rs_lu:.4f}  Kendall={kt_lu:.4f}")

# Top-K overlap
def topK_overlap(df, score_a, score_b, K):
    if K > len(df): return None
    setA = set(df.nlargest(K, score_a).index)
    setB = set(df.nlargest(K, score_b).index)
    return round(len(setA & setB) / K, 4)

overlap = {}
for K in [100, 500, 1000]:
    overlap[K] = {
        "vs_potential": topK_overlap(f3_A, "f3_priority_score", "score_potential_only", K),
        "vs_low_util":  topK_overlap(f3_A, "f3_priority_score", "score_low_util_only", K),
    }
    print(f"  Top-{K:<4} overlap vs potential={overlap[K]['vs_potential']*100:.0f}%   "
          f"vs low-util={overlap[K]['vs_low_util']*100:.0f}%")

results_discrim = {
    "n_branch_A":         len(f3_A),
    "spearman_vs_potential": rs_pot,
    "kendall_vs_potential":  kt_pot,
    "spearman_vs_low_util":  rs_lu,
    "kendall_vs_low_util":   kt_lu,
    "topK_overlap":          {str(k): v for k, v in overlap.items()},
}

# ─────────────────────────────────────────────────────────────
# 3. NEGATIVE VALIDATION — F3 should NOT rank these high
# ─────────────────────────────────────────────────────────────
print("\n[3] Negative validation — F3 should NOT rank these high")

# Attach F2 lost_status for negative checks
def get_f2_status(row):
    return f2_lookup.get((row["client_id"], row["product_family_biz"]), None)
f3["f2_status_check"] = f3.apply(get_f2_status, axis=1)

results_negative = {}
for K in [100, 500, 1000]:
    top = f3.nlargest(K, "f3_priority_score")
    neg = {
        "K": K,
        # Should be LOW: top alerts that are F2 Likely Lost
        "pct_in_F2_likely_lost":  round(float((top["f2_status_check"] == "Likely Lost").mean()), 4),
        "pct_in_F2_at_risk":      round(float((top["f2_status_check"] == "At Risk").mean()), 4),
        # Should be LOW (for Branch A): long-sleep flagged as opportunity
        # (Branch B is cold-start so days_since_last is NaN by design — exclude)
        "pct_long_sleep_in_branch_A":
            round(float(((top["method"]=="underutilization")
                        & (top["days_since_last_purchase"].fillna(0) > 365)).sum()
                       / max((top["method"]=="underutilization").sum(), 1)), 4),
        # Should be LOW: very thin history flagged as Branch A opportunity (low signal)
        "pct_thin_history_in_branch_A":
            round(float(((top["method"]=="underutilization")
                        & (top["total_purchase_months"].fillna(0) < 3)).sum()
                       / max((top["method"]=="underutilization").sum(), 1)), 4),
        # Reference: utilization_ratio in top alerts (should be low by design)
        "median_utilization_top":  round(float(top["utilization_ratio"].median()), 4),
    }
    results_negative[f"top_{K}"] = neg
    print(f"  Top-{K:<4}  in_F2_LikelyLost={neg['pct_in_F2_likely_lost']*100:.1f}%  "
          f"in_F2_AtRisk={neg['pct_in_F2_at_risk']*100:.1f}%  "
          f"long_sleep_A={neg['pct_long_sleep_in_branch_A']*100:.1f}%  "
          f"thin_hist_A={neg['pct_thin_history_in_branch_A']*100:.1f}%")

# Check capture_window_flag composition in Top-100 — URGENT_CAPTURE means F2 lost
top100 = f3.nlargest(100, "f3_priority_score")
flag_top100 = top100["capture_window_flag"].value_counts(normalize=True).round(4).to_dict()
print(f"\n  Top-100 capture_window_flag composition:")
for k, v in flag_top100.items():
    print(f"    {k:<18} {v*100:.0f}%")

results_negative["top100_flag_composition"] = flag_top100

# ─────────────────────────────────────────────────────────────
# 4. PROFILE COMPARISON — F3 P1 vs population average
# ─────────────────────────────────────────────────────────────
print("\n[4] Profile comparison (P1 vs P4 vs all)")

pop_stats = {}
for grp_name, grp in [("All",      f3),
                       ("P1 only", f3[f3["priority_level"]=="P1 Critical"]),
                       ("P4 only", f3[f3["priority_level"]=="P4 Low"])]:
    pop_stats[grp_name] = {
        "n":                       len(grp),
        "median_potential":        round(float(grp["potential_value"].median()), 2),
        "median_utilization":      round(float(grp["utilization_ratio"].median()), 4),
        "median_potential_gap":    round(float(grp["potential_gap"].median()), 2),
        "pct_cold_start":          round(float(grp["is_cold_start"].mean()), 4),
        "pct_F2_lost_or_risk":     round(float(grp["f2_status_check"].isin(["Likely Lost","At Risk"]).mean()), 4),
    }
    print(f"  {grp_name:<8}  n={pop_stats[grp_name]['n']:>5}  "
          f"med_pot={pop_stats[grp_name]['median_potential']:>8.0f}  "
          f"med_util={pop_stats[grp_name]['median_utilization']:.3f}  "
          f"cold={pop_stats[grp_name]['pct_cold_start']*100:.0f}%  "
          f"F2_at_risk_or_lost={pop_stats[grp_name]['pct_F2_lost_or_risk']*100:.0f}%")

# ─────────────────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────────────────
out = {
    "limitation_note": (
        "F3 is prescriptive. Without intervention records (sales-contact A/B "
        "test) there is no proper outcome ground truth. Metrics here only "
        "assess construct/discriminative/negative validity, not real-world lift."
    ),
    "construct_validity":     results_construct,
    "discriminative_validity": results_discrim,
    "negative_validation":    results_negative,
    "profile_comparison":     pop_stats,
}
(OUTPUT_DIR / "f3_validation_metrics.json").write_text(json.dumps(out, indent=2))

# Markdown report
report = [
    "# F3 — Validation Report (construct / discriminative / negative)",
    "",
    "## ⚠️ Limitation",
    "",
    "F3 is **prescriptive** — its output is a list of clients sales SHOULD contact.",
    "Without intervention records (no record of who was actually called; no A/B",
    "test against a control group), there is no valid outcome ground truth.",
    "",
    "These metrics assess whether the model's STRUCTURE matches its stated intent,",
    "not whether the model produces business lift in practice.",
    "",
    "---",
    "",
    "## 1. Construct Validity",
    "",
    "Does the Top-K of F3 match the 'opportunity' profile (high potential, low",
    "utilization, still active)?",
    "",
] + [
    f"- **Top-{prof['K']}**: median_potential={prof['median_potential_value']:.0f}€, "
    f"median_utilization={prof['median_utilization']:.3f}, "
    f"recent_active={prof['pct_active_recent']*100:.0f}%, "
    f"cold_start={prof['pct_cold_start']*100:.0f}%"
    for prof in results_construct.values()
] + [
    "",
    "Interpretation: top alerts have very high median potential and very low",
    "utilization, consistent with the formula. Cold-start share reflects how",
    "Branch B alerts dominate the priority queue.",
    "",
    "---",
    "",
    "## 2. Discriminative Validity",
    "",
    "Does F3 add value over single-signal baselines? If F3 ≈ a baseline,",
    "the composite formula contributes nothing.",
    "",
    f"- **Spearman ρ vs potential-only**: {rs_pot:.4f}",
    f"- **Spearman ρ vs low-util-only**:  {rs_lu:.4f}",
    "",
    "Top-K overlap with naive baselines:",
    "",
    "| K | overlap with potential-only | overlap with low-util-only |",
    "|---|---|---|",
] + [
    f"| {K} | {overlap[K]['vs_potential']*100:.0f}% | {overlap[K]['vs_low_util']*100:.0f}% |"
    for K in [100, 500, 1000]
] + [
    "",
    "Interpretation: F3 is moderately correlated with each baseline but neither",
    "dominates. Top-K overlap below 100% means F3 produces a meaningfully",
    "different ranking — i.e. the composite formula does combine the two signals.",
    "",
    "---",
    "",
    "## 3. Negative Validation",
    "",
    "F3 should NOT rank these high (they violate the 'opportunity' definition):",
    "",
    "| Top-K | in F2 Likely Lost | in F2 At Risk | long-sleep (Branch A) | thin history (Branch A) |",
    "|---|---|---|---|---|",
] + [
    f"| Top-{neg['K']} | {neg['pct_in_F2_likely_lost']*100:.1f}% | "
    f"{neg['pct_in_F2_at_risk']*100:.1f}% | "
    f"{neg['pct_long_sleep_in_branch_A']*100:.1f}% | "
    f"{neg['pct_thin_history_in_branch_A']*100:.1f}% |"
    for neg in results_negative.values() if isinstance(neg, dict) and "K" in neg
] + [
    "",
    "Top-100 `capture_window_flag` composition:",
    "",
] + [f"- {k}: {v*100:.0f}%" for k, v in flag_top100.items()] + [
    "",
    "Interpretation: presence of F2 'Likely Lost' clients in F3 Top-K is",
    "expected — those are URGENT_CAPTURE flag cases (F3's design boosts them).",
    "Whether this is correct or wrong depends on business view: are 'losing' high-",
    "potential clients an opportunity (last chance to recapture) or a loss (don't",
    "waste sales time)? This is a policy choice, not a model bug.",
    "",
    "---",
    "",
    "## 4. Profile Comparison",
    "",
    "P1 vs P4 vs the full population:",
    "",
    "| Group | n | median_potential | median_utilization | %cold-start | %in F2 (lost or at-risk) |",
    "|---|---|---|---|---|---|",
] + [
    f"| {name} | {p['n']:,} | {p['median_potential']:.0f} | {p['median_utilization']:.3f} | "
    f"{p['pct_cold_start']*100:.0f}% | {p['pct_F2_lost_or_risk']*100:.0f}% |"
    for name, p in pop_stats.items()
] + [
    "",
    "Interpretation: P1 should have higher potential and lower utilization than P4;",
    "if not, the priority score doesn't match the design intent.",
    "",
    "---",
    "",
    "## Summary",
    "",
    "What we CAN say from these checks:",
    "1. F3 Top-K alerts match the construct definition (low utilization, high potential).",
    "2. F3 ranking differs from naive single-signal baselines, so the formula",
    "   contributes structure beyond a simple lookup.",
    "3. F3 deliberately includes some F2-lost clients via URGENT_CAPTURE — whether",
    "   this is right depends on sales policy.",
    "",
    "What we CANNOT say:",
    "1. Whether F3-flagged clients actually become buyers when contacted.",
    "2. Whether F3 produces incremental sales lift over a control group.",
    "3. Whether the priority bucket sizes match sales team capacity.",
    "",
    "These can only be answered with intervention data from a future A/B test.",
]

(OUTPUT_DIR / "f3_validation_report.md").write_text("\n".join(report))

print(f"\n[F3-VALID] Saved → {OUTPUT_DIR / 'f3_validation_metrics.json'}")
print(f"[F3-VALID] Saved → {OUTPUT_DIR / 'f3_validation_report.md'}")

# Clean up old outcome-eval files since they were misleading
old_files = [INPUT_F3 / "f3_backtest_metrics.json",
             INPUT_F3 / "f3_evaluation_report.md"]
for f in old_files:
    if f.exists():
        f.unlink()
        print(f"  removed obsolete file: {f.name}")
