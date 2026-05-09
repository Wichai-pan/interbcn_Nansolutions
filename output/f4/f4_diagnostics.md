# F4 — Commercial Operations Engine Diagnostics

**Scoring date:** 2026-05-09

## Inputs
- F1 alerts (input): 4,570
- F2 alerts (input): 4,683
- F3 alerts (input): 12,367

## Schema unification
- F1 collapsed (T1+T2 → Biomateriales) duplicates dropped: 0
- F2 collapsed (T1+T2) duplicates dropped: 1042

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
- P3 Medium:   5,196
- P4 Low:      8,659
- **Total:**   17,319

## Module share in global Top-100
- F3: 60
- F1: 22
- F2: 18

## Top-5 module distribution
- F1: 2  |  F2: 1  |  F3: 2
- Unique clients in Top-5: 5

## Top-5 selection log

| Round | Alert | Module | Client | unified_score | adjusted_score_at_pick | penalties_carried |
|---|---|---|---|---|---|---|
| 1 | F1-000001 | F1 | 1000080301 | 1.0000 | 1.0000 | 0 |
| 2 | F2-000001 | F2 | 7135 | 1.0000 | 1.0000 | 0 |
| 3 | F3-000001 | F3 | 1000081536 | 1.0000 | 1.0000 | 0 |
| 4 | F3-000002 | F3 | 17168 | 0.9999 | 0.6999 | 1 |
| 5 | F1-000002 | F1 | 39452 | 0.9998 | 0.6998 | 1 |

## Robustness notes
- evidence dict NaN → null: handled
- unified_score all-identical fallback: no
- Top-N short of 5: no (got 5)