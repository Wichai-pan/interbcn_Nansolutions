"""
Stage 0 — Data Preprocessing & Master Panel Construction
F1 Replenishment Intelligence | Inibsa Smart Demand Signals
"""
import warnings
import os
import sys
import random
import numpy as np
import pandas as pd
from pathlib import Path

# ─────────────────────────────────────────────────────────────
# SEED & PATHS
# ─────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

DATA_DIR   = Path("./notebook_data")
OUTPUT_DIR = Path("./output/stage0")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# 0.2 PRODUCT FAMILY MAPPING  (ASSUMPTION — edit if sponsor confirms)
# ─────────────────────────────────────────────────────────────
MAP_FAMILY_TO_BUSINESS = {
    "Familia C1": "Anestesia",       # commodity, anesthetics
    "Familia C2": "Bioseguridad",    # commodity, biosafety/PPE
    "Familia T1": "Biomateriales",   # technical, biomaterials
    "Familia T2": "Biomateriales",   # technical, biomaterials
}

print("=" * 70)
print("STAGE 0 — DATA PREPROCESSING")
print("=" * 70)
print()
print("⚠️  WARNING: FAMILY MAPPING IS AN ASSUMPTION — verify with sponsor.")
print("   MAP_FAMILY_TO_BUSINESS:", MAP_FAMILY_TO_BUSINESS)
print()

# ─────────────────────────────────────────────────────────────
# LOAD RAW FILES
# ─────────────────────────────────────────────────────────────
def load_csv(name, **kwargs):
    path = DATA_DIR / name
    df = pd.read_csv(path, **kwargs)
    print(f"  Loaded {name}: {len(df):,} rows × {df.shape[1]} cols")
    return df

print("Loading raw files …")
ventas    = load_csv("Ventas.csv")
productos = load_csv("Productos.csv")
potencial = load_csv("Potencial.csv")
clientes  = load_csv("Clientes.csv")
campanas  = load_csv("Campañas.csv")
print()

# ─────────────────────────────────────────────────────────────
# 0.1 COLUMN NORMALIZATION
# ─────────────────────────────────────────────────────────────
print("Normalizing column names …")

# Ventas
ventas = ventas.rename(columns={
    "Id. Cliente":  "client_id",
    "Id. Producto": "product_id",
    "Fecha":        "date",
    "Unidades":     "units",
    "Valores_H":    "sales_value",
})
ventas["client_id"]  = ventas["client_id"].astype(str).str.strip()
ventas["product_id"] = ventas["product_id"].astype(str).str.strip()
ventas["date"]       = pd.to_datetime(ventas["date"], dayfirst=False)

# Productos
productos = productos.rename(columns={
    "Id.Prod":           "product_id",
    "Bloque analítico":  "product_block",
    "Categoria_H":       "category",
    "Familia_H":         "product_family",
})
productos["product_id"] = productos["product_id"].astype(str).str.strip()
productos["product_family_biz"] = productos["product_family"].map(MAP_FAMILY_TO_BUSINESS)

# Clientes
clientes = clientes.rename(columns={
    "Id. Cliente": "client_id",
    "Unnamed: 1":  "segment_code",
    "Provincia":   "province",
})
clientes["client_id"]    = clientes["client_id"].astype(str).str.strip()
clientes["segment_code"] = clientes["segment_code"].astype(str).str.strip()

# Potencial
potencial = potencial.rename(columns={
    "Id.Cliente":          "client_id",
    "Familia":             "product_family_biz",
    "Categoria Productos": "category",
    "Potencial_H":         "potential_value",
})
potencial["client_id"] = potencial["client_id"].astype(str).str.strip()

# Campañas
campanas = campanas.rename(columns={
    "Fecha inicio": "date_start",
    "Fecha fin":    "date_end",
})
campanas["date_start"] = pd.to_datetime(campanas["date_start"], dayfirst=False)
campanas["date_end"]   = pd.to_datetime(campanas["date_end"],   dayfirst=False)

print("  Column normalization complete.")
print()

