# F3 — Validation Report (construct / discriminative / negative)

## ⚠️ Limitation

F3 is **prescriptive** — its output is a list of clients sales SHOULD contact.
Without intervention records (no record of who was actually called; no A/B
test against a control group), there is no valid outcome ground truth.

These metrics assess whether the model's STRUCTURE matches its stated intent,
not whether the model produces business lift in practice.

---

## 1. Construct Validity

Does the Top-K of F3 match the 'opportunity' profile (high potential, low
utilization, still active)?

- **Top-100**: median_potential=32367€, median_utilization=0.043, recent_active=61%, cold_start=25%
- **Top-500**: median_potential=16645€, median_utilization=0.060, recent_active=59%, cold_start=26%
- **Top-1000**: median_potential=11097€, median_utilization=0.039, recent_active=52%, cold_start=34%

Interpretation: top alerts have very high median potential and very low
utilization, consistent with the formula. Cold-start share reflects how
Branch B alerts dominate the priority queue.

---

## 2. Discriminative Validity

Does F3 add value over single-signal baselines? If F3 ≈ a baseline,
the composite formula contributes nothing.

- **Spearman ρ vs potential-only**: 0.5868
- **Spearman ρ vs low-util-only**:  0.7485

Top-K overlap with naive baselines:

| K | overlap with potential-only | overlap with low-util-only |
|---|---|---|
| 100 | 64% | 18% |
| 500 | 69% | 22% |
| 1000 | 75% | 27% |

Interpretation: F3 is moderately correlated with each baseline but neither
dominates. Top-K overlap below 100% means F3 produces a meaningfully
different ranking — i.e. the composite formula does combine the two signals.

---

## 3. Negative Validation

F3 should NOT rank these high (they violate the 'opportunity' definition):

| Top-K | in F2 Likely Lost | in F2 At Risk | long-sleep (Branch A) | thin history (Branch A) |
|---|---|---|---|---|
| Top-100 | 0.0% | 9.0% | 18.7% | 8.0% |
| Top-500 | 0.0% | 14.4% | 20.4% | 16.1% |
| Top-1000 | 0.0% | 10.5% | 21.1% | 19.4% |

Top-100 `capture_window_flag` composition:

- FRESH_OPPORTUNITY: 47%
- COLD_START: 25%
- MONITOR: 19%
- TRANSITIONAL: 9%

Interpretation: presence of F2 'Likely Lost' clients in F3 Top-K is
expected — those are URGENT_CAPTURE flag cases (F3's design boosts them).
Whether this is correct or wrong depends on business view: are 'losing' high-
potential clients an opportunity (last chance to recapture) or a loss (don't
waste sales time)? This is a policy choice, not a model bug.

---

## 4. Profile Comparison

P1 vs P4 vs the full population:

| Group | n | median_potential | median_utilization | %cold-start | %in F2 (lost or at-risk) |
|---|---|---|---|---|---|
| All | 12,367 | 2223 | 0.000 | 53% | 4% |
| P1 only | 622 | 15722 | 0.059 | 25% | 15% |
| P4 only | 4,894 | 1086 | 0.000 | 64% | 3% |

Interpretation: P1 should have higher potential and lower utilization than P4;
if not, the priority score doesn't match the design intent.

---

## Summary

What we CAN say from these checks:
1. F3 Top-K alerts match the construct definition (low utilization, high potential).
2. F3 ranking differs from naive single-signal baselines, so the formula
   contributes structure beyond a simple lookup.
3. F3 deliberately includes some F2-lost clients via URGENT_CAPTURE — whether
   this is right depends on sales policy.

What we CANNOT say:
1. Whether F3-flagged clients actually become buyers when contacted.
2. Whether F3 produces incremental sales lift over a control group.
3. Whether the priority bucket sizes match sales team capacity.

These can only be answered with intervention data from a future A/B test.