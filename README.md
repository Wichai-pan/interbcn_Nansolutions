# Inibsa Smart Demand Signals — Commercial Intelligence Pipeline

**Hackathon:** Interhack BCN 2026
**Domain:** B2B medical/dental consumables wholesale (Inibsa, Spain)
**Task:** Convert raw sales history into a ranked, explainable list of daily commercial actions for the sales team.

---

## End-to-End Pipeline

```
Stage 0  Data Preprocessing
   ↓
F1 Replenishment   F2 Lost Customer    F3 Capture Opportunity
   ↓                  ↓                      ↓
   └──────────────────┴──────────────────────┘
                      ↓
              F4 Action Queue Engine
                      ↓
         F5 Explanation Layer (Gemini, EN+ES)
                      ↓
           Dashboard / CRM consumption
```

Every stage reads only from prior outputs and is independently runnable.

---

## Project Structure

```
Interbcn/
├── README.md
├── .env                              # GEMINI_API_KEY (gitignored)
├── notebook_data/                    # Raw data (read-only)
│   ├── Ventas.csv                    # Sales — 162,546 rows
│   ├── Productos.csv                 # Product master — 25 SKUs
│   ├── Potencial.csv                 # Client potential — 33,093 rows
│   ├── Clientes.csv                  # Client master — 11,031 rows
│   └── Campañas.csv                  # Promotional campaigns — 10 rows
├── src/
│   ├── stage0_preprocessing.py       # Data cleaning & weekly/monthly panels
│   ├── stage1_baseline.py            # F1 seasonal statistical baseline
│   ├── stage2_gru.py                 # F1 GRU sequential model + ensemble
│   ├── f2_lost_customer.py           # F2 lost-customer risk detection
│   ├── f2_evaluate.py                # F2 historical backtest
│   ├── f3_capture_opportunity.py     # F3 capture opportunity detection
│   ├── f3_evaluate.py                # F3 construct/discriminative/negative validation
│   ├── f4_action_queue.py            # F4 unified Top-N engine
│   └── explanation_layer.py          # F5 Gemini bilingual explanations
├── output/
│   ├── env.txt
│   ├── stage0/                       # Master / weekly panel / cold-start
│   ├── stage1/                       # F1 statistical baseline alerts
│   ├── stage2/                       # F1 GRU model + combined alerts
│   ├── f2/                           # F2 alerts + backtest metrics
│   ├── f3/                           # F3 alerts + validation report
│   ├── f4/                           # all_alerts.* + top_actions.json
│   └── f5/                           # top_actions_explained.json
└── docs/
    └── inibsa-dataset-eda.ipynb      # EDA notebook
```

---

## Dataset Overview

| Dimension | Value |
|---|---|
| Date range | 2021-01-04 → 2025-12-29 |
| Transactions (after cleaning) | 162,546 |
| Active clients | 8,095 |
| SKUs | 25 |
| Product families | 4 (Familia C1 / C2 / T1 / T2) |
| Cold-start clients (potential but no orders) | 2,940 |

**Product family mapping (assumed — pending sponsor confirmation):**

| Code | Business name | Type | Target module |
|---|---|---|---|
| Familia C1 | Anestesia | Commodity | F1, F2 (Branch B/C), F3 |
| Familia C2 | Bioseguridad | Commodity | F1, F2 (Branch B/C), F3 |
| Familia T1 | Biomateriales | Técnico | F2 (Branch A), F3 |
| Familia T2 | Biomateriales | Técnico | F2 (Branch A), F3 |

> ⚠️ The mapping C1 → Anestesia and C2 → Bioseguridad is an assumption; verify before production use.

---

## How to Run

```bash
cd /path/to/Interbcn

# Stage 0 — preprocessing (must run first)
python src/stage0_preprocessing.py        # ~30 s

# F1 — replenishment (statistical + GRU)
python src/stage1_baseline.py             # ~20 s
python src/stage2_gru.py                  # ~7 min CPU

# F2 — lost customer risk
python src/f2_lost_customer.py            # ~1 min
python src/f2_evaluate.py                 # ~1 min  (historical backtest)

# F3 — capture opportunity
python src/f3_capture_opportunity.py      # ~30 s
python src/f3_evaluate.py                 # ~5 s   (construct/discriminative/negative)

# F4 — unified action queue
python src/f4_action_queue.py             # ~10 s

# F5 — bilingual explanations (Gemini API)
python src/explanation_layer.py           # ~30 s for Top-5
```

**Dependencies:** `pandas>=2.0`, `numpy`, `torch>=2.0`, `scikit-learn`, `pyarrow`, `requests`, `python-dotenv`, `scipy`

