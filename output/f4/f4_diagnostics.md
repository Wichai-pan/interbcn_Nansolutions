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
- Rows dropped: 3,259
- Module overlap pair counts (within shared client × product_family_biz):
  - F1∩F2: 0
  - F1∩F3: 2,418
  - F2∩F3: 841
  - F1∩F2∩F3: 0

## Global priority distribution
- P1 Critical: 866
- P2 High:     2,598
- P3 Medium:   5,197
- P4 Low:      8,658
- **Total:**   17,319

## Module share in global Top-100
- F3: 63
- F1: 37

## Top-5 module distribution
- F1: 2  |  F2: 1  |  F3: 2
- Unique clients in Top-5: 5

## Top-5 selection log

| Round | Alert | Module | Client | unified_score | adjusted_score_at_pick | penalties_carried |
|---|---|---|---|---|---|---|
| 1 | F1-000050 | F1 | 1000082089 | 1.0400 | 1.0400 | 0 |
| 2 | F3-000018 | F3 | 39718 | 1.0394 | 1.0394 | 0 |
| 3 | F2-000001 | F2 | 7135 | 1.0000 | 1.0000 | 0 |
| 4 | F1-000100 | F1 | 28152 | 1.0398 | 0.7278 | 1 |
| 5 | F3-000022 | F3 | 6642 | 1.0391 | 0.7274 | 1 |

## Robustness notes
- evidence dict NaN → null: handled
- unified_score all-identical fallback: no
- Top-N short of 5: no (got 5)