# ─────────────────────────────────────────────────────────────
# 0.3 SALES CLEANING
# ─────────────────────────────────────────────────────────────
print("Cleaning Ventas …")
n_raw = len(ventas)
print(f"  Rows before cleaning: {n_raw:,}")

# 1. Drop null key fields
mask_null = ventas["client_id"].isna() | ventas["product_id"].isna() | ventas["date"].isna()
n_null = mask_null.sum()
ventas = ventas[~mask_null].copy()
print(f"  Dropped {n_null:,} rows with null client_id/product_id/date")

# 2. Tag returns
ventas["is_return"] = (ventas["units"] < 0) | (ventas["sales_value"] < 0)
n_returns = ventas["is_return"].sum()
print(f"  Tagged {n_returns:,} return rows ({n_returns/len(ventas)*100:.1f}%) — kept")

# 3. Deduplicate identical invoice rows
dup_keys = ["Num.Fact", "client_id", "product_id", "date"]
n_before_dedup = len(ventas)
ventas = ventas.drop_duplicates(subset=dup_keys)
n_dedup = n_before_dedup - len(ventas)
print(f"  Dropped {n_dedup:,} duplicate rows (same Num.Fact + client + product + date)")

# 4. Sanity price filter (unit_price > 10,000 EUR)
# Avoid division by zero: only compute price where units != 0
non_zero = ventas["units"] != 0
ventas["unit_price"] = np.where(non_zero, ventas["sales_value"] / ventas["units"], 0.0)
mask_price = np.abs(ventas["unit_price"]) > 10_000
n_price = mask_price.sum()
ventas = ventas[~mask_price].copy()
print(f"  Dropped {n_price:,} rows with |unit_price| > 10,000 EUR")

print(f"  Rows after cleaning: {len(ventas):,}")
print()

# ─────────────────────────────────────────────────────────────
# 0.4 MASTER MERGE  (transaction-level)
# ─────────────────────────────────────────────────────────────
print("Building df_master (transaction-level) …")
n_before = len(ventas)

df_master = (
    ventas
    .merge(productos[["product_id", "product_block", "category",
                       "product_family", "product_family_biz"]],
           on="product_id", how="left")
    .merge(clientes[["client_id", "segment_code", "province"]],
           on="client_id", how="left")
)

# Clients in Ventas but not in Clientes → province = Unknown
mask_unknown = df_master["province"].isna()
df_master.loc[mask_unknown, "province"]      = "Unknown"
df_master.loc[mask_unknown, "segment_code"]  = "Unknown"
n_unknown_clients = df_master.loc[mask_unknown, "client_id"].nunique()
print(f"  {n_unknown_clients:,} clients found in Ventas but not in Clientes → province=Unknown")
print(f"  df_master: {len(df_master):,} rows × {df_master.shape[1]} cols")
print()

# Build df_potential as a lookup (NOT merged into transactions)
print("Building df_potential lookup …")
df_potential = potencial.copy()
print(f"  df_potential: {len(df_potential):,} rows × {df_potential.shape[1]} cols")
print()

# ─────────────────────────────────────────────────────────────
# 0.7 COLD-START CLIENTS
# ─────────────────────────────────────────────────────────────
print("Identifying cold-start clients …")
clients_in_ventas    = set(df_master["client_id"].unique())
clients_in_potencial = set(df_potential["client_id"].unique())
cold_client_ids      = clients_in_potencial - clients_in_ventas

df_cold_clients = (
    df_potential[df_potential["client_id"].isin(cold_client_ids)]
    .drop_duplicates(subset=["client_id"])
    [["client_id"]]
    .merge(clientes[["client_id", "segment_code", "province"]],
           on="client_id", how="left")
)
print(f"  Cold-start clients (in Potencial but NOT in Ventas): {len(df_cold_clients):,}")
print()

# ─────────────────────────────────────────────────────────────
# 0.5 WEEKLY PANEL CONSTRUCTION
# ─────────────────────────────────────────────────────────────
print("Building weekly panel …")

