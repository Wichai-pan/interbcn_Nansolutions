# Stage 0 — Preprocessing Report

## Row counts
- Ventas raw:                   162,546
- Dropped (null key fields):    0
- Return rows (tagged, kept):   3,880
- Deduplicated rows removed:    0
- Price-filter removed:         0
- df_master (final):            163,052

## Panel
- Unique (client × family) pairs: 15,047
- df_weekly rows:                 2,891,786
- Panel end date:                 2025-12-29
- Campaign-active weeks:          12

## Clients
- Active clients in Ventas:       8,095
- Cold-start clients (Potencial only): 2,940
- Clients in Ventas not in Clientes:   34 (province=Unknown)

## ⚠️  Family Mapping Decision (ASSUMPTION — not confirmed by sponsor)
```
Familia C1 → Anestesia      (commodity anesthetics)
Familia C2 → Bioseguridad   (commodity biosafety/PPE)
Familia T1 → Biomateriales  (technical biomaterials)
Familia T2 → Biomateriales  (technical biomaterials)
```
Note: Potencial.csv has 3 business names vs 4 family codes.
T1 and T2 both map to Biomateriales — verify with sponsor.

## Date coverage
- Earliest transaction: 2021-01-04
- Latest transaction:   2025-12-29

## Products
- Unique products: 25
- Product families: 4
  ['Familia C1', 'Familia T1', 'Familia C2', 'Familia T2']
- Product blocks: ['Commodities', 'Productos Técnicos']