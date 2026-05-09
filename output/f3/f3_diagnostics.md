# F3 — Capture Opportunity Diagnostics

**Scoring date:** 2026-01-05

## Branch counts
- Branch A (Underutilization):  6,493
- Branch B (Cold-start):        6,541
- Duplicates dropped on merge:   0
- **Total alerts:** 12,367

## opportunity_type distribution
- New Account Opportunity: 6,541
- Moderate Underutilization: 2,169
- High Potential Underutilization: 2,076
- Mild Underutilization: 1,581

## capture_window_flag distribution
- COLD_START: 6,541
- FRESH_OPPORTUNITY: 4,985
- TRANSITIONAL: 439
- MONITOR: 402

## priority_level distribution
- P3 Medium: 4,951
- P4 Low: 4,894
- P2 High: 1,900
- P1 Critical: 622

## product_family_biz distribution
- Anestesia: 6,247
- Bioseguridad: 3,843
- Biomateriales: 2,277

## Top 10 provinces
- Madrid: 2,025
- Barcelona: 1,291
- Valencia: 968
- Sevilla: 525
- Alicante: 511
- Málaga: 441
- Tarragona: 434
- Granada: 356
- Murcia: 348
- Asturias: 346

## Quality control
- potential_value invalid (NaN or ≤0) dropped: 5,209 rows from raw potencial table
- utilization_ratio ≥ 0.8 skipped:             2,191 pairs
- F2 file present:                              True
- Cold-start in alerts:                         6,541 (52.9%)

## F2 linkage breakdown (capture_window_flag)
- FRESH_OPPORTUNITY:  4,985
- TRANSITIONAL:       439
- MONITOR:            402
- COLD_START:         6,541

## F2 hand-off
- Dropped 'Likely Lost' rows (handed to F2 win-back queue): 667

## Top 10 alerts

 alert_id  client_id product_family_biz           method                opportunity_type capture_window_flag  utilization_ratio  potential_value  f3_priority_score priority_level
F3-000001 1000081536      Biomateriales       cold_start         New Account Opportunity          COLD_START           0.000000          92473.0           0.974301    P1 Critical
F3-000002      17168      Biomateriales underutilization High Potential Underutilization   FRESH_OPPORTUNITY           0.015130         110967.6           0.958185    P1 Critical
F3-000003      33709      Biomateriales       cold_start         New Account Opportunity          COLD_START           0.000000          73978.4           0.912412    P1 Critical
F3-000004       7892      Biomateriales       cold_start         New Account Opportunity          COLD_START           0.000000          73978.4           0.912412    P1 Critical
F3-000005 1000076427      Biomateriales       cold_start         New Account Opportunity          COLD_START           0.000000          64731.1           0.876348    P1 Critical
F3-000006       3928      Biomateriales underutilization High Potential Underutilization   FRESH_OPPORTUNITY           0.034737          73978.4           0.871516    P1 Critical
F3-000007      32845      Biomateriales underutilization High Potential Underutilization   FRESH_OPPORTUNITY           0.157059         110967.6           0.864955    P1 Critical
F3-000008      30900      Biomateriales underutilization High Potential Underutilization   FRESH_OPPORTUNITY           0.067441          73978.4           0.851329    P1 Critical
F3-000009      24229      Biomateriales underutilization High Potential Underutilization   FRESH_OPPORTUNITY           0.187337         110967.6           0.844890    P1 Critical
F3-000010      36464      Biomateriales       cold_start         New Account Opportunity          COLD_START           0.000000          55483.8           0.835620    P1 Critical