**Environment:** A `.env` file with `GEMINI_API_KEY=...` is required for F5 only.

---

## Stage 0 — Data Preprocessing

Builds the canonical artifacts every downstream module reads from.

**Steps:**
1. Column normalisation across all 5 raw tables
2. Sales cleaning — tag returns (`is_return=True`, kept), deduplicate, drop `|unit_price|>10,000€`
3. Master join — Ventas ⟕ Productos ⟕ Clientes; missing province → `Unknown`
4. Weekly panel — `client_id × product_family × week_start` (ISO Monday), explicit zero-fill on missing weeks
5. Campaign flag — `campaign_active=1` for weeks overlapping any promotional window
6. Cold-start — clients in Potencial but absent from Ventas saved separately

**Outputs (`output/stage0/`):**
- `df_master.parquet` — 163,052 transaction rows
- `df_weekly.parquet` — 2,891,786 rows (15,047 pairs × 261 weeks, zero-filled)
- `df_potential.parquet` — 33,093 rows
- `df_cold_clients.parquet` — 2,940 rows

---

## F1 — Replenishment Intelligence

Two complementary models on the same Commodity (C1/C2) universe.

### F1a — Seasonality-Aware Statistical Baseline

Frames replenishment prediction as **anomaly detection on purchase intervals**.

**Core formula:**
```
seasonal_time_score = max(0, delay / std_used)
delay               = days_since_last_purchase − expected_interval
replenishment_score = seasonal_time_score × value_factor
```

**Three-level hierarchical fallback:**

| Level | Grouping | Condition | Confidence |
|---|---|---|---|
| A | client × family × quarter | ≥3 purchase intervals | high |
| B | client × family | ≥4 purchase intervals | medium |
| C | family × quarter (global) | final fallback | low |

`value_factor = minmax(log1p(max(potential, hist_12m)))` to weight by commercial value while down-weighting low-revenue noise. Standard deviation floor `ε = 3 days` prevents score blow-up.

### F1b — GRU Sequential Model

Binary classification: *given last 12 weeks of behaviour, will this pair purchase in the next 4 weeks?*

| Component | Setting |
|---|---|
| Lookback | 12 weeks, 7-dim sequence features |
| Static features | log1p(potential) + segment + province (target-mean) + family one-hot |
| Architecture | GRU(hidden=32, layers=1) → MLP(64) → sigmoid |
| Parameters | **6,433** (target: < 20k) |
| Loss | BCEWithLogitsLoss(pos_weight=4.57) |
| Split | Train ≤ 2024-06-09 / Val 2024-07~12 / Test 2025-01~11 (time-based, no shuffle) |

### F1 Ensemble & Evaluation

```
f1_final_score = 0.5 × rank_norm(replenishment_score) + 0.5 × reorder_probability
```

| Metric | Validation | Test |
|---|---|---|
| **AUROC** | 0.7736 | **0.7732** |
| AUPRC | 0.4168 | 0.4419 |
| Precision@100 | 0.88 | **0.99** |
| Precision@1000 | 0.717 | 0.772 |

**Top features (permutation importance, AUROC drop):**
days_since_last_purchase 0.053 · potential_gap_ratio 0.037 · weekly_value 0.029.

**Outputs:**
- `output/stage1/f1_baseline_alerts.parquet` — 8,450 scored pairs
- `output/stage2/f1_combined_alerts.parquet` — 4,570 ensemble alerts (P1+P2: 919)

---

## F2 — Lost Customer Risk

Three independent branches with strict scope separation. Each (client × product_family) appears in exactly one branch.

| Branch | Scope | Method |
|---|---|---|
| **A** | Productos Técnicos (T1/T2), ≥1 purchase | Silence score vs client's own p90 interval |
| **B** | Commodities (C1/C2), >730 days silent, not in F1 scope | Direct flag → Likely Lost |
| **C** | Commodities (C1/C2), ≤730 days, ≥3 purchase months, not in F1 scope | Volume + frequency drop vs 12-month baseline |

**Branch A scoring** (Silence Score):
```
threshold_used = max(p90(historical_intervals), 1)   if n_intervals ≥ 3
                 else 210d (T1) / 251d (T2)
silence_score  = days_since_last / threshold_used
```
- `> 2.0σ` → Likely Lost · `> 1.5σ` → At Risk · `> 1.0σ` → Early Warning

**Branch C scoring** (Pattern Deterioration):
```
volume_drop_ratio        = (hist_avg - recent_avg) / hist_avg
frequency_drop_ratio     = (hist_purchase_rate - recent_purchase_rate)
pattern_deterioration_score = 0.5 × volume_drop + 0.5 × frequency_drop
```

