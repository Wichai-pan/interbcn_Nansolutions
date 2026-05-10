# F4 — Commercial Operations Engine Diagnostics

**Scoring date:** 2026-05-10

## Inputs
- F1 alerts (input): 4,570
- F2 alerts (input): 4,683
- F3 alerts (input): 12,367

## Schema unification
- F1 collapsed (T1+T2 → Biomateriales) duplicates dropped: 0
- F2 collapsed (T1+T2) duplicates dropped: 1042

## Layer modifications applied
- Layer 1 (F1 dormancy): LOST_MULTIPLIER=3.0, HARD_CAP=730d, SCORE_SCALE=0.1
- Layer 2 (F3 weights): cold_start=0.65, mild=0.8, moderate=0.9, high=1.0
- Layer 3 (linked_signals): CROSS_MODULE_BONUS=0.04 per link

## Cross-module dedup
- Rows dropped: 1,052
- Module overlap pair counts (within shared client × product_family_biz):
  - F1∩F2: 0
  - F1∩F3: 211
  - F2∩F3: 841
  - F1∩F2∩F3: 0

## Global priority distribution
- P1 Critical: 867
- P2 High:     2,547
- P3 Medium:   5,121
- P4 Low:      8,533
- **Total:**   17,068

## Module share in global Top-100
- F3: 90
- F1: 10

## Top-5 module distribution
- F1: 2  |  F2: 1  |  F3: 2
- Unique clients in Top-5: 5

## Top-5 selection log

| Round | Alert | Module | Client | unified_score | adjusted_score_at_pick | penalties_carried |
|---|---|---|---|---|---|---|
| 1 | F1-000337 | F1 | 10052 | 1.0395 | 1.0395 | 0 |
| 2 | F3-000018 | F3 | 39718 | 1.0394 | 1.0394 | 0 |
| 3 | F2-000001 | F2 | 7135 | 1.0000 | 1.0000 | 0 |
| 4 | F3-000022 | F3 | 6642 | 1.0391 | 0.7274 | 1 |
| 5 | F1-000781 | F1 | 37656 | 1.0386 | 0.7270 | 1 |

## Robustness notes
- evidence dict NaN → null: handled
- unified_score all-identical fallback: no
- Top-N short of 5: no (got 5)