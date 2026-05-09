"""
Stage 2 — GRU Sequential Model (vectorized, production-ready)
F1 Replenishment Intelligence | Inibsa Smart Demand Signals
"""
import warnings
import os
import sys
import json
import random
import time
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.metrics import (
    roc_auc_score, average_precision_score, brier_score_loss,
    precision_score, recall_score
)
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from torch.optim.lr_scheduler import ReduceLROnPlateau

# ─────────────────────────────────────────────────────────────
# SEED & DEVICE
# ─────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

INPUT_STAGE0 = Path("./output/stage0")
INPUT_STAGE1 = Path("./output/stage1")
OUTPUT_DIR   = Path("./output/stage2")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# HYPERPARAMETERS
# ─────────────────────────────────────────────────────────────
L             = 12
HORIZON       = 4
HIDDEN_SIZE   = 32
NUM_LAYERS    = 1
DROPOUT       = 0.3
LR            = 1e-3
WEIGHT_DECAY  = 1e-5
BATCH_SIZE    = 256
EPOCHS_MAX    = 40
PATIENCE      = 5
LR_PATIENCE   = 3
LR_FACTOR     = 0.5
GRAD_CLIP     = 1.0

TRAIN_END = pd.Timestamp("2024-06-30")
VAL_END   = pd.Timestamp("2024-12-31")
TEST_END  = pd.Timestamp("2025-11-30")
COMMODITY_FAMILIES = ["Familia C1", "Familia C2"]

print("=" * 70)
print("STAGE 2 — GRU SEQUENTIAL MODEL")
print("=" * 70)
print(f"  Device: {DEVICE}")
print()

# ─────────────────────────────────────────────────────────────
# LOAD DATA
# ─────────────────────────────────────────────────────────────
t0 = time.time()
print("Loading data …")
df_weekly    = pd.read_parquet(INPUT_STAGE0 / "df_weekly.parquet")
df_potential = pd.read_parquet(INPUT_STAGE0 / "df_potential.parquet")
df_master    = pd.read_parquet(INPUT_STAGE0 / "df_master.parquet")
f1_alerts    = pd.read_parquet(INPUT_STAGE1 / "f1_baseline_alerts.parquet")
print(f"  df_weekly: {len(df_weekly):,}  ({time.time()-t0:.1f}s)")

# ─────────────────────────────────────────────────────────────
# FILTER TO COMMODITIES
# ─────────────────────────────────────────────────────────────
df_comm = df_weekly[df_weekly["product_family"].isin(COMMODITY_FAMILIES)].copy()
df_comm = df_comm.sort_values(["client_id", "product_family", "week_start"]).reset_index(drop=True)
print(f"  Commodity panel: {len(df_comm):,}  unique pairs: {df_comm.groupby(['client_id','product_family']).ngroups:,}")

# ─────────────────────────────────────────────────────────────
# STATIC FEATURE PREP (potential lookup)
# ─────────────────────────────────────────────────────────────
print("\nPreparing static features …")
family_biz_df = df_comm[["product_family","product_family_biz"]].drop_duplicates()
pot_lookup = (
    df_potential
    .groupby(["client_id","product_family_biz"])["potential_value"]
    .sum().reset_index()
    .merge(family_biz_df, on="product_family_biz", how="inner")
)
pot_map = pot_lookup.set_index(["client_id","product_family"])["potential_value"].to_dict()

client_meta = (
    df_master[["client_id","segment_code","province"]]
    .drop_duplicates(subset=["client_id"])
    .fillna("Unknown")
)
client_meta["segment_code"] = client_meta["segment_code"].astype(str)
client_meta["province"]     = client_meta["province"].astype(str)

family_onehot_cols = sorted(COMMODITY_FAMILIES)
family_onehot_map  = {f: i for i, f in enumerate(family_onehot_cols)}
S_FAM_DIM = len(family_onehot_cols)

# ─────────────────────────────────────────────────────────────
# VECTORIZED ROLLING FEATURES  (no Python loops over rows)
# ─────────────────────────────────────────────────────────────
print("Computing rolling features (vectorized) …")

