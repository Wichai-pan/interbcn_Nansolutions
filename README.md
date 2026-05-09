# Inibsa Smart Demand Signals — F1 Replenishment Intelligence

**Hackathon:** Interhack BCN 2026  
**Domain:** B2B medical/dental consumables wholesale (Inibsa, Spain)  
**Task:** Predict which clients need replenishment calls in the next 4 weeks

---

## Project Structure

```
Interbcn/
├── README.md
├── notebook_data/          # Raw data (read-only)
│   ├── Ventas.csv          # Sales transactions — 162,546 rows
│   ├── Productos.csv       # Product master — 25 SKUs
│   ├── Potencial.csv       # Client commercial potential — 33,093 rows
│   ├── Clientes.csv        # Client master — 11,031 rows
│   └── Campañas.csv        # Promotional campaigns — 10 rows
├── src/
│   ├── stage0_preprocessing.py   # Data cleaning & weekly panel construction
│   ├── stage1_baseline.py        # Seasonality-aware statistical baseline
│   └── stage2_gru.py             # GRU sequential model
├── output/
│   ├── env.txt                   # Package version snapshot
│   ├── stage0/                   # Stage 0 artifacts
│   ├── stage1/                   # Stage 1 artifacts
│   └── stage2/                   # Stage 2 artifacts
└── docs/
    └── inibsa-dataset-eda.ipynb  # Exploratory data analysis notebook
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

| Code | Business name | Type |
|---|---|---|
| Familia C1 | Anestesia (anaesthetics) | Commodity → F1 target |
| Familia C2 | Bioseguridad (biosafety / PPE) | Commodity → F1 target |
| Familia T1 | Biomateriales (biomaterials) | Técnico → F2 |
| Familia T2 | Biomateriales (biomaterials) | Técnico → F2 |

> ⚠️ The mapping C1 → Anestesia and C2 → Bioseguridad is an assumption. Verify with the sponsor before using in production.

---

## How to Run

Each stage is self-contained and must be run in order:

```bash
cd /path/to/Interbcn

