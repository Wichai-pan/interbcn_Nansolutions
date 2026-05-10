# Inibsa Smart Demand Signals — Commercial Intelligence Pipeline

**Hackathon:** Interhack BCN 2026
**Domain:** B2B medical/dental consumables wholesale (Inibsa, Spain)
**Task:** Convert raw sales history into a ranked, explainable list of daily commercial actions for the sales team.

---

## End-to-End Pipeline

```
Data
  ↓
Data Preprocessing
  ↓
F1 Replenishment   F2 Lost Customer    F3 Capture Opportunity
  ↓                  ↓                      ↓
  └──────────────────┴──────────────────────┘
                     ↓
             F4 Action Queue Engine
          (+ Statistical Cross-validation)
                     ↓
        F5 Explanation Layer (Gemini, EN+ES)
                     ↓
          FastAPI Backend + Live Dashboard
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
├── teamate/
│   ├── Final Gradation Results.csv   # Statistical cross-validation output
│   └── Main Python Script.py         # KMeans + F_in urgency scoring
├── src/
│   ├── stage0_preprocessing.py       # Data cleaning & weekly/monthly panels
│   ├── stage1_baseline.py            # F1 seasonal statistical baseline
│   ├── stage2_gru.py                 # F1 GRU sequential model + ensemble
│   ├── f2_lost_customer.py           # F2 lost-customer risk detection
│   ├── f2_evaluate.py                # F2 historical backtest
│   ├── f3_capture_opportunity.py     # F3 capture opportunity detection
│   ├── f3_evaluate.py                # F3 construct/discriminative/negative validation
│   ├── f4_action_queue.py            # F4 unified Top-N engine
│   ├── explanation_layer.py          # F5 Gemini bilingual explanations (batch)
│   └── api/
│       ├── main.py                   # FastAPI app + static frontend mount
│       ├── config.py
│       ├── data_loader.py            # Parquet/JSON loader + status overrides
│       ├── models.py                 # Pydantic schemas
│       └── routers/
│           ├── overview.py           # GET /api/overview
│           ├── alerts.py             # GET /api/alerts · PATCH /api/alerts/{id}/status
│           ├── explain.py            # POST /api/alerts/{id}/explain (on-demand Gemini)
│           ├── actions.py            # GET /api/top-actions
│           ├── map.py                # GET /api/map
│           └── clients.py            # GET /api/clients
├── web/
│   └── index.html                    # Single-page dashboard (vanilla JS)
└── output/
    ├── stage0/                       # Master / weekly panel / cold-start
    ├── stage1/                       # F1 statistical baseline alerts
    ├── stage2/                       # F1 GRU model + combined alerts
    ├── f2/                           # F2 alerts + backtest metrics
    ├── f3/                           # F3 alerts + validation report
    ├── f4/                           # all_alerts.* + top_actions.json
    └── f5/                           # top_actions_explained.json
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

**Product family mapping:**

| Code | Business name | Type | Target module |
|---|---|---|---|
| Familia C1 | Anestesia | Commodity | F1, F2 (Branch B/C), F3 |
| Familia C2 | Bioseguridad | Commodity | F1, F2 (Branch B/C), F3 |
| Familia T1 | Biomateriales | Técnico | F2 (Branch A), F3 |
| Familia T2 | Biomateriales | Técnico | F2 (Branch A), F3 |

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
python src/f3_evaluate.py                 # ~5 s

# F4 — unified action queue (reads teamate/ for statistical enrichment)
python src/f4_action_queue.py             # ~10 s

# F5 — bilingual explanations batch (Gemini API)
python src/explanation_layer.py           # ~30 s for Top-5

# API + Dashboard
uvicorn src.api.main:app --port 8788
```

**Dependencies:** `pandas>=2.0`, `numpy`, `torch>=2.0`, `scikit-learn`, `pyarrow`, `fastapi`, `uvicorn`, `requests`, `python-dotenv`, `scipy`

**Environment:** `.env` with `GEMINI_API_KEY=...` required for F5 only.

---

## Stage 0 — Data Preprocessing

Builds the canonical artifacts every downstream module reads from.

**Steps:**
1. Column normalisation across all 5 raw tables
2. Sales cleaning — tag returns, deduplicate, drop `|unit_price| > 10,000€`
3. Master join — Ventas ⟕ Productos ⟕ Clientes; missing province → `Unknown`
4. Weekly panel — `client_id × product_family × week_start` (ISO Monday), explicit zero-fill
5. Campaign flag — `campaign_active=1` for weeks overlapping any promotional window
6. Cold-start — clients in Potencial but absent from Ventas saved separately

**Outputs (`output/stage0/`):**
- `df_master.parquet` — 163,052 transaction rows
- `df_weekly.parquet` — 2,891,786 rows (15,047 pairs × 261 weeks, zero-filled)
- `df_potential.parquet` — 33,093 rows
- `df_cold_clients.parquet` — 2,940 rows

---

## F1 — Replenishment Intelligence

Two complementary models on the Commodity (C1/C2) universe.

### F1a — Seasonality-Aware Statistical Baseline

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

