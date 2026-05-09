# Stage 1 — Baseline Diagnostics

## Coverage
- Total scored pairs:   8,450
- Overdue (score > 0):  4,570
- On track:             3,880

## Priority Distribution
- P1 Critical: 230
- P2 High: 689
- P3 Medium: 1366
- P4 Low: 2285
- On track: 3,880

## Confidence Level Coverage
- low: 4017
- high: 2634
- medium: 1799

## Score Distribution (overdue population)
- count: 4570
- mean:  3.762
- std:   7.594
- min:   0.000
- 25%:   0.747
- 50%:   2.343
- 75%:   5.348
- max:   316.358

## P1+P2 Alert Count: 919

## Top 10 Alerts

 client_id product_family_biz priority_level  days_since_last_purchase  expected_interval  seasonal_time_score  replenishment_score confidence_level
1000073191       Bioseguridad    P1 Critical                      1687          23.333333           460.239521           316.357859           medium
     36492       Bioseguridad    P1 Critical                      1414          31.500000           197.500000           144.067483             high
1000081322          Anestesia    P1 Critical                      1428          74.200000           169.623021           128.527486           medium
      9184       Bioseguridad    P1 Critical                      1428          67.200000           128.183564            88.110377           medium
1000037345       Bioseguridad    P1 Critical                      1715          28.000000           120.500000            87.899401           medium
     41044          Anestesia    P1 Critical                      1309          28.000000            91.500000            79.412989             high
1000051951          Anestesia    P1 Critical                       896          31.500000            94.324683            78.105127             high
     37516          Anestesia    P1 Critical                      1484          66.500000            97.277853            77.799836           medium
1000080181          Anestesia    P1 Critical                       812          29.166667            95.662113            72.485508             high
     26122          Anestesia    P1 Critical                      1351          72.333333            70.746496            61.400991           medium

## Notes
- Value factor uses log1p normalization (skewed EUR distribution)
- STD epsilon = 3 days to prevent score explosion for very regular clients
- Priority bins: P1=top 5%, P2=next 15%, P3=next 30%, P4=remaining 50%