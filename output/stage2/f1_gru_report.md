# Stage 2 — GRU Report

## Architecture
- Input: (batch, L=12, F=7)
- GRU hidden=32, layers=1
- MLP: Linear(32+5→64) → ReLU → Dropout(0.3) → Linear→1
- Total params: 6,433
- Device: cpu

## Split Policy
Time-based split. Same CLIENT appears in all splits — correct for B2B replenishment.
- Train: window_end ≤ 2024-06-02 (578,377 samples)
- Val:   (2024-06-02, 2024-12-31] (122,449 samples)
- Test:  (2024-12-31, 2025-11-30] (193,956 samples)
4-week buffer between train/val to prevent label leakage.

## Validation Metrics
- auroc: 0.7736
- auprc: 0.4168
- brier: 0.1867
- n_pos: 19734
- n_total: 122449
- precision@100: 0.88
- recall@100: 0.0045
- precision@500: 0.76
- recall@500: 0.0193
- precision@1000: 0.717
- recall@1000: 0.0363

## Test Metrics
- auroc: 0.7732
- auprc: 0.4419
- brier: 0.1919
- n_pos: 34222
- n_total: 193956
- precision@100: 0.99
- recall@100: 0.0029
- precision@500: 0.822
- recall@500: 0.012
- precision@1000: 0.772
- recall@1000: 0.0226

## Feature Importances (permutation, val AUROC drop)
- days_since_last_purchase: 0.0527
- potential_gap_ratio: 0.0373
- weekly_value: 0.0293
- rolling_mean_units_4w: 0.0227
- weekly_units: 0.0090
- order_count: 0.0068
- campaign_active: -0.0009

## Training curve (all epochs)
 epoch  train_loss  train_auc  val_loss  val_auc
     1    0.963903   0.750306  0.893996 0.770585
     2    0.930800   0.773705  0.889988 0.772117
     3    0.923445   0.777802  0.890468 0.772400
     4    0.918808   0.780338  0.894240 0.770749
     5    0.915268   0.782020  0.900068 0.770682
     6    0.913645   0.782959  0.896162 0.772131
     7    0.911889   0.784096  0.892938 0.772876
     8    0.910382   0.784695  0.901610 0.770400
     9    0.908653   0.785797  0.893739 0.771669
    10    0.907772   0.786279  0.892674 0.773643
    11    0.906959   0.786766  0.906339 0.770956
    12    0.905972   0.787205  0.903008 0.770511
    13    0.905327   0.787472  0.899910 0.770230
    14    0.904255   0.788237  0.898682 0.771784
    15    0.900981   0.790008  0.898556 0.771641

## Ensemble Formula
f1_final_score = 0.5 × rank_norm(replenishment_score) + 0.5 × reorder_probability

## Combined P1+P2 alerts: 914

## Failure Modes
- pos_weight: 4.57 (BCEWithLogitsLoss)
- Sparse pairs (<L+H weeks): dropped from GRU, kept in Stage 1.
- Province/segment: train-set target-mean encoded (no leakage).
- All-zero lookback + >180d dormancy: excluded from training.