**Final priority:** `f2_priority_score = raw_score × value_factor` then percentile binning P1/P2/P3/P4.

### F2 Backtest Evaluation

Historical backtest at observation date 2025-06-30, ground truth from next 6 months:
- `y_strict`: zero purchase in future 6 months
- `y_lenient`: future 6m value < 40% of historical 6m mean

| Metric | Value |
|---|---|
| **AUROC (vs y_strict)** | **0.7333** |
| AUPRC | 0.9123 |
| Precision@100 | 0.98 |
| Lift@100 | 1.24× |

**Hit rate by `lost_status` (sanity check, monotonic by design):**

| Status | n | Real lost rate |
|---|---|---|
| Likely Lost | 4,455 | **90.9%** |
| At Risk | 765 | 54.1% |
| Early Warning | 924 | 42.6% |

**Outputs:**
- `output/f2/f2_lost_customer_alerts.parquet` — 4,683 alerts (P1+P2: 937)
- `output/f2/f2_backtest_metrics.json` + `f2_evaluation_report.md`

---

## F3 — Capture Opportunity

Identifies clients with **untapped commercial potential** at granularity `client_id × product_family_biz` (3 business names, not 4 codes — Potencial table has only 3).

Two branches:

| Branch | Scope | Score |
|---|---|---|
| **A** Underutilization | active client, has purchase history, `utilization_ratio < 0.8` | `0.6 × low_util + 0.4 × normalized_potential_gap` |
| **B** Cold-start | in Potencial but never purchased | `normalized_potential_gap` only |

### Capture vs Win-back Separation

F3 explicitly **excludes F2 "Likely Lost" clients** — they belong to F2's win-back queue, not F3's capture queue. This was a deliberate design choice after evaluation showed the original formula's URGENT_CAPTURE boost made 96% of F3 P1 overlap with F2 lost customers, conflating two fundamentally different sales motions.

`capture_window_flag` indicates the client's standing in F2:
- `FRESH_OPPORTUNITY` — no F2 issue, healthy active client
- `TRANSITIONAL` — F2 At Risk
- `MONITOR` — F2 Early Warning
- `COLD_START` — never purchased

### F3 Validation (no proper ground truth available)

F3 is **prescriptive** ("should sales contact this client?") — there's no outcome ground truth without intervention records (no A/B test, no record of who was actually called). Three weak validation modes are reported instead:

1. **Construct validity** — Top-100 has median potential 25,892€, median utilization 0.000 (matches "opportunity" profile by definition)
2. **Discriminative validity** — Spearman ρ vs naive baselines: 0.59 (potential-only), 0.75 (low-util-only); Top-100 overlap: 64% / 18%
3. **Negative validation** — after fix:

| Top-K | in F2 Likely Lost | long-sleep (>365d) |
|---|---|---|
| Top-100 | **0.0%** ✅ | 18.7% |
| Top-500 | 0.0% | 20.4% |

**Outputs:**
- `output/f3/f3_capture_opportunity_alerts.parquet` — 12,367 alerts (P1+P2: 2,522)
- `output/f3/f3_validation_metrics.json` + `f3_validation_report.md`

---

## F4 — Commercial Operations Engine

Merges F1 + F2 + F3 into a unified, ranked action queue.

### Merge logic

1. **Schema unification** — map F1 product_family (C1/C2) → product_family_biz; collapse F2 T1+T2 duplicates by max severity
2. **In-module rank-percentile** — `module_rank_pct = rank(score, pct=True)` (so cross-module scores are comparable)
3. **Concat** — `unified_score = module_rank_pct`
4. **Cross-module dedup** — same (client × family_biz) appearing in multiple modules: keep highest unified_score
5. **Global priority bins** — top 5% P1 / next 15% P2 / next 30% P3 / rest P4

### Top-N Soft Penalty Selection

Greedy diversification to avoid sales fatigue and module monoculture:

```
penalty_same_module = 0.7   # cumulative across rounds
penalty_same_client = 0.5

while |selected| < N:
    pick row with highest adjusted_score
    apply both penalties to remaining rows that match module / client
```

Each Top-N record carries `selection_reason.penalties_applied` for full traceability.

### Run results

| Stage | Count |
|---|---|
| F1 input | 4,570 |
| F2 input | 4,683 |
| F3 input | 12,367 |
| Concat (before dedup) | 20,578 |
| Cross-module overlap removed | 3,259 |
| **Unified all_alerts** | **17,319** |
| P1 / P2 / P3 / P4 | 866 / 2,598 / 5,196 / 8,659 |
| **Top 5 module mix** | **F1×2 · F2×1 · F3×2** |
| Top 5 unique clients | 5/5 |