python src/stage0_preprocessing.py   # ~30 s
python src/stage1_baseline.py        # ~20 s
python src/stage2_gru.py             # ~7 min (CPU)
```

**Dependencies:** `pandas>=2.0`, `numpy`, `torch>=2.0`, `scikit-learn`, `pyarrow`

---

## Stage 0 — Data Preprocessing

**Script:** `src/stage0_preprocessing.py`

### Steps

1. **Column normalisation** — Unified field names across all tables (`client_id`, `product_id`, `date`, …)
2. **Sales cleaning** — Tag return rows (`is_return=True`, kept), deduplicate, drop rows with `|unit_price| > 10,000 €`
3. **Master join** — `Ventas LEFT JOIN Productos LEFT JOIN Clientes`; clients missing from Clientes receive `province = Unknown`
4. **Weekly panel** — Aggregate to `client_id × product_family × week_start` (ISO Monday); **explicitly zero-fill missing weeks** so every pair has a continuous time axis
5. **Campaign flag** — Mark `campaign_active = 1` for weeks overlapping any promotional window
6. **Cold-start identification** — Clients present in Potencial but absent from Ventas saved separately

### Output Files

| File | Rows | Description |
|---|---|---|
| `output/stage0/df_master.parquet` | 163,052 | Transaction-level master table |
| `output/stage0/df_weekly.parquet` | 2,891,786 | Weekly panel (15,047 pairs × 261 weeks, zero-filled) |
| `output/stage0/df_potential.parquet` | 33,093 | Client potential lookup |
| `output/stage0/df_cold_clients.parquet` | 2,940 | Cold-start clients (F3 input) |
| `output/stage0/preprocessing_report.md` | — | Data cleaning report |

---

## Stage 1 — Seasonality-Aware Statistical Baseline

**Script:** `src/stage1_baseline.py`

### Algorithm

For Commodity products (C1/C2), replenishment prediction is framed as **statistical anomaly detection** on purchase intervals.

**Core formula:**
```
seasonal_time_score = max(0, delay / std_used)
delay               = days_since_last_purchase − expected_interval
replenishment_score = seasonal_time_score × value_factor
```

**Three-level hierarchical fallback (handles sparse purchase history):**

| Level | Grouping | Condition | Confidence |
|---|---|---|---|
| A | client × family × quarter | ≥ 3 purchase intervals | high |
| B | client × family | ≥ 4 purchase intervals | medium |
| C | family × quarter (global) | final fallback | low |

Standard deviation floor ε = 3 days prevents score blow-up for highly regular clients.

**Value factor:** `log1p(max(potential_value, trailing-12m sales))` normalised to [0, 1] — down-weights low-revenue noise. Log scale is used because EUR sales are heavily right-skewed.

**Priority bins** (computed on the actual score distribution, not fixed thresholds):  
P1 Critical = top 5% · P2 High = next 15% · P3 Medium = next 30% · P4 Low = remaining 50%

### Results

| Metric | Value |
|---|---|
| Total scored pairs | 8,450 |
| Overdue alerts (score > 0) | 4,570 |
| P1 Critical | 230 |
| P2 High | 689 |
| **P1 + P2 total** | **919** |
| Confidence high / medium / low | 2,634 / 1,799 / 4,017 |
| Mean expected reorder interval (overdue set) | 143 days |

### Output Files

| File | Rows | Description |
|---|---|---|
| `output/stage1/f1_baseline_alerts.parquet` | 8,450 | Full scored output with priority levels and reason text |
| `output/stage1/f1_baseline_diagnostics.md` | — | Diagnostics report |

---

## Stage 2 — GRU Sequential Model

**Script:** `src/stage2_gru.py`

### Task Definition

```
Input : last 12 weeks of time-series features for a (client_id, product_family) pair
Output: probability of placing at least one order in the next 4 weeks ∈ [0, 1]
```

### Features

**Sequence features — 7 dims per timestep, lookback L = 12 weeks:**

| Feature | Description |
|---|---|
| `weekly_units` | Units purchased in that week |
| `weekly_value` | EUR sales value |
| `order_count` | Number of distinct orders |
| `days_since_last_purchase` | Days since last purchase (capped at 365) |
| `rolling_mean_units_4w` | 4-week rolling mean (shift(1) to prevent lookahead) |
| `campaign_active` | 1 if a promotional campaign overlaps this week |
| `potential_gap_ratio` | 1 − (YTD cumulative sales / potential value), clipped [0, 1] |

**Static features — 5 dims per sample:**  
`log1p(potential_value)` + segment code (target-mean encoded) + province (target-mean encoded) + product family (one-hot)

### Model Architecture

```
(batch, 12, 7)
    ↓  GRU(hidden=32, layers=1, batch_first=True)
(batch, 32)   ← last hidden state h_T
    ↓  concat static features
(batch, 37)
    ↓  Linear(64) → ReLU → Dropout(0.3) → Linear(1)
    ↓  BCEWithLogitsLoss(pos_weight = 4.57)