# Snap each transaction to ISO week Monday
df_master["week_start"] = df_master["date"].dt.to_period("W-SUN").apply(
    lambda p: p.start_time.date()
)
df_master["week_start"] = pd.to_datetime(df_master["week_start"])

# Date range for the panel
PANEL_END = pd.Timestamp("2025-12-29")

# Aggregate: only positive units/values for purchase metrics
def agg_weekly(grp):
    pos = grp[grp["units"] > 0]
    ret = grp[grp["units"] < 0]
    return pd.Series({
        "weekly_units":  pos["units"].sum()        if len(pos) > 0 else 0.0,
        "weekly_value":  pos["sales_value"].sum()  if len(pos) > 0 else 0.0,
        "order_count":   pos["Num.Fact"].nunique()  if len(pos) > 0 else 0,
        "return_units":  ret["units"].abs().sum()  if len(ret) > 0 else 0.0,
        "had_purchase":  1 if len(pos) > 0 else 0,
    })

agg = (
    df_master
    .groupby(["client_id", "product_family", "week_start"], observed=True)
    .apply(agg_weekly)
    .reset_index()
)
print(f"  Aggregated transactions: {len(agg):,} (client × family × week)")

# Pull product_family_biz for each product_family (static mapping)
family_biz_map = (
    df_master[["product_family", "product_family_biz"]]
    .drop_duplicates()
    .dropna(subset=["product_family"])
)

# Build complete weekly grid (fill missing weeks with 0)
print("  Building complete weekly grid (filling gaps) …")
pairs = agg[["client_id", "product_family"]].drop_duplicates()
n_pairs = len(pairs)
print(f"  Unique (client × family) pairs: {n_pairs:,}")

# Get per-pair date ranges
min_dates = (
    agg.groupby(["client_id", "product_family"], observed=True)["week_start"]
    .min().reset_index().rename(columns={"week_start": "min_date"})
)
pairs = pairs.merge(min_dates, on=["client_id", "product_family"])

# Generate all weeks from min_date to PANEL_END
all_weeks_global = pd.date_range(
    start=agg["week_start"].min(),
    end=PANEL_END,
    freq="W-MON"
)

# Expand: for each pair, weeks from their min_date onward
rows = []
for _, row in pairs.iterrows():
    weeks_for_pair = all_weeks_global[all_weeks_global >= row["min_date"]]
    tmp = pd.DataFrame({
        "client_id":      row["client_id"],
        "product_family": row["product_family"],
        "week_start":     weeks_for_pair,
    })
    rows.append(tmp)

df_grid = pd.concat(rows, ignore_index=True)
print(f"  Full grid rows (before merge): {len(df_grid):,}")

# Merge actuals into grid
df_weekly = df_grid.merge(agg, on=["client_id", "product_family", "week_start"], how="left")

# Fill missing weeks with 0
fill_cols = ["weekly_units", "weekly_value", "order_count", "return_units", "had_purchase"]
df_weekly[fill_cols] = df_weekly[fill_cols].fillna(0)

# Attach product_family_biz
df_weekly = df_weekly.merge(family_biz_map, on="product_family", how="left")

print(f"  df_weekly: {len(df_weekly):,} rows × {df_weekly.shape[1]} cols")
print()

# ─────────────────────────────────────────────────────────────
# 0.6 CAMPAIGN FLAG
# ─────────────────────────────────────────────────────────────
print("Adding campaign_active flag …")
unique_weeks = df_weekly["week_start"].unique()
campaign_active_map = {}
for w in unique_weeks:
    week_end = w + pd.Timedelta(days=6)
    active = any(
        (row["date_start"] <= week_end) and (row["date_end"] >= w)
        for _, row in campanas.iterrows()
    )
    campaign_active_map[w] = int(active)

df_weekly["campaign_active"] = df_weekly["week_start"].map(campaign_active_map)
n_campaign_weeks = sum(v for v in campaign_active_map.values())
print(f"  Weeks with campaign_active=1: {n_campaign_weeks:,} / {len(unique_weeks):,}")
print()

# ─────────────────────────────────────────────────────────────
# 0.8 SAVE DELIVERABLES
# ─────────────────────────────────────────────────────────────
print("Saving Stage 0 outputs …")

