# F2 — Backtest Evaluation Report

## Setup
- **Observation date:** 2025-06-30
- **Future window:**    2025-07-01 → 2025-12-29 (6 months)
- **Backtest alerts:**  6,144
- **Note:** f1_scope exclusion disabled in eval mode; F2 evaluated standalone

## Proxy Labels
- `y_strict`:  no purchase in future 6 months (positive rate: 79.1%)
- `y_lenient`: future 6m value < 40% of historical 6m (positive rate: 79.7%)

## Overall Metrics

### vs y_strict
- label: y_strict (no purchase 6m)
- auroc: 0.7333
- auprc: 0.9123
- n_pos: 4860
- n_total: 6144
- base_rate: 0.791
- precision@50: 0.96
- recall@50: 0.0099
- lift@50: 1.2136
- precision@100: 0.98
- recall@100: 0.0202
- lift@100: 1.2389
- precision@200: 0.96
- recall@200: 0.0395
- lift@200: 1.2136
- precision@500: 0.968
- recall@500: 0.0996
- lift@500: 1.2237
- precision@1000: 0.964
- recall@1000: 0.1984
- lift@1000: 1.2187

### vs y_lenient
- label: y_lenient (>60% drop)
- auroc: 0.7286
- auprc: 0.9132
- n_pos: 4897
- n_total: 6144
- base_rate: 0.797
- precision@50: 0.96
- recall@50: 0.0098
- lift@50: 1.2045
- precision@100: 0.98
- recall@100: 0.02
- lift@100: 1.2296
- precision@200: 0.96
- recall@200: 0.0392
- lift@200: 1.2045
- precision@500: 0.968
- recall@500: 0.0988
- lift@500: 1.2145
- precision@1000: 0.964
- recall@1000: 0.1969
- lift@1000: 1.2095

## Branch-level (vs y_strict)

                       n_alerts  y_strict_rate  auroc_strict  auprc_strict
Branch A (silence)       3396.0         0.8884        0.6355        0.9367
Branch B (direct)        1529.0         0.9457        0.5951        0.9585
Branch C (historical)    1219.0         0.3257        0.6636        0.4992

## Hit-rate by `lost_status`  (sanity check)
Higher severity → higher actual lost rate is expected.

  lost_status    n  strict_rate  lenient_rate
      At Risk  765       0.5412        0.5569
Early Warning  924       0.4264        0.4502
  Likely Lost 4455       0.9095        0.9102

## Hit-rate by `priority_level`

priority_level    n  strict_rate  lenient_rate
   P1 Critical  308       0.9675        0.9675
       P2 High  921       0.9620        0.9620
     P3 Medium 1843       0.8861        0.8888
        P4 Low 3072       0.6650        0.6755