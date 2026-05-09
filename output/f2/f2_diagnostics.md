# F2 — Lost Customer Risk Diagnostics

**Scoring date:** 2026-01-05

## Branch counts (before dedup)
- Branch A (T silence):       3,831
- Branch B (C direct >730d):  0
- Branch C (C historical):    852
- Duplicates dropped on merge: 0
- **Total alerts:** 4,683

## lost_status distribution
- Likely Lost: 3,009
- Early Warning: 951
- At Risk: 723

## priority_level distribution
- P4 Low: 2,341
- P3 Medium: 1,405
- P2 High: 702
- P1 Critical: 235

## product_family distribution
- Familia T1: 2,243
- Familia T2: 1,588
- Familia C1: 656
- Familia C2: 196

## Top 10 provinces
- Madrid: 845
- Barcelona: 484
- Valencia: 262
- Sevilla: 217
- Asturias: 153
- A Coruña: 148
- Granada: 147
- Vizcaya: 141
- Sta.Cruz Tenerife: 135
- Murcia: 132

## Branch C skipped (hist_purchase_months < 2)
- 1,295 pairs

## f1_scope exclusion (C-products already flagged by F1)
- excluded from B/C consideration: 4,570 pairs

## Merge dedup
- duplicates dropped (higher raw_score kept): 0

## Top 10 alerts

 alert_id  client_id product_family_biz        method lost_status priority_level  f2_priority_score  days_since_last_purchase
F2-000001       7135      Biomateriales silence_score Likely Lost    P1 Critical          90.114929                      1753
F2-000002      40798      Biomateriales silence_score Likely Lost    P1 Critical          55.977134                      1735
F2-000003 1000077426      Biomateriales silence_score Likely Lost    P1 Critical          49.757085                      1530
F2-000004 1000082371      Biomateriales silence_score Likely Lost    P1 Critical          47.245691                      1407
F2-000005      37252      Biomateriales silence_score Likely Lost    P1 Critical          44.354843                      1524
F2-000006 1000072252      Biomateriales silence_score Likely Lost    P1 Critical          41.364408                      1734
F2-000007      12055      Biomateriales silence_score Likely Lost    P1 Critical          40.699352                      1481
F2-000008      21659      Biomateriales silence_score Likely Lost    P1 Critical          36.460035                      1687
F2-000009 1000080858      Biomateriales silence_score Likely Lost    P1 Critical          33.117843                      1523
F2-000010 1000080433      Biomateriales silence_score Likely Lost    P1 Critical          31.657808                      1545