**Outputs:**
- `output/f4/all_alerts.parquet` + `all_alerts.json` — 17,319 ranked alerts (full)
- `output/f4/top_actions.json` — Today's Top-5 with full evidence + selection trace
- `output/f4/f4_diagnostics.md`

`linked_signals: []` placeholder field is reserved on every alert for a future cross-module signal aggregation pass.

---

## F5 — Explanation Layer (Gemini)

Generates a strict-schema bilingual EN/ES summary + recommendation per alert.

### Configuration

| Parameter | Value |
|---|---|
| Model | `gemini-2.5-flash` (REST API) |
| Temperature | 0.3 (stable but not deterministic) |
| Max output tokens | 1,024 |
| Thinking budget | 0 (disabled — gemini-2.5 internal "thinking" tokens charge against output limit) |
| Retries | 3 with exponential backoff (2s, 4s, 6s) |
| Auth | `GEMINI_API_KEY` from `.env` (gitignored) |

### Per-module prompts

Three prompts share a common system block enforcing 8 strict rules:
- Use **only** facts from `<evidence>` block
- Never promise outcomes — use "indicates" / "suggests" / "sugiere"
- Refer to clients by ID, never invent names
- Output must be a **single valid JSON object** (no prose, no markdown fences)
- Schema: `summary_en`, `summary_es`, `recommendation_en`, `recommendation_es`
- Length budget: summary 30–50 words · recommendation 20–30 words
- Spanish must be natural Castilian, not literal translation

**F3 special constraint:** must NOT assert competitor purchase as fact (Inibsa cannot observe competitors). Required phrasing: "potential unmet demand" / "posible fuga a competencia".

### Robustness

```
LLM raw → strip markdown fences → parse JSON → validate schema → fallback template
```

- `safe_parse_json` extracts the outer `{...}` block even with surrounding noise
- `validate_schema` requires all 4 fields present and non-empty
- On any failure: drop in a deterministic template (`"Client X flagged by F-N..."`) so the front-end never crashes

### Run results

```
[Explain] output/f4/top_actions.json (5 items)
  saved → output/f5/top_actions_explained.json
  fallback used on 0/5 alerts
```

**Outputs:**
- `output/f5/top_actions_explained.json` — Top-5 with `explanation` field per alert
- Optionally `output/f5/all_alerts_explained.json` (with `--enrich-all --max-all 50`)

---

## Module Status Summary

| Module | Implementation | Evaluation | Key Result |
|---|---|---|---|
| Stage 0 | ✅ | — | 2.89M-row weekly panel, 681K-row monthly panel |
| **F1 Statistical** | ✅ | ⚠️ Business sanity | 919 P1+P2 alerts |
| **F1 GRU** | ✅ | ✅ Time-based test | **AUROC 0.7732** |
| **F2** | ✅ | ✅ Historical backtest | **AUROC 0.7333** · Likely-Lost hit rate **90.9%** |
| **F3** | ✅ | ⚠️ Construct/discriminative/negative only | No outcome GT — prescriptive task |
| **F4** | ✅ | — | 17,319 unified alerts · Top-5 covers 3 modules + 5 unique clients |
| **F5** | ✅ | — | 0/5 fallback rate · bilingual EN+ES |

---

## Design Principles & Caveats

1. **Time-based splits, never random** — every supervised evaluation uses temporal cutoff to avoid lookahead bias.
2. **Module separation of concerns** — F1 (補貨), F2 (流失/挽回), F3 (拉新進攻) are deliberately disjoint queues. F3 hands off "Likely Lost" customers to F2.
3. **Soft over hard rules** — F4's penalty system favours diversity without forcing it (a strong score can still beat a same-module penalty).
4. **Fallback everywhere** — empty inputs, missing files, API failures, all-equal scores: every stage degrades gracefully.
5. **No invented facts** — F5 prompts and validation enforce that LLM output trace back to evidence; numbers are checked against source.
6. **F3 has no outcome GT** — its evaluation is structural (construct/discriminative/negative), not predictive. True outcome lift requires intervention data we don't have.
7. **Family mapping is an assumption** — C1→Anestesia, C2→Bioseguridad, T1/T2→Biomateriales is plausible but not sponsor-confirmed.

---

## Reproducibility

- All random seeds fixed: `SEED = 42` (numpy / random / torch).
- Versions snapshot: `output/env.txt`.
- Read any output:
  ```bash
  python3 -c "import pandas as pd; print(pd.read_parquet('output/f4/all_alerts.parquet').head())"
  cat output/f5/top_actions_explained.json | jq .actions[0].explanation
  ```