### F1b — GRU Sequential Model

Binary classification: *given last 12 weeks of behaviour, will this pair purchase in the next 4 weeks?*

| Component | Setting |
|---|---|
| Lookback | 12 weeks, 7-dim sequence features |
| Architecture | GRU(hidden=32, layers=1) → MLP(64) → sigmoid |
| Parameters | 6,433 |
| Loss | BCEWithLogitsLoss(pos_weight=4.57) |
| Split | Train ≤ 2024-06-09 / Val 2024-07~12 / Test 2025-01~11 |

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

**Outputs:**
- `output/stage2/f1_combined_alerts.parquet` — 4,570 ensemble alerts (P1+P2: 919)

---

## F2 — Lost Customer Risk

Three independent branches with strict scope separation.

| Branch | Scope | Method |
|---|---|---|
| **A** | Técnicos (T1/T2), ≥1 purchase | Silence score vs client's own p90 interval |
| **B** | Commodities (C1/C2), >730 days silent | Direct flag → Likely Lost |
| **C** | Commodities (C1/C2), ≤730 days, ≥3 purchase months | Volume + frequency drop vs 12-month baseline |

**Branch A:**
```
silence_score = days_since_last / threshold_used
```
`> 2.0σ` → Likely Lost · `> 1.5σ` → At Risk · `> 1.0σ` → Early Warning

**Branch C:**
```
volume_drop_ratio    = (hist_avg - recent_avg) / hist_avg
frequency_drop_ratio = hist_purchase_rate - recent_purchase_rate
pattern_score        = 0.5 × volume_drop + 0.5 × frequency_drop
```

### F2 Backtest (observation: 2025-06-30, horizon: 6 months)

| Priority | n | Hit Rate |
|---|---|---|
| P1 Critical | 308 | **96.8%** |
| P2 High | 921 | **96.2%** |
| P3 Medium | 1,843 | 88.6% |
| P4 Low | 3,072 | 66.5% |

Overall: **Precision@100 = 98%** · AUROC = 0.733

**Outputs:**
- `output/f2/f2_lost_customer_alerts.parquet` — 4,683 alerts (P1+P2: 937)
- `output/f2/f2_backtest_metrics.json` + `f2_evaluation_report.md`

---

## F3 — Capture Opportunity

Identifies clients with untapped commercial potential at `client_id × product_family_biz` granularity.

| Branch | Scope | Score |
|---|---|---|
| **A** Underutilization | active client, `utilization_ratio < 0.8` | `0.6 × low_util + 0.4 × normalized_gap` |
| **B** Cold-start | in Potencial, never purchased | `normalized_potential_gap` only |

```
utilization_ratio = observed_value_12m / potential_value
potential_gap     = potential_value − observed_value_12m
```

F3 explicitly excludes F2 "Likely Lost" clients — they belong to the win-back queue, not the capture queue.

### F3 Validation (construct validity only — no A/B ground truth)

| | Top-100 | Top-500 |
|---|---|---|
| Median potential gap | €32,367 | €16,645 |
| Spearman vs low-utilization | **0.749** | — |
| Likely Lost in results | **0%** | **0%** |

**Outputs:**
- `output/f3/f3_capture_opportunity_alerts.parquet` — 12,367 alerts (P1+P2: 2,522)

---

## F4 — Commercial Operations Engine

Merges F1 + F2 + F3 into a unified ranked action queue, with statistical cross-validation from teammate data.

### Statistical Cross-validation (teamate/)

Before ranking, F4 loads `teamate/Final Gradation Results.csv` — the output of an independent statistical pipeline (KMeans k=5 clustering + median purchase interval scoring):

```
F_in = (Δt / ⟨t_individual⟩ + Δt / ⟨t_group⟩)   capped at 10.0
Grading = F_in × Potencial_H
```

**Integration rules:**
- F1 alerts where the statistical method classifies the entire client × family as `Lost Customer` (silence > 180d relative to their median interval) are **removed before ranking** — replenishment alerts for already-churned clients are false signals
- Remaining stat fields (`stat_avg_interval_days`, `stat_f_in_fixed`, `stat_grading_eur`, `stat_behavioral_status`, `stat_cluster`) are written into the evidence dict and surfaced in the dashboard as a separate "Statistical Analysis" section alongside "Our Method"

### Ranking Logic

**Step 1 — Within-module rank normalization:**
```
module_rank_pct = rank(module_score, pct=True)   # per module independently
```

**Step 2 — Three scoring layers before normalization:**
- Layer 1 (F1 dormancy): clients past `min(max(expected_interval × 3, 90), 730)` days get `module_score × 0.10` and relabelled "Reactivation (Dormant)"
- Layer 2 (F3 weights): cold-start × 0.65 · mild × 0.80 · moderate × 0.90 · high × 1.00
- Layer 3 (cross-module bonus): `unified_score += 0.04 × |linked_signals|` when the same client × family appears in multiple modules