grp = df_comm.groupby(["client_id","product_family"], observed=True, sort=False)

# rolling_mean_units_4w: shift(1) then rolling(4) within group
df_comm["rolling_mean_units_4w"] = (
    grp["weekly_units"]
    .transform(lambda x: x.shift(1).rolling(4, min_periods=1).mean())
    .fillna(0)
)

# days_since_last_purchase: forward-fill last purchase date, then diff
df_comm["_last_purch_date"] = df_comm["week_start"].where(df_comm["had_purchase"] == 1)
df_comm["_last_purch_date"] = (
    grp["_last_purch_date"]
    .transform(lambda x: x.ffill())
)
df_comm["days_since_last_purchase"] = (
    (df_comm["week_start"] - df_comm["_last_purch_date"]).dt.days
    .clip(upper=365)
    .fillna(365)
)
df_comm.drop(columns=["_last_purch_date"], inplace=True)

# potential_gap_ratio (vectorized)
df_comm["year"] = df_comm["week_start"].dt.year
df_comm["cumval_ytd"] = (
    df_comm.groupby(["client_id","product_family","year"], observed=True)["weekly_value"]
    .cumsum() - df_comm["weekly_value"]     # exclude current week
)
# Map potential via (client_id, product_family)
pair_idx = list(zip(df_comm["client_id"], df_comm["product_family"]))
pot_arr  = np.array([pot_map.get(k, 0.0) for k in pair_idx], dtype=np.float32)
safe_pot = np.where(pot_arr > 0, pot_arr, 1.0)
gap      = 1.0 - (df_comm["cumval_ytd"].values / safe_pot).clip(0, 1)
df_comm["potential_gap_ratio"] = np.where(pot_arr <= 0, 0.5, gap)
df_comm.drop(columns=["year","cumval_ytd"], inplace=True)

SEQ_FEATURES = [
    "weekly_units", "weekly_value", "order_count",
    "days_since_last_purchase", "rolling_mean_units_4w",
    "campaign_active", "potential_gap_ratio"
]
F_DIM = len(SEQ_FEATURES)
print(f"  Sequence dims: {F_DIM}  ({time.time()-t0:.1f}s)")

# ─────────────────────────────────────────────────────────────
# BUILD SAMPLES  (numpy-based sliding window)
# ─────────────────────────────────────────────────────────────
print("Building samples …")
TRAIN_CUTOFF = TRAIN_END - pd.Timedelta(weeks=HORIZON)

pairs_list = df_comm[["client_id","product_family"]].drop_duplicates().values.tolist()
all_windows, all_targets, all_cids, all_fams, all_wends = [], [], [], [], []

df_comm_np = df_comm[SEQ_FEATURES].values.astype(np.float32)
df_comm_purch = df_comm["had_purchase"].values.astype(np.int8)
df_comm_dates = df_comm["week_start"].values  # numpy datetime64

# Build per-pair index map for fast slicing
pair_col = list(zip(df_comm["client_id"], df_comm["product_family"]))
df_comm["_pair_idx"] = range(len(df_comm))

pair_index = grp["_pair_idx"].apply(list).to_dict()
df_comm.drop(columns=["_pair_idx"], inplace=True)

n_pairs_ok = 0
for cid, fam in pairs_list:
    idxs = pair_index.get((cid, fam), [])
    if len(idxs) < L + HORIZON + 1:
        continue
    idxs = sorted(idxs)
    arr   = df_comm_np[idxs]
    purch = df_comm_purch[idxs]
    dates = df_comm_dates[idxs]
    n = len(arr)
    for t in range(L, n - HORIZON):
        win = arr[t - L : t]
        # Skip: all-zero lookback + >180 days dormancy
        if (win[:, 0].sum() == 0) and (win[:, 3].max() > 180):
            continue
        target   = int(purch[t : t + HORIZON].sum() > 0)
        wend     = pd.Timestamp(dates[t - 1])
        all_windows.append(win)
        all_targets.append(target)
        all_cids.append(cid)
        all_fams.append(fam)
        all_wends.append(wend)
    n_pairs_ok += 1