Total parameters: 6,433  (design target: < 20k)
```

### Train / Val / Test Split (strict time-based — no random shuffle)

```
Train : window_end ≤ 2024-06-09    578,377 samples
Val   : 2024-07 ~ 2024-12          122,449 samples
Test  : 2025-01 ~ 2025-11          193,956 samples
```

The same client appears in all three splits — this is intentional for B2B replenishment: the entity is not held out, the **time period** is. A 4-week buffer between train and val prevents label leakage.

### Evaluation Results

| Metric | Validation | Test |
|---|---|---|
| **AUROC** | **0.7736** | **0.7732** |
| AUPRC | 0.4168 | 0.4419 |
| Brier Score | 0.1867 | 0.1919 |
| Precision@100 | 0.88 | **0.99** |
| Precision@500 | 0.76 | 0.82 |
| Precision@1000 | 0.717 | 0.772 |
| Recall@1000 | 0.036 | 0.023 |

Training: early stopped at epoch 15 (best epoch 10), Adam lr = 1e-3, ~7 min on CPU.

**Feature importances (permutation AUROC drop on validation set):**

| Rank | Feature | Importance |
|---|---|---|
| 1 | `days_since_last_purchase` | 0.053 |
| 2 | `potential_gap_ratio` | 0.037 |
| 3 | `weekly_value` | 0.029 |
| 4 | `rolling_mean_units_4w` | 0.015 |
| 5 | `weekly_units` | 0.012 |
| 6 | `order_count` | 0.008 |
| 7 | `campaign_active` | 0.002 |

### Output Files

| File | Description |
|---|---|
| `output/stage2/gru_model.pt` | Best model weights (epoch 10) |
| `output/stage2/f1_gru_predictions.parquet` | Cross-sectional inference for 8,349 pairs |
| `output/stage2/f1_combined_alerts.parquet` | Stage 1 + Stage 2 merged alerts, 4,570 rows |
| `output/stage2/train_val_test_metrics.json` | Full metrics record |
| `output/stage2/f1_gru_report.md` | Model report |

---

## Head-to-Head Comparison

Fair comparison on the **same test set** (193k samples, 12.3% positive rate):

| Method | AUROC | AUPRC | Precision@1000 |
|---|---|---|---|
| GRU (deep learning) | **0.7732** | **0.4419** | **0.772** |
| Days overdue × value weight (statistical proxy) | 0.5755 | 0.1500 | 0.138 |
| Rolling mean units (activity proxy) | 0.5159 | 0.1249 | 0.119 |
| Days overdue only | 0.3575 | 0.0890 | 0.024 |

**Key findings:**

- GRU leads on Precision@1000 by **5.6×** (0.772 vs 0.138) — the Top-1000 clients it flags have a 77% chance of actually ordering in the next 4 weeks
- Raw days-overdue scores an AUROC below 0.5, because it cannot distinguish temporarily dormant clients from permanently churned ones — ranking is effectively reversed
- The two signals have a correlation of only −0.055, meaning they are nearly orthogonal: the statistical score captures *how far past due* a client is, while the GRU captures *sequential purchase patterns*
- The current ensemble formula (0.5 × rank + 0.5 × GRU) underperforms either method alone because the two signals point in opposite directions

**Irreplaceable value of the statistical baseline:**
- Generates human-readable reason text ("3.5σ beyond the expected Q3 reorder cycle")
- Cold-start robust: produces a score with as few as 1 historical purchase; GRU requires ≥ 16 weeks of data
- Extreme overdue alerts (e.g. 460σ) are a strong business signal for high-value clients regardless of model score

---

## Progress & Roadmap

### Done ✅
- [x] Stage 0: full data cleaning, zero-filled weekly panel, cold-start identification
- [x] Stage 1: three-level hierarchical baseline, 8,450 pairs scored, 919 P1+P2 alerts
- [x] Stage 2: GRU training (AUROC 0.773), cross-sectional inference, permutation feature importance
- [x] Head-to-head comparison on shared test set

### To Do / Improvements 🔧
- [ ] **Ensemble fix**: replace the 0.5+0.5 linear blend with a dual-view display or a stacking layer
- [ ] **F2 module**: low-frequency purchase prediction for Técnico products (T1/T2)
- [ ] **Cold-start F3**: first-touch strategy for the 2,940 clients with no order history
- [ ] **Family mapping confirmation**: verify C1 → Anestesia and C2 → Bioseguridad with the sponsor
- [ ] **Sales dashboard**: priority list UI for field sales teams
- [ ] **Recall improvement**: current Recall@1000 is only 2–4%; needs broader effective coverage

---

## Reproducibility

```bash
# All random seeds fixed: SEED = 42 (numpy / random / torch)
# Read any output with pandas:
python3 -c "import pandas as pd; print(pd.read_parquet('output/stage1/f1_baseline_alerts.parquet').head())"
```

Full package version snapshot: `output/env.txt`