**Step 3 — MMR Top-5 diversity selection:**
```
penalty_same_module = 0.70   # cumulative across rounds
penalty_same_client = 0.50

while |selected| < 5:
    pick row with highest adjusted_score
    apply penalties to remaining rows matching module / client
```

### Run results

| Stage | Count |
|---|---|
| F1 input | 4,570 |
| F2 input | 4,683 |
| F3 input | 12,367 |
| Cross-module overlap removed | 3,259 |
| **Unified all_alerts** | **17,319** |
| P1 / P2 / P3 / P4 | 866 / 2,598 / 5,196 / 8,659 |
| Top-5 module mix | F1×2 · F2×1 · F3×2 |
| Top-5 unique clients | 5 / 5 |

**Outputs:**
- `output/f4/all_alerts.json` — 17,319 ranked alerts
- `output/f4/top_actions.json` — Top-5 with full evidence + selection trace

---

## F5 — Explanation Layer (Gemini)

Generates bilingual EN/ES summary + recommendation per alert. Available in two modes:

- **Batch** — `python src/explanation_layer.py` processes Top-5 and writes `output/f5/top_actions_explained.json`
- **On-demand** — `POST /api/alerts/{alert_id}/explain` calls Gemini at request time with in-memory caching; result is merged into the alert payload returned to the dashboard

| Parameter | Value |
|---|---|
| Model | `gemini-2.5-flash` |
| Temperature | 0.3 |
| Retries | 3 × exponential backoff |
| Output schema | `summary_en`, `summary_es`, `recommendation_en`, `recommendation_es` |
| Length | summary 30–50 words · recommendation 20–30 words |

F1 prompts surface both method signals (GRU urgency + statistical F_in) and flag significant divergence between the two for the sales rep. F3 prompts are constrained to never assert competitor purchase as fact.

---

## API — Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/overview` | KPI summary — total alerts, P1/P2 counts, module breakdown |
| GET | `/api/alerts` | Paginated alert list with filters (module, priority, province, status, min_score) |
| GET | `/api/alerts/{id}` | Single alert detail including raw evidence |
| PATCH | `/api/alerts/{id}/status` | Update status (open → in_progress → resolved) |
| POST | `/api/alerts/{id}/explain` | On-demand Gemini explanation (cached per session) |
| GET | `/api/top-actions` | Today's Top-5 pre-selected alerts |
| GET | `/api/map` | Province-level alert counts for map view |
| GET | `/api/clients` | Client list with alert summary |

Frontend served at `/` via `StaticFiles` (mounted after all API routes).

---

## Dashboard

Single-page app (`web/index.html`) consuming the FastAPI backend.

**Features:**
- Alert list with priority badges, score bars, province labels (`Madrid · Dental · #14052`)
- Expandable evidence drawer — two sections: **Our Method** (GRU + baseline) and **Statistical Analysis** (KMeans + F_in)
- Status management — open / in progress / resolved with optimistic UI update
- On-demand AI explanation button — calls `/explain`, renders EN+ES recommendation card
- Overview KPIs — total alerts, P1/P2 counts, avg score, module breakdown

---

## Module Status Summary

| Module | Implementation | Evaluation | Key Result |
|---|---|---|---|
| Stage 0 | ✅ | — | 2.89M-row weekly panel |
| F1 Statistical | ✅ | ⚠️ Business sanity | 919 P1+P2 alerts |
| F1 GRU | ✅ | ✅ Time-based test | **AUROC 0.7732** · Precision@100 = 99% |
| F2 | ✅ | ✅ Historical backtest | **AUROC 0.7333** · P1 hit rate 96.8% |
| F3 | ✅ | ⚠️ Construct validity only | Median gap €32k · 0% overlap with churned |
| F4 | ✅ | — | 17,319 unified alerts · Top-5: 3 modules, 5 unique clients |
| F5 (batch) | ✅ | — | 0/5 fallback · bilingual EN+ES |
| F5 (on-demand API) | ✅ | — | Cached per session · async-safe |
| API | ✅ | — | 8 endpoints · FastAPI + Pydantic |
| Dashboard | ✅ | — | Dual-method evidence · live status updates |

---

## Design Principles

1. **Time-based splits, never random** — all supervised evaluation uses temporal cutoff to avoid lookahead bias.
2. **Module separation of concerns** — F1 (replenishment), F2 (churn/win-back), F3 (capture) are deliberately disjoint queues.
3. **Statistical cross-validation** — independent KMeans + interval-scoring pipeline acts as a second opinion; disagreements are surfaced to the sales rep rather than silently resolved.
4. **Soft over hard rules** — F4's penalty system favours diversity without forcing it.
5. **Fallback everywhere** — empty inputs, missing files, API failures: every stage degrades gracefully.
6. **No invented facts** — F5 prompts enforce that LLM output traces back to evidence only.

---

## Reproducibility

```bash
# Read any output
python3 -c "import pandas as pd; print(pd.read_parquet('output/f4/all_alerts.parquet').head())"
cat output/f5/top_actions_explained.json | jq .actions[0].explanation
```

All random seeds fixed: `SEED = 42` (numpy / random / torch). Version snapshot: `output/env.txt`.