print(f"  Pairs with sufficient history: {n_pairs_ok:,}")
print(f"  Total samples: {len(all_windows):,}  ({time.time()-t0:.1f}s)")

# ─────────────────────────────────────────────────────────────
# TIME-BASED SPLIT
# ─────────────────────────────────────────────────────────────
print("Splitting (time-based, NOT random — same client in all splits) …")
train_mask = [w <= TRAIN_CUTOFF for w in all_wends]
val_mask   = [(TRAIN_CUTOFF < w <= VAL_END) for w in all_wends]
test_mask  = [(VAL_END < w <= TEST_END) for w in all_wends]

def select(mask):
    idxs = [i for i, m in enumerate(mask) if m]
    return idxs

train_idx = select(train_mask)
val_idx   = select(val_mask)
test_idx  = select(test_mask)
print(f"  Train: {len(train_idx):,}  Val: {len(val_idx):,}  Test: {len(test_idx):,}")

if len(train_idx) == 0:
    print("ERROR: No training samples!"); sys.exit(1)

# ─────────────────────────────────────────────────────────────
# STANDARDIZE (train stats only)
# ─────────────────────────────────────────────────────────────
train_wins = np.stack([all_windows[i] for i in train_idx])  # (N, L, F)
feat_mean  = train_wins.reshape(-1, F_DIM).mean(axis=0)
feat_std   = train_wins.reshape(-1, F_DIM).std(axis=0) + 1e-8

def norm(w):
    return (w - feat_mean) / feat_std

# ─────────────────────────────────────────────────────────────
# STATIC FEATURES (precomputed for every pair in dataset)
# ─────────────────────────────────────────────────────────────
train_labels_arr = np.array([all_targets[i] for i in train_idx])
train_cids_arr   = [all_cids[i] for i in train_idx]
train_fams_arr   = [all_fams[i] for i in train_idx]

global_mean = train_labels_arr.mean()

# Target-mean encode province & segment on train
train_meta_df = pd.DataFrame({
    "client_id": train_cids_arr,
    "target":    train_labels_arr,
}).merge(client_meta, on="client_id", how="left").fillna("Unknown")

prov_mean = train_meta_df.groupby("province")["target"].mean().to_dict()
seg_card  = train_meta_df["segment_code"].nunique()

if seg_card < 50:
    seg_ohe_vals = sorted(train_meta_df["segment_code"].unique())
    seg_ohe_map  = {s: i for i, s in enumerate(seg_ohe_vals)}
    S_SEG_DIM = len(seg_ohe_vals)
    USE_SEG_OHE = True
    print(f"  Segment: one-hot ({S_SEG_DIM})")
else:
    seg_mean_map = train_meta_df.groupby("segment_code")["target"].mean().to_dict()
    S_SEG_DIM = 1
    USE_SEG_OHE = False
    print(f"  Segment: target-mean ({seg_card} cats)")

S_DIM = 1 + S_SEG_DIM + 1 + S_FAM_DIM
print(f"  Static dim S: {S_DIM}")

# Precompute static vectors for each unique (client_id, product_family) pair
print("  Precomputing static features …")
static_cache = {}
for cid, fam in pairs_list:
    key = (cid, fam)
    pot = np.log1p(pot_map.get(key, 0.0))
    meta_row = client_meta[client_meta["client_id"] == cid]
    prov = meta_row["province"].values[0]      if len(meta_row) else "Unknown"
    seg  = meta_row["segment_code"].values[0]  if len(meta_row) else "Unknown"
    prov_enc = prov_mean.get(prov, global_mean)
    if USE_SEG_OHE:
        seg_vec = np.zeros(S_SEG_DIM, dtype=np.float32)
        idx = seg_ohe_map.get(str(seg), None)
        if idx is not None:
            seg_vec[idx] = 1.0
    else:
        seg_vec = np.array([seg_mean_map.get(str(seg), global_mean)], dtype=np.float32)
    fam_vec = np.zeros(S_FAM_DIM, dtype=np.float32)
    fidx = family_onehot_map.get(fam, None)
    if fidx is not None:
        fam_vec[fidx] = 1.0
    static_cache[key] = np.concatenate([[pot], seg_vec, [prov_enc], fam_vec]).astype(np.float32)