# Ensure mixed-type columns are cast to string before parquet
df_master["Num.Fact"] = df_master["Num.Fact"].astype(str)

df_master.to_parquet(OUTPUT_DIR / "df_master.parquet", index=False)
print(f"  ✓ df_master.parquet ({len(df_master):,} rows)")

df_weekly.to_parquet(OUTPUT_DIR / "df_weekly.parquet", index=False)
print(f"  ✓ df_weekly.parquet ({len(df_weekly):,} rows)")

df_potential.to_parquet(OUTPUT_DIR / "df_potential.parquet", index=False)
print(f"  ✓ df_potential.parquet ({len(df_potential):,} rows)")

df_cold_clients.to_parquet(OUTPUT_DIR / "df_cold_clients.parquet", index=False)
print(f"  ✓ df_cold_clients.parquet ({len(df_cold_clients):,} rows)")

# ─────────────────────────────────────────────────────────────
# PREPROCESSING REPORT
# ─────────────────────────────────────────────────────────────
date_cov = (
    df_master.groupby("client_id")["date"]
    .agg(["min", "max"])
    .describe()
)

report_lines = [
    "# Stage 0 — Preprocessing Report",
    "",
    "## Row counts",
    f"- Ventas raw:                   {n_raw:,}",
    f"- Dropped (null key fields):    {n_null:,}",
    f"- Return rows (tagged, kept):   {n_returns:,}",
    f"- Deduplicated rows removed:    {n_dedup:,}",
    f"- Price-filter removed:         {n_price:,}",
    f"- df_master (final):            {len(df_master):,}",
    "",
    "## Panel",
    f"- Unique (client × family) pairs: {n_pairs:,}",
    f"- df_weekly rows:                 {len(df_weekly):,}",
    f"- Panel end date:                 {PANEL_END.date()}",
    f"- Campaign-active weeks:          {n_campaign_weeks}",
    "",
    "## Clients",
    f"- Active clients in Ventas:       {df_master['client_id'].nunique():,}",
    f"- Cold-start clients (Potencial only): {len(df_cold_clients):,}",
    f"- Clients in Ventas not in Clientes:   {n_unknown_clients:,} (province=Unknown)",
    "",
    "## ⚠️  Family Mapping Decision (ASSUMPTION — not confirmed by sponsor)",
    "```",
    "Familia C1 → Anestesia      (commodity anesthetics)",
    "Familia C2 → Bioseguridad   (commodity biosafety/PPE)",
    "Familia T1 → Biomateriales  (technical biomaterials)",
    "Familia T2 → Biomateriales  (technical biomaterials)",
    "```",
    "Note: Potencial.csv has 3 business names vs 4 family codes.",
    "T1 and T2 both map to Biomateriales — verify with sponsor.",
    "",
    "## Date coverage",
    f"- Earliest transaction: {df_master['date'].min().date()}",
    f"- Latest transaction:   {df_master['date'].max().date()}",
    "",
    "## Products",
    f"- Unique products: {df_master['product_id'].nunique():,}",
    f"- Product families: {df_master['product_family'].nunique():,}",
    f"  {list(df_master['product_family'].unique())}",
    f"- Product blocks: {list(df_master['product_block'].dropna().unique())}",
]

report_path = OUTPUT_DIR / "preprocessing_report.md"
report_path.write_text("\n".join(report_lines))
print(f"  ✓ preprocessing_report.md")

# Env log
import pkg_resources
env_lines = [f"{pkg.key}=={pkg.version}" for pkg in pkg_resources.working_set]
(Path("./output") / "env.txt").write_text("\n".join(sorted(env_lines)))
print(f"  ✓ env.txt")

print()
print("=" * 70)
print("STAGE 0 COMPLETE")
print("=" * 70)
print(f"  df_master:      {len(df_master):,} rows")
print(f"  df_weekly:      {len(df_weekly):,} rows")
print(f"  df_potential:   {len(df_potential):,} rows")
print(f"  df_cold_clients:{len(df_cold_clients):,} rows")