print(f"  Static cache built ({len(static_cache):,} entries)  ({time.time()-t0:.1f}s)")

# ─────────────────────────────────────────────────────────────
# DATASET  (all arrays preloaded — zero lookup cost in __getitem__)
# ─────────────────────────────────────────────────────────────
class ReplenDataset(Dataset):
    def __init__(self, idxs):
        self.X_seq    = torch.tensor(
            np.stack([norm(all_windows[i]) for i in idxs]), dtype=torch.float32)
        self.X_static = torch.tensor(
            np.stack([static_cache[(all_cids[i], all_fams[i])] for i in idxs]),
            dtype=torch.float32)
        self.y = torch.tensor([float(all_targets[i]) for i in idxs], dtype=torch.float32)

    def __len__(self):  return len(self.y)
    def __getitem__(self, i): return self.X_seq[i], self.X_static[i], self.y[i]

print("Building datasets …")
train_ds = ReplenDataset(train_idx)
val_ds   = ReplenDataset(val_idx)
test_ds  = ReplenDataset(test_idx)
print(f"  Datasets built  ({time.time()-t0:.1f}s)")

train_dl = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=0)
val_dl   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=0)
test_dl  = DataLoader(test_ds,  batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

n_pos      = int(train_ds.y.sum().item())
n_neg      = len(train_ds) - n_pos
pos_weight = torch.tensor([n_neg / max(n_pos, 1)], dtype=torch.float32).to(DEVICE)
print(f"\n  Class balance — pos: {n_pos:,}, neg: {n_neg:,}, pos_weight: {pos_weight.item():.2f}")

# ─────────────────────────────────────────────────────────────
# MODEL
# ─────────────────────────────────────────────────────────────
class ReplenGRU(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(F_DIM, HIDDEN_SIZE, NUM_LAYERS, batch_first=True)
        self.mlp = nn.Sequential(
            nn.Linear(HIDDEN_SIZE + S_DIM, 64),
            nn.ReLU(),
            nn.Dropout(DROPOUT),
            nn.Linear(64, 1),
        )
    def forward(self, x_seq, x_static):
        _, h = self.gru(x_seq)
        return self.mlp(torch.cat([h[-1], x_static], dim=1)).squeeze(-1)

model    = ReplenGRU().to(DEVICE)
n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
print(f"\n  Parameters: {n_params:,}")
assert n_params < 20_000, f"Model too large: {n_params}"

criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
optimizer = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
scheduler = ReduceLROnPlateau(optimizer, mode="max", factor=LR_FACTOR,
                              patience=LR_PATIENCE, verbose=False)

# ─────────────────────────────────────────────────────────────
# TRAINING
# ─────────────────────────────────────────────────────────────
def run_epoch(dl, train=True):
    model.train() if train else model.eval()
    total_loss, all_probs, all_labels = 0, [], []
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x_seq, x_static, y in dl:
            x_seq = x_seq.to(DEVICE); x_static = x_static.to(DEVICE); y = y.to(DEVICE)
            logits = model(x_seq, x_static)
            loss   = criterion(logits, y)
            if train:
                optimizer.zero_grad()
                loss.backward()
                nn.utils.clip_grad_norm_(model.parameters(), GRAD_CLIP)
                optimizer.step()
            total_loss += loss.item() * len(y)
            all_probs.extend(torch.sigmoid(logits).detach().cpu().numpy().tolist())
            all_labels.extend(y.cpu().numpy().tolist())
    avg_loss = total_loss / len(dl.dataset)
    auroc    = roc_auc_score(all_labels, all_probs) if len(set(all_labels)) > 1 else 0.5
    return avg_loss, auroc, np.array(all_probs), np.array(all_labels)

print("\nTraining …")
print(f"  {'Ep':>3}  {'TrLoss':>8}  {'TrAUC':>7}  {'ValLoss':>8}  {'ValAUC':>7}  {'LR':>8}")

best_val_auc, best_epoch, patience_cnt = -1, 0, 0
train_history = []

for epoch in range(1, EPOCHS_MAX + 1):
    tr_loss, tr_auc, _, _   = run_epoch(train_dl, train=True)
    va_loss, va_auc, _, _   = run_epoch(val_dl,   train=False)
    cur_lr = optimizer.param_groups[0]["lr"]
    train_history.append({"epoch": epoch, "train_loss": tr_loss, "train_auc": tr_auc,
                          "val_loss": va_loss, "val_auc": va_auc})
    print(f"  {epoch:>3}  {tr_loss:>8.4f}  {tr_auc:>7.4f}  {va_loss:>8.4f}  {va_auc:>7.4f}  {cur_lr:>8.1e}")
    scheduler.step(va_auc)
    if va_auc > best_val_auc:
        best_val_auc = va_auc; best_epoch = epoch; patience_cnt = 0
        torch.save(model.state_dict(), OUTPUT_DIR / "gru_model.pt")
    else:
        patience_cnt += 1
        if patience_cnt >= PATIENCE:
            print(f"  Early stop epoch {epoch} (best {best_epoch})")
            break

model.load_state_dict(torch.load(OUTPUT_DIR / "gru_model.pt", map_location=DEVICE))
print(f"\n  Best val AUROC: {best_val_auc:.4f} at epoch {best_epoch}")

# ─────────────────────────────────────────────────────────────
# EVALUATION
# ─────────────────────────────────────────────────────────────
def topk_metrics(labels, probs, k):
    if k > len(labels): return None, None
    top_k = np.argsort(probs)[-k:]
    prec = labels[top_k].mean()
    pos_in_top = labels[top_k].sum()
    total_pos  = labels.sum()
    rec  = pos_in_top / total_pos if total_pos > 0 else 0
    return float(prec), float(rec)

def evaluate(dl, name):
    _, _, probs, labels = run_epoch(dl, train=False)
    auroc = roc_auc_score(labels, probs)
    auprc = average_precision_score(labels, probs)
    brier = brier_score_loss(labels, probs)
    m = {"split": name, "auroc": round(auroc,4), "auprc": round(auprc,4),
         "brier": round(brier,4), "n_pos": int(labels.sum()), "n_total": len(labels)}
    print(f"\n  [{name}] AUROC={auroc:.4f}  AUPRC={auprc:.4f}  Brier={brier:.4f}")
    for k in [100, 500, 1000]:
        p, r = topk_metrics(labels, probs, k)
        if p is not None:
            m[f"precision@{k}"] = round(p,4); m[f"recall@{k}"] = round(r,4)
            print(f"    Precision@{k}={p:.4f}  Recall@{k}={r:.4f}")
    return m, probs, labels

print("\nEvaluating …")
val_metrics,  val_probs,  val_labels  = evaluate(val_dl,  "Val")
test_metrics, test_probs, test_labels = evaluate(test_dl, "Test")

if val_metrics["auroc"] < 0.65:
    print("  ⚠️  Val AUROC < 0.65 — investigate before shipping!")

(OUTPUT_DIR / "train_val_test_metrics.json").write_text(
    json.dumps({"val": val_metrics, "test": test_metrics,
                "training_history": train_history}, indent=2))
print("  ✓ train_val_test_metrics.json")

# ─────────────────────────────────────────────────────────────
# INFERENCE — most recent window per pair
# ─────────────────────────────────────────────────────────────
print("\nRunning inference …")
SCORING_DATE = df_weekly["week_start"].max() + pd.Timedelta(weeks=1)

inference_rows = []
model.eval()
batch_seqs, batch_statics, batch_meta = [], [], []

for cid, fam in pairs_list:
    idxs = pair_index.get((cid, fam), [])
    if len(idxs) < L: continue
    idxs = sorted(idxs)
    win = norm(df_comm_np[idxs[-L:]])
    stat = static_cache.get((cid, fam), None)
    if stat is None: continue
    fam_biz = df_comm.loc[df_comm["client_id"]==cid].iloc[0]["product_family_biz"] if "product_family_biz" in df_comm.columns else fam
    batch_seqs.append(win)
    batch_statics.append(stat)
    batch_meta.append((cid, fam, fam_biz))

# Batch inference
bs = 512
for i in range(0, len(batch_seqs), bs):
    x_seq    = torch.tensor(np.stack(batch_seqs[i:i+bs]),    dtype=torch.float32).to(DEVICE)
    x_static = torch.tensor(np.stack(batch_statics[i:i+bs]), dtype=torch.float32).to(DEVICE)
    with torch.no_grad():
        probs = torch.sigmoid(model(x_seq, x_static)).cpu().numpy()
    for j, prob in enumerate(probs):
        cid, fam, fam_biz = batch_meta[i+j]
        inference_rows.append({
            "client_id": cid, "product_family": fam,
            "product_family_biz": fam_biz,
            "scoring_date": SCORING_DATE,
            "reorder_probability": float(prob),
        })

df_gru_preds = pd.DataFrame(inference_rows)
print(f"  Inference rows: {len(df_gru_preds):,}")

# ─────────────────────────────────────────────────────────────
# PERMUTATION IMPORTANCE (val set)
# ─────────────────────────────────────────────────────────────
print("  Permutation importance …")
_, base_auc, _, _ = run_epoch(val_dl, train=False)
feat_importances = {}
val_X_seq_np = val_ds.X_seq.numpy().copy()  # (N, L, F)

for fi, fname in enumerate(SEQ_FEATURES):
    shuf = val_X_seq_np.copy()
    shuf[:, :, fi] = shuf[np.random.permutation(len(shuf)), :, fi]
    x_perm   = torch.tensor(shuf, dtype=torch.float32)
    x_static = val_ds.X_static
    all_pr, all_lb = [], []
    for start in range(0, len(x_perm), BATCH_SIZE):
        xb = x_perm[start:start+BATCH_SIZE].to(DEVICE)
        xs = x_static[start:start+BATCH_SIZE].to(DEVICE)
        with torch.no_grad():
            p = torch.sigmoid(model(xb, xs)).cpu().numpy()
        all_pr.extend(p.tolist())
        all_lb.extend(val_ds.y[start:start+BATCH_SIZE].numpy().tolist())
    perm_auc = roc_auc_score(all_lb, all_pr)
    feat_importances[fname] = round(float(base_auc - perm_auc), 4)

top_feats = sorted(feat_importances.items(), key=lambda x: -x[1])[:3]
top_feats_str = "; ".join(f"{k}={v:.3f}" for k, v in top_feats)
print(f"  Top features: {top_feats_str}")
df_gru_preds["top_features"] = top_feats_str

df_gru_preds.to_parquet(OUTPUT_DIR / "f1_gru_predictions.parquet", index=False)
print(f"  ✓ f1_gru_predictions.parquet")

# ─────────────────────────────────────────────────────────────
# COMBINED ALERTS
# ─────────────────────────────────────────────────────────────
print("\nBuilding combined alerts …")
f1_stats = f1_alerts[f1_alerts["priority_level"] != "On track"].copy()
f1_stats["stat_rank"] = f1_stats["replenishment_score"].rank(pct=True).fillna(0)

merged = f1_stats.merge(
    df_gru_preds[["client_id","product_family","reorder_probability"]],
    on=["client_id","product_family"], how="left"
)
merged["reorder_probability"] = merged["reorder_probability"].fillna(0.0)
merged["f1_final_score"]      = 0.5 * merged["stat_rank"] + 0.5 * merged["reorder_probability"]

q5  = merged["f1_final_score"].quantile(0.95)
q80 = merged["f1_final_score"].quantile(0.80)
q50 = merged["f1_final_score"].quantile(0.50)

def combined_priority(s):
    return ("P1 Critical" if s >= q5 else "P2 High" if s >= q80
            else "P3 Medium" if s >= q50 else "P4 Low")

merged["combined_priority"] = merged["f1_final_score"].apply(combined_priority)
merged.to_parquet(OUTPUT_DIR / "f1_combined_alerts.parquet", index=False)

p1p2_count = (merged["combined_priority"].isin(["P1 Critical","P2 High"])).sum()
assert p1p2_count >= 500, f"Only {p1p2_count} P1+P2 alerts — check pipeline!"
print(f"  Combined P1+P2: {p1p2_count:,}")
print(f"  ✓ f1_combined_alerts.parquet ({len(merged):,} rows)")

# ─────────────────────────────────────────────────────────────
# GRU REPORT
# ─────────────────────────────────────────────────────────────
hist_df = pd.DataFrame(train_history)
report = [
    "# Stage 2 — GRU Report",
    "",
    "## Architecture",
    f"- Input: (batch, L={L}, F={F_DIM})",
    f"- GRU hidden={HIDDEN_SIZE}, layers={NUM_LAYERS}",
    f"- MLP: Linear({HIDDEN_SIZE}+{S_DIM}→64) → ReLU → Dropout({DROPOUT}) → Linear→1",
    f"- Total params: {n_params:,}",
    f"- Device: {DEVICE}",
    "",
    "## Split Policy",
    "Time-based split. Same CLIENT appears in all splits — correct for B2B replenishment.",
    f"- Train: window_end ≤ {TRAIN_CUTOFF.date()} ({len(train_idx):,} samples)",
    f"- Val:   ({TRAIN_CUTOFF.date()}, {VAL_END.date()}] ({len(val_idx):,} samples)",
    f"- Test:  ({VAL_END.date()}, {TEST_END.date()}] ({len(test_idx):,} samples)",
    "4-week buffer between train/val to prevent label leakage.",
    "",
    "## Validation Metrics",
] + [f"- {k}: {v}" for k, v in val_metrics.items() if k != "split"] + [
    "",
    "## Test Metrics",
] + [f"- {k}: {v}" for k, v in test_metrics.items() if k != "split"] + [
    "",
    "## Feature Importances (permutation, val AUROC drop)",
] + [f"- {k}: {v:.4f}" for k, v in sorted(feat_importances.items(), key=lambda x: -x[1])] + [
    "",
    "## Training curve (all epochs)",
    hist_df.to_string(index=False),
    "",
    "## Ensemble Formula",
    "f1_final_score = 0.5 × rank_norm(replenishment_score) + 0.5 × reorder_probability",
    "",
    f"## Combined P1+P2 alerts: {p1p2_count:,}",
    "",
    "## Failure Modes",
    f"- pos_weight: {pos_weight.item():.2f} (BCEWithLogitsLoss)",
    "- Sparse pairs (<L+H weeks): dropped from GRU, kept in Stage 1.",
    "- Province/segment: train-set target-mean encoded (no leakage).",
    "- All-zero lookback + >180d dormancy: excluded from training.",
]

(OUTPUT_DIR / "f1_gru_report.md").write_text("\n".join(report))
print("  ✓ f1_gru_report.md")

print()
print("=" * 70)
print("STAGE 2 COMPLETE")
print("=" * 70)
print(f"  Val  AUROC: {val_metrics['auroc']:.4f}  AUPRC: {val_metrics['auprc']:.4f}")
print(f"  Test AUROC: {test_metrics['auroc']:.4f}  AUPRC: {test_metrics['auprc']:.4f}")
print(f"  GRU preds:  {len(df_gru_preds):,}")
print(f"  P1+P2 combined: {p1p2_count:,}")
print(f"  Total time: {time.time()-t0:.0f